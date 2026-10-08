/// Live integration test for the mobile client against a running backend.
///
/// Unlike the unit tests, this exercises the real `ApiClient` — HTTP, JWT
/// handling, error mapping and model parsing — against the actual FastAPI
/// server, so a backend contract change cannot slip past the app.
///
/// Requires the backend to be running:
///   ./run_app.ps1 -NoBuild          (serves http://127.0.0.1:8000)
///   flutter test test/live_api_test.dart
library;

import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:hospital_mobile/core/api_client.dart';
import 'package:hospital_mobile/core/models.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const _base = 'http://127.0.0.1:8000';

Future<bool> _serverUp() async {
  try {
    final response = await http
        .get(Uri.parse('$_base/health'))
        .timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  } catch (_) {
    return false;
  }
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    // flutter_test installs a mock HttpClient that returns 400 for every
    // request. Clearing it lets these tests reach the real server.
    HttpOverrides.global = null;
    SharedPreferences.setMockInitialValues({});
  });

  // A short unique suffix keeps repeated runs from colliding on username.
  final suffix = '${DateTime.now().millisecondsSinceEpoch % 1000000}'
      '${Random().nextInt(90) + 10}';
  final patientUsername = 'mob$suffix';
  const patientPassword = 'Mobile@Pass1';
  const adminPassword = 'admin123';

  late bool available;

  setUpAll(() async {
    available = await _serverUp();
    if (!available) {
      throw StateError(
        'Backend is not reachable at $_base.\n'
        'Start it with: ./run_app.ps1 -NoBuild',
      );
    }
  });

  group('live: authentication', () {
    test('rejects a wrong password without leaking details', () async {
      final client = ApiClient();
      await expectLater(
        client.login('admin', 'definitely-not-the-password'),
        throwsA(isA<ApiException>().having((e) => e.isAuthError || e.statusCode == 400 ||
            e.statusCode == 401 || e.statusCode == 429, 'auth-ish error', isTrue)),
      );
    });

    test('signs in and resolves the current user', () async {
      final client = ApiClient();
      final tokens = await client.login('admin', adminPassword);
      expect(tokens.accessToken, isNotEmpty);
      expect(tokens.role, 'Admin');

      await TokenStore.save(tokens, SessionUser(id: 0, username: 'admin', role: tokens.role));

      final user = await client.me();
      expect(user.username, 'admin');
      expect(user.role, 'Admin');
      expect(user.isPatient, isFalse);
      expect(user.isWardStaff, isTrue);
    });
  });

  group('live: patient portal', () {
    late ApiClient patientClient;

    setUpAll(() async {
      // Register a fresh portal account so the test owns its credentials.
      final response = await http.post(
        Uri.parse('$_base/portal/register'),
        headers: {'Content-Type': 'application/json'},
        body: '{"username":"$patientUsername","password":"$patientPassword",'
            '"name":"Mobile Test $suffix","age":34,"gender":"Male",'
            '"phone":"9${suffix.padLeft(9, '0').substring(0, 9)}"}',
      );
      expect(response.statusCode, 200, reason: 'portal registration failed: ${response.body}');

      patientClient = ApiClient();
      final tokens = await patientClient.login(patientUsername, patientPassword);
      expect(tokens.role, 'Patient');
      await TokenStore.save(
        tokens,
        SessionUser(id: 0, username: patientUsername, role: tokens.role),
      );
      final user = await patientClient.me();
      expect(user.isPatient, isTrue);
      expect(user.patientId, isNotNull, reason: 'portal accounts must link to a patient');
      await TokenStore.save(tokens, user);
    });

    test('dashboard parses into the model', () async {
      final dashboard = await patientClient.dashboard();
      expect(dashboard.profile.name, contains('Mobile Test'));
      expect(dashboard.profile.age, 34);
      expect(dashboard.upcomingAppointments, greaterThanOrEqualTo(0));
      expect(dashboard.totalBilled, greaterThanOrEqualTo(0));
    });

    test('appointments list parses', () async {
      final appointments = await patientClient.appointments();
      expect(appointments, isA<List<Appointment>>());
    });

    test('prescriptions, reports, bills and documents all parse', () async {
      expect(await patientClient.prescriptions(), isA<List<Prescription>>());
      expect(await patientClient.labReports(), isA<List<LabReport>>());
      expect(await patientClient.bills(), isA<List<PortalBill>>());
      expect(await patientClient.documents(), isA<List<PortalDocument>>());
    });

    test('books an appointment and then cancels it', () async {
      final doctors = await patientClient.portalDoctors();
      if (doctors.isEmpty) {
        markTestSkipped('No doctors are configured for booking.');
        return;
      }
      final doctorId = doctors.first['id'] as int;

      // Find the first day over the next fortnight that has free slots.
      String? bookedDate;
      String? bookedSlot;
      for (var offset = 0; offset < 14 && bookedSlot == null; offset++) {
        final day = DateTime.now().add(Duration(days: offset));
        final param = '${day.year}-${day.month.toString().padLeft(2, '0')}'
            '-${day.day.toString().padLeft(2, '0')}';
        final slots = await patientClient.doctorSlots(doctorId, param);
        if (slots.isNotEmpty) {
          bookedDate = param;
          bookedSlot = slots.first;
        }
      }
      if (bookedSlot == null) {
        markTestSkipped('No free slots in the next two weeks.');
        return;
      }

      await patientClient.bookAppointment(
        doctorId: doctorId,
        date: bookedDate!,
        slot: bookedSlot,
        reason: 'Mobile integration test',
      );

      final after = await patientClient.appointments();
      final created = after.where(
        (a) => a.appointmentDate.startsWith(bookedDate!) && a.timeSlot == bookedSlot,
      );
      expect(created, isNotEmpty, reason: 'the booked appointment should be listed');
      final appointment = created.first;
      expect(appointment.isActive, isTrue);

      await patientClient.cancelAppointment(appointment.id);
      final finalList = await patientClient.appointments();
      final cancelled = finalList.firstWhere((a) => a.id == appointment.id);
      expect(cancelled.status, 'Cancelled');
    });

    test('a patient token cannot reach the staff API', () async {
      // The bed board is staff-only; the app must surface the refusal, not data.
      await expectLater(
        patientClient.bedBoard(),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 403)),
      );
    });
  });

  group('live: ward (staff)', () {
    test('bed board and stats parse for an admin', () async {
      final client = ApiClient();
      final tokens = await client.login('admin', adminPassword);
      await TokenStore.save(tokens, const SessionUser(id: 0, username: 'admin', role: 'Admin'));

      final beds = await client.bedBoard();
      expect(beds, isA<List<BedTile>>());
      expect(beds, isNotEmpty, reason: 'the live database has beds configured');

      final stats = await client.ipdStats();
      expect(stats.totalBeds, greaterThan(0));
      expect(stats.availableBeds + stats.occupiedBeds, lessThanOrEqualTo(stats.totalBeds));
      expect(stats.occupancyPercent, inInclusiveRange(0, 100));
    });

    test('occupancy is consistent with the individual bed statuses', () async {
      final client = ApiClient();
      final tokens = await client.login('admin', adminPassword);
      await TokenStore.save(tokens, const SessionUser(id: 0, username: 'admin', role: 'Admin'));

      final beds = await client.bedBoard();
      final stats = await client.ipdStats();

      final occupied = beds.where((b) => b.isOccupied).length;
      expect(occupied, stats.occupiedBeds,
          reason: 'the board and the summary must agree on occupancy');
      expect(beds.where((b) => b.isAvailable).length, stats.availableBeds);
    });

    test('status filtering is applied by the server', () async {
      final client = ApiClient();
      final tokens = await client.login('admin', adminPassword);
      await TokenStore.save(tokens, const SessionUser(id: 0, username: 'admin', role: 'Admin'));

      final available = await client.bedBoard(status: 'Available');
      expect(available.every((b) => b.status == 'Available'), isTrue);
    });

    test('an admitted patient exposes a full ward record', () async {
      final client = ApiClient();
      final tokens = await client.login('admin', adminPassword);
      await TokenStore.save(tokens, const SessionUser(id: 0, username: 'admin', role: 'Admin'));

      final admissions = await client.currentAdmissions();
      if (admissions.isEmpty) {
        markTestSkipped('No patient is currently admitted.');
        return;
      }
      final detail = await client.admissionDetail(admissions.first['id'] as int);
      expect(detail.patientName, isNotNull);
      expect(detail.isAdmitted, isTrue);
      expect(detail.bedCode, isNotNull);
      expect(detail.lengthOfStayDays, greaterThanOrEqualTo(0));
      // Every charted note must expose a usable display value.
      for (final note in detail.nursingNotes) {
        expect(note.bp, isNotEmpty);
      }
    });
  });
}
