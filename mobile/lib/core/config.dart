import 'dart:io' show Platform;

/// Runtime configuration.
///
/// The API host differs by platform: an Android emulator reaches the host
/// machine at 10.0.2.2, while iOS simulators and desktop use loopback.
/// Override at build time for a real deployment:
///
///   flutter run --dart-define=API_BASE=https://hms.example.org
class AppConfig {
  static const String _override = String.fromEnvironment('API_BASE');

  static String get apiBase {
    if (_override.isNotEmpty) return _override;
    if (Platform.isAndroid) return 'http://10.0.2.2:8000';
    return 'http://127.0.0.1:8000';
  }

  /// Shown on the login screen so a tester can see which backend is in use.
  static String get apiLabel => apiBase.replaceFirst(RegExp(r'^https?://'), '');

  static const Duration requestTimeout = Duration(seconds: 20);
}
