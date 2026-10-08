import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import 'dashboard_tab.dart' show Loader;

/// Appointments: list the patient's own bookings and make a new one.
class AppointmentsTab extends StatefulWidget {
  const AppointmentsTab({super.key, required this.client});
  final ApiClient client;

  @override
  State<AppointmentsTab> createState() => _AppointmentsTabState();
}

class _AppointmentsTabState extends State<AppointmentsTab> {
  late Future<List<Appointment>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.client.appointments();
  }

  void _reload() => setState(() => _future = widget.client.appointments());

  Future<void> _cancel(Appointment appointment) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel appointment?'),
        content: Text(
            '${appointment.doctorName ?? 'This appointment'} on ${prettyDate(appointment.appointmentDate)} will be cancelled.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            child: const Text('Cancel it'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.client.cancelAppointment(appointment.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Appointment cancelled')),
      );
      _reload();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _book() async {
    final booked = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => _BookAppointmentSheet(client: widget.client)),
    );
    if (booked == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _book,
        backgroundColor: AppTheme.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('Book'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => _reload(),
        child: Loader<List<Appointment>>(
          future: _future,
          onRetry: _reload,
          isEmpty: (list) => list.isEmpty,
          emptyIcon: Icons.event_busy,
          emptyTitle: 'No appointments yet',
          emptyMessage: 'Tap Book to schedule a consultation.',
          builder: (context, list) => ListView.builder(
            padding: const EdgeInsets.only(top: 8, bottom: 90),
            itemCount: list.length,
            itemBuilder: (context, index) {
              final appointment = list[index];
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              appointment.doctorName ?? 'Doctor',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                            ),
                          ),
                          StatusChip(appointment.status, compact: true),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Icon(Icons.calendar_today, size: 14, color: Colors.black45),
                          const SizedBox(width: 6),
                          Text(prettyDate(appointment.appointmentDate),
                              style: const TextStyle(fontSize: 13)),
                          if (appointment.timeSlot != null) ...[
                            const SizedBox(width: 14),
                            const Icon(Icons.schedule, size: 14, color: Colors.black45),
                            const SizedBox(width: 6),
                            Text(appointment.timeSlot!, style: const TextStyle(fontSize: 13)),
                          ],
                        ],
                      ),
                      if (appointment.reason != null && appointment.reason!.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(appointment.reason!,
                            style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      ],
                      if (appointment.isActive) ...[
                        const SizedBox(height: 6),
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton.icon(
                            onPressed: () => _cancel(appointment),
                            icon: const Icon(Icons.close, size: 16),
                            label: const Text('Cancel'),
                            style: TextButton.styleFrom(foregroundColor: AppTheme.danger),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Two-step booking: pick a doctor and a date, then choose from the slots the
/// server says are actually free.
class _BookAppointmentSheet extends StatefulWidget {
  const _BookAppointmentSheet({required this.client});
  final ApiClient client;

  @override
  State<_BookAppointmentSheet> createState() => _BookAppointmentSheetState();
}

class _BookAppointmentSheetState extends State<_BookAppointmentSheet> {
  List<Map<String, dynamic>>? _doctors;
  String? _error;
  Map<String, dynamic>? _selectedDoctor;
  DateTime _date = DateTime.now();
  List<String> _slots = [];
  bool _loadingSlots = false;
  String? _selectedSlot;
  bool _booking = false;

  @override
  void initState() {
    super.initState();
    _loadDoctors();
  }

  Future<void> _loadDoctors() async {
    setState(() => _error = null);
    try {
      final doctors = await widget.client.portalDoctors();
      if (!mounted) return;
      setState(() => _doctors = doctors);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  String get _dateParam =>
      '${_date.year}-${_date.month.toString().padLeft(2, '0')}-${_date.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 90)),
    );
    if (picked == null) return;
    setState(() {
      _date = picked;
      _selectedSlot = null;
      _slots = [];
    });
    await _loadSlots();
  }

  Future<void> _loadSlots() async {
    final doctor = _selectedDoctor;
    if (doctor == null) return;
    setState(() {
      _loadingSlots = true;
      _error = null;
    });
    try {
      final slots = await widget.client.doctorSlots(doctor['id'] as int, _dateParam);
      if (!mounted) return;
      setState(() => _slots = slots);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _slots = [];
      });
    } finally {
      if (mounted) setState(() => _loadingSlots = false);
    }
  }

  Future<void> _confirm() async {
    final doctor = _selectedDoctor;
    // Capture into locals: null-promotion does not apply to instance fields.
    final slot = _selectedSlot;
    if (doctor == null || slot == null) return;
    setState(() => _booking = true);
    try {
      await widget.client.bookAppointment(
        doctorId: doctor['id'] as int,
        date: _dateParam,
        slot: slot,
      );
      if (!mounted) return;
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _booking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Book an appointment')),
      body: _doctors == null && _error == null
          ? const Center(child: CircularProgressIndicator())
          : _doctors == null
              ? StateView(
                  icon: Icons.cloud_off,
                  title: 'Could not load doctors',
                  message: _error,
                  action: FilledButton(onPressed: _loadDoctors, child: const Text('Retry')),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    const Text('Choose a doctor',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 8),
                    if (_doctors!.isEmpty)
                      const Text('No doctors are available for booking right now.',
                          style: TextStyle(color: Colors.black54, fontSize: 13)),
                    ..._doctors!.map((doctor) {
                      final selected = _selectedDoctor?['id'] == doctor['id'];
                      return Card(
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(
                            color: selected ? AppTheme.primary : AppTheme.border,
                            width: selected ? 2 : 1,
                          ),
                        ),
                        child: ListTile(
                          onTap: () {
                            setState(() {
                              _selectedDoctor = doctor;
                              _slots = [];
                              _selectedSlot = null;
                            });
                            _loadSlots();
                          },
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.primary.withValues(alpha: 0.12),
                            child: const Icon(Icons.medical_services, color: AppTheme.primary, size: 20),
                          ),
                          title: Text((doctor['name'] ?? doctor['username'] ?? 'Doctor') as String,
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                          subtitle: Text(
                            [
                              if ((doctor['specialization'] ?? '') != '') doctor['specialization'],
                              if ((doctor['department'] ?? '') != '') doctor['department'],
                              if (doctor['consultation_fee'] != null)
                                'Fee ${rupees((doctor['consultation_fee'] as num))}',
                            ].join(' · '),
                            style: const TextStyle(fontSize: 12),
                          ),
                          trailing: selected
                              ? const Icon(Icons.check_circle, color: AppTheme.primary)
                              : null,
                        ),
                      );
                    }),
                    if (_selectedDoctor != null) ...[
                      const SizedBox(height: 20),
                      const Text('Pick a date',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                      const SizedBox(height: 8),
                      OutlinedButton.icon(
                        onPressed: _pickDate,
                        icon: const Icon(Icons.calendar_month, size: 18),
                        label: Text(prettyDate(_dateParam)),
                        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(46)),
                      ),
                      const SizedBox(height: 18),
                      const Text('Available slots',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                      const SizedBox(height: 8),
                      if (_loadingSlots)
                        const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else if (_slots.isEmpty)
                        const Text('No free slots on this date. Try another day.',
                            style: TextStyle(color: Colors.black54, fontSize: 13))
                      else
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _slots.map((slot) {
                            final selected = _selectedSlot == slot;
                            return ChoiceChip(
                              label: Text(slot),
                              selected: selected,
                              onSelected: (_) => setState(() => _selectedSlot = slot),
                            );
                          }).toList(),
                        ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 16),
                      Text(_error!, style: const TextStyle(color: AppTheme.danger, fontSize: 13)),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: (_selectedDoctor == null || _selectedSlot == null || _booking)
                          ? null
                          : _confirm,
                      child: _booking
                          ? const SizedBox(
                              width: 20, height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Confirm booking'),
                    ),
                  ],
                ),
    );
  }
}
