import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/theme.dart';

/// Small helper so every tab gets the same load → empty → error → data cycle.
class Loader<T> extends StatelessWidget {
  const Loader({
    super.key,
    required this.future,
    required this.builder,
    required this.emptyIcon,
    required this.emptyTitle,
    this.emptyMessage,
    this.isEmpty,
    this.onRetry,
  });

  final Future<T> future;
  final Widget Function(BuildContext, T) builder;
  final IconData emptyIcon;
  final String emptyTitle;
  final String? emptyMessage;
  final bool Function(T)? isEmpty;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          final message = error is ApiException ? error.message : '$error';
          return StateView(
            icon: Icons.cloud_off,
            title: 'Could not load',
            message: message,
            action: onRetry == null
                ? null
                : FilledButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Try again'),
                  ),
          );
        }
        final data = snapshot.data as T;
        if (isEmpty != null && isEmpty!(data)) {
          return StateView(icon: emptyIcon, title: emptyTitle, message: emptyMessage);
        }
        return builder(context, data);
      },
    );
  }
}

/// The patient's home: a summary of everything waiting on them.
class PatientDashboardTab extends StatefulWidget {
  const PatientDashboardTab({super.key, required this.client, required this.user});
  final ApiClient client;
  final SessionUser user;

  @override
  State<PatientDashboardTab> createState() => _PatientDashboardTabState();
}

class _PatientDashboardTabState extends State<PatientDashboardTab> {
  late Future<PortalDashboard> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.client.dashboard();
  }

  void _reload() => setState(() => _future = widget.client.dashboard());

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: Loader<PortalDashboard>(
        future: _future,
        onRetry: _reload,
        emptyIcon: Icons.inbox,
        emptyTitle: 'Nothing to show yet',
        builder: (context, data) {
          final profile = data.profile;
          return ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 26,
                        backgroundColor: AppTheme.primary.withValues(alpha: 0.12),
                        child: Text(
                          profile.name.isNotEmpty ? profile.name[0].toUpperCase() : '?',
                          style: const TextStyle(
                              fontSize: 22, fontWeight: FontWeight.bold, color: AppTheme.primary),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(profile.name,
                                style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 3),
                            Text(
                              'UHID P${profile.id.toString().padLeft(6, '0')} · ${profile.age}y ${profile.gender}',
                              style: const TextStyle(fontSize: 12, color: Colors.black54),
                            ),
                            if (profile.bloodGroup != null && profile.bloodGroup!.isNotEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text('Blood group ${profile.bloodGroup}',
                                    style: const TextStyle(fontSize: 12, color: Colors.black54)),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (data.abnormalReports > 0)
                Card(
                  color: AppTheme.danger.withValues(alpha: 0.06),
                  child: ListTile(
                    leading: const Icon(Icons.warning_amber_rounded, color: AppTheme.danger),
                    title: Text(
                      '${data.abnormalReports} report${data.abnormalReports == 1 ? '' : 's'} need attention',
                      style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.danger),
                    ),
                    subtitle: const Text('A result is outside the reference range'),
                  ),
                ),
              if (data.nextAppointment != null)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.event_available, color: AppTheme.primary),
                    title: Text('Next appointment — ${data.nextAppointment!.doctorName ?? 'Doctor'}'),
                    subtitle: Text(
                        '${prettyDate(data.nextAppointment!.appointmentDate)}'
                        '${data.nextAppointment!.timeSlot != null ? ' at ${data.nextAppointment!.timeSlot}' : ''}'),
                    trailing: const StatusChip('Booked'),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
                child: Row(
                  children: [
                    _StatBox(
                        label: 'Appointments',
                        value: '${data.upcomingAppointments}',
                        icon: Icons.event,
                        color: AppTheme.primary),
                    const SizedBox(width: 10),
                    _StatBox(
                        label: 'Tests pending',
                        value: '${data.pendingLabTests}',
                        icon: Icons.hourglass_bottom,
                        color: AppTheme.warning),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 6),
                child: Row(
                  children: [
                    _StatBox(
                        label: 'Reports ready',
                        value: '${data.readyReports}',
                        icon: Icons.description,
                        color: AppTheme.success),
                    const SizedBox(width: 10),
                    _StatBox(
                        label: 'Total billed',
                        value: rupees(data.totalBilled),
                        icon: Icons.receipt_long,
                        color: const Color(0xFF8B5CF6)),
                  ],
                ),
              ),
              if (data.recentLabOrders.isNotEmpty) ...[
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 14, 16, 4),
                  child: Text('Recent tests',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                ),
                ...data.recentLabOrders.take(4).map(
                      (order) => Card(
                        child: ListTile(
                          dense: true,
                          title: Text(order.testName,
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Text(prettyDate(order.orderDate)),
                          trailing: StatusChip(
                            order.reportReady ? 'Ready' : order.status,
                            compact: true,
                          ),
                        ),
                      ),
                    ),
              ],
              if (profile.phone != null && profile.phone!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                  child: Row(
                    children: [
                      const Icon(Icons.phone_outlined, size: 15, color: Colors.black38),
                      const SizedBox(width: 6),
                      Text(profile.phone!,
                          style: const TextStyle(fontSize: 12, color: Colors.black45)),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StatBox extends StatelessWidget {
  const _StatBox({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 8),
            Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text(label, style: const TextStyle(fontSize: 11, color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}
