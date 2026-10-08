import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/models.dart';
import 'core/theme.dart';
import 'features/auth/login_screen.dart';
import 'features/patient/appointments_tab.dart';
import 'features/patient/dashboard_tab.dart';
import 'features/patient/records_tab.dart';
import 'features/staff/ward_screen.dart';

void main() => runApp(const HospitalApp());

class HospitalApp extends StatelessWidget {
  const HospitalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MedBill Pro',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const _Boot(),
    );
  }
}

/// Restores a stored session before deciding between sign-in and the app.
class _Boot extends StatefulWidget {
  const _Boot();

  @override
  State<_Boot> createState() => _BootState();
}

class _BootState extends State<_Boot> {
  final ApiClient _client = ApiClient();
  late Future<SessionUser?> _session;

  @override
  void initState() {
    super.initState();
    _session = _restore();
  }

  Future<SessionUser?> _restore() async {
    final token = await TokenStore.accessToken();
    if (token == null) return null;
    try {
      // Validate the stored token against the server rather than trusting it.
      return await _client.me();
    } catch (_) {
      await TokenStore.clear();
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SessionUser?>(
      future: _session,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        final user = snapshot.data;
        if (user == null) {
          return LoginScreen(
            client: _client,
            onSignedIn: (signedIn) =>
                setState(() => _session = Future.value(signedIn)),
          );
        }
        return HomeShell(client: _client, user: user);
      },
    );
  }
}

/// Role-aware shell.
///
/// Patients get their own portal; clinical staff get the ward. The backend
/// enforces authorisation regardless of what the app chooses to show.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.client, required this.user});
  final ApiClient client;
  final SessionUser user;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  bool get _isPatient => widget.user.isPatient;

  List<Widget> get _screens => _isPatient
      ? [
          PatientDashboardTab(client: widget.client, user: widget.user),
          AppointmentsTab(client: widget.client),
          RecordsTab(client: widget.client),
        ]
      : [
          WardScreen(client: widget.client, user: widget.user),
          AppointmentsTab(client: widget.client),
        ];

  Future<void> _signOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Stay')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Sign out')),
        ],
      ),
    );
    if (confirmed != true) return;
    await TokenStore.clear();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => LoginScreen(
          client: widget.client,
          onSignedIn: (_) {},
        ),
      ),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final screens = _screens;
    final titles = _isPatient
        ? const ['My health', 'Appointments', 'My records']
        : const ['Ward', 'Appointments'];
    final index = _index.clamp(0, screens.length - 1);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(titles[index], style: const TextStyle(fontSize: 17)),
            Text(
              '${widget.user.fullName ?? widget.user.username} · ${widget.user.role}',
              style: const TextStyle(fontSize: 11, color: Colors.white70),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: _signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: IndexedStack(index: index, children: screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: _isPatient
            ? const [
                NavigationDestination(
                    icon: Icon(Icons.dashboard_outlined),
                    selectedIcon: Icon(Icons.dashboard),
                    label: 'Health'),
                NavigationDestination(
                    icon: Icon(Icons.event_outlined),
                    selectedIcon: Icon(Icons.event),
                    label: 'Visits'),
                NavigationDestination(
                    icon: Icon(Icons.folder_outlined),
                    selectedIcon: Icon(Icons.folder),
                    label: 'Records'),
              ]
            : const [
                NavigationDestination(
                    icon: Icon(Icons.bed_outlined),
                    selectedIcon: Icon(Icons.bed),
                    label: 'Ward'),
                NavigationDestination(
                    icon: Icon(Icons.event_outlined),
                    selectedIcon: Icon(Icons.event),
                    label: 'Visits'),
              ],
      ),
    );
  }
}
