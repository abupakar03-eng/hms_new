import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'models.dart';

/// Raised for any non-2xx response, carrying the backend's `detail` when present.
class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);

  bool get isAuthError => statusCode == 401 || statusCode == 403;

  @override
  String toString() => message;
}

/// Persisted credentials.
///
/// Tokens live in `SharedPreferences`, which is the standard store available
/// without extra plugins. A production deployment handling real PHI should move
/// these to the platform keystore (`flutter_secure_storage`).
class TokenStore {
  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';
  static const _kUser = 'session_user';

  static Future<void> save(AuthTokens tokens, SessionUser user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAccess, tokens.accessToken);
    if (tokens.refreshToken != null) {
      await prefs.setString(_kRefresh, tokens.refreshToken!);
    }
    await prefs.setString(_kUser, jsonEncode({
      'id': user.id,
      'username': user.username,
      'role': user.role,
      'patient_id': user.patientId,
      'full_name': user.fullName,
    }));
  }

  static Future<String?> accessToken() async =>
      (await SharedPreferences.getInstance()).getString(_kAccess);

  static Future<String?> refreshToken() async =>
      (await SharedPreferences.getInstance()).getString(_kRefresh);

  static Future<SessionUser?> user() async {
    final raw = (await SharedPreferences.getInstance()).getString(_kUser);
    if (raw == null) return null;
    try {
      return SessionUser.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kAccess);
    await prefs.remove(_kRefresh);
    await prefs.remove(_kUser);
  }
}

/// Thin, dependency-light client over the hospital REST API.
///
/// On a 401 it transparently refreshes the access token once and replays the
/// request; if that also fails the caller sees the error and the app signs out.
class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;

  Uri _uri(String path) => Uri.parse('${AppConfig.apiBase}$path');

  Future<Map<String, String>> _headers({bool json = true}) async {
    final headers = <String, String>{'Accept': 'application/json'};
    if (json) headers['Content-Type'] = 'application/json';
    final token = await TokenStore.accessToken();
    if (token != null) headers['Authorization'] = 'Bearer $token';
    return headers;
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? query,
    bool retryOnAuthFailure = true,
  }) async {
    var uri = _uri(path);
    if (query != null && query.isNotEmpty) {
      uri = uri.replace(queryParameters: query);
    }
    final headers = await _headers();
    final encoded = body == null ? null : jsonEncode(body);

    late http.Response response;
    try {
      switch (method) {
        case 'GET':
          response = await _client.get(uri, headers: headers).timeout(AppConfig.requestTimeout);
        case 'POST':
          response = await _client
              .post(uri, headers: headers, body: encoded)
              .timeout(AppConfig.requestTimeout);
        case 'PUT':
          response = await _client
              .put(uri, headers: headers, body: encoded)
              .timeout(AppConfig.requestTimeout);
        case 'DELETE':
          response = await _client.delete(uri, headers: headers).timeout(AppConfig.requestTimeout);
        default:
          throw ApiException(0, 'Unsupported method $method');
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(0, 'Cannot reach the hospital server.\n${AppConfig.apiLabel}\n$e');
    }

    if (response.statusCode == 401 && retryOnAuthFailure) {
      if (await _refresh()) {
        return _send(method, path, body: body, query: query, retryOnAuthFailure: false);
      }
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(utf8.decode(response.bodyBytes));
    }
    throw ApiException(response.statusCode, _errorMessage(response));
  }

  /// FastAPI returns `{"detail": "..."}`; validation errors return a list.
  String _errorMessage(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] != null) {
        final detail = decoded['detail'];
        if (detail is String) return detail;
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map && first['msg'] != null) return first['msg'].toString();
        }
        return detail.toString();
      }
    } catch (_) {
      // fall through to the raw body
    }
    if (response.statusCode == 403) return 'Your role does not allow this action.';
    if (response.statusCode == 429) return 'Too many requests — please wait a moment.';
    return 'Request failed (${response.statusCode}).';
  }

  Future<bool> _refresh() async {
    final token = await TokenStore.refreshToken();
    if (token == null) return false;
    try {
      final response = await _client
          .post(_uri('/refresh-token'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'refresh_token': token}))
          .timeout(AppConfig.requestTimeout);
      if (response.statusCode != 200) return false;
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final current = await TokenStore.user();
      await TokenStore.save(
        AuthTokens(
          accessToken: data['access_token'] as String,
          refreshToken: data['refresh_token'] as String? ?? token,
          role: current?.role ?? '',
        ),
        current ?? const SessionUser(id: 0, username: '', role: 'Patient'),
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  // -------------------------------------------------------------------------
  // Auth
  // -------------------------------------------------------------------------

  /// `/login` expects form encoding, not JSON.
  Future<AuthTokens> login(String username, String password) async {
    late http.Response response;
    try {
      response = await _client
          .post(
            _uri('/login'),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: {'username': username, 'password': password},
          )
          .timeout(AppConfig.requestTimeout);
    } catch (e) {
      throw ApiException(0, 'Cannot reach the hospital server.\n${AppConfig.apiLabel}\n$e');
    }
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, _errorMessage(response));
    }
    return AuthTokens.fromJson(jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>);
  }

  Future<SessionUser> me() async {
    final data = await _send('GET', '/users/me') as Map<String, dynamic>;
    return SessionUser.fromJson(data);
  }

  // -------------------------------------------------------------------------
  // Patient portal
  // -------------------------------------------------------------------------

  Future<PortalDashboard> dashboard() async {
    final data = await _send('GET', '/portal/dashboard') as Map<String, dynamic>;
    return PortalDashboard.fromJson(data);
  }

  Future<List<Appointment>> appointments() async {
    final data = await _send('GET', '/portal/appointments') as List;
    return data.map((a) => Appointment.fromJson(a as Map<String, dynamic>)).toList();
  }

  Future<List<Prescription>> prescriptions() async {
    final data = await _send('GET', '/portal/prescriptions') as List;
    return data.map((p) => Prescription.fromJson(p as Map<String, dynamic>)).toList();
  }

  Future<List<LabReport>> labReports() async {
    final data = await _send('GET', '/portal/lab-reports') as List;
    return data.map((r) => LabReport.fromJson(r as Map<String, dynamic>)).toList();
  }

  Future<List<LabOrderProgress>> labOrders() async {
    final data = await _send('GET', '/portal/lab-orders') as List;
    return data.map((o) => LabOrderProgress.fromJson(o as Map<String, dynamic>)).toList();
  }

  Future<List<PortalBill>> bills() async {
    final data = await _send('GET', '/portal/bills') as List;
    return data.map((b) => PortalBill.fromJson(b as Map<String, dynamic>)).toList();
  }

  Future<List<PortalDocument>> documents() async {
    final data = await _send('GET', '/portal/documents') as List;
    return data.map((d) => PortalDocument.fromJson(d as Map<String, dynamic>)).toList();
  }

  /// Doctors available for booking. The backend returns `name`, `department`,
  /// `specialization` and `consultation_fee`.
  Future<List<Map<String, dynamic>>> portalDoctors() async {
    final data = await _send('GET', '/portal/doctors') as List;
    return data.cast<Map<String, dynamic>>();
  }

  /// Slots still free for this doctor on this date.
  ///
  /// `/portal/slots` returns the full roster when called without filters and the
  /// genuinely available times when given both — matching what booking accepts.
  Future<List<String>> doctorSlots(int doctorId, String date) async {
    final data = await _send('GET', '/portal/slots', query: {
      'doctor_id': '$doctorId',
      'appointment_date': date,
    }) as List;
    return data.map((s) => s.toString()).toList();
  }

  Future<void> bookAppointment({
    required int doctorId,
    required String date,
    required String slot,
    String? reason,
  }) async {
    await _send('POST', '/portal/appointments', body: {
      'doctor_id': doctorId,
      'appointment_date': date,
      'time_slot': slot,
      'reason': reason,
    });
  }

  /// Cancelling someone else's appointment returns 404, never a leak.
  Future<void> cancelAppointment(int appointmentId) async {
    await _send('PUT', '/portal/appointments/$appointmentId/cancel');
  }

  // -------------------------------------------------------------------------
  // Ward (IPD)
  // -------------------------------------------------------------------------

  Future<IpdStats> ipdStats() async {
    final data = await _send('GET', '/ipd/stats') as Map<String, dynamic>;
    return IpdStats.fromJson(data);
  }

  Future<List<BedTile>> bedBoard({int? wardId, String? status}) async {
    final query = <String, String>{};
    if (wardId != null) query['ward_id'] = '$wardId';
    if (status != null) query['status'] = status;
    final data = await _send('GET', '/ipd/bed-board', query: query) as List;
    return data.map((b) => BedTile.fromJson(b as Map<String, dynamic>)).toList();
  }

  Future<List<Map<String, dynamic>>> currentAdmissions() async {
    final data = await _send('GET', '/ip-admissions/',
        query: {'current_only': 'true', 'limit': '200'}) as List;
    return data.cast<Map<String, dynamic>>();
  }

  Future<AdmissionDetail> admissionDetail(int admissionId) async {
    final data = await _send('GET', '/ip-admissions/$admissionId/detail') as Map<String, dynamic>;
    return AdmissionDetail.fromJson(data);
  }

  /// Blank fields must be omitted, never sent as 0 — that would chart a wrong value.
  Future<void> chartVitals(int admissionId, Map<String, dynamic> vitals) async {
    final clean = <String, dynamic>{};
    vitals.forEach((key, value) {
      if (value == null) return;
      if (value is String && value.trim().isEmpty) return;
      clean[key] = value is String ? num.tryParse(value) ?? value : value;
    });
    await _send('POST', '/ip-admissions/$admissionId/nursing-notes', body: clean);
  }

  Future<void> prescribe(
    int admissionId, {
    required String medicineName,
    String? dose,
    String route = 'Oral',
    String frequency = 'BD',
  }) async {
    await _send('POST', '/ip-admissions/$admissionId/medications', body: {
      'medicine_name': medicineName,
      if (dose != null && dose.isNotEmpty) 'dose': dose,
      'route': route,
      'frequency': frequency,
    });
  }

  Future<void> administer(int orderId, String status) async {
    await _send('POST', '/ipd/medications/$orderId/administer', body: {'status': status});
  }
}
