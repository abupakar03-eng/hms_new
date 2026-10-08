import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import '../patient/dashboard_tab.dart' show Loader;

/// The ward in your pocket: a live bed board plus the ability to chart vitals
/// and record medication from the bedside.
class WardScreen extends StatefulWidget {
  const WardScreen({super.key, required this.client, required this.user});
  final ApiClient client;
  final SessionUser user;

  @override
  State<WardScreen> createState() => _WardScreenState();
}

class _WardScreenState extends State<WardScreen> {
  late Future<_WardData> _future;
  String _filter = 'All';

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_WardData> _load() async {
    final results = await Future.wait([
      widget.client.bedBoard(),
      widget.client.ipdStats(),
      widget.client.currentAdmissions(),
    ]);
    return _WardData(
      beds: results[0] as List<BedTile>,
      stats: results[1] as IpdStats,
      admissions: results[2] as List<Map<String, dynamic>>,
    );
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: Loader<_WardData>(
        future: _future,
        onRetry: _reload,
        emptyIcon: Icons.bed_outlined,
        emptyTitle: 'No beds configured',
        emptyMessage: 'An administrator must add wards, rooms and beds first.',
        isEmpty: (data) => data.beds.isEmpty,
        builder: (context, data) {
          final visible = _filter == 'All'
              ? data.beds
              : data.beds.where((b) => b.status == _filter).toList();
          final wards = <String, List<BedTile>>{};
          for (final bed in visible) {
            wards.putIfAbsent(bed.wardName ?? 'Unassigned', () => []).add(bed);
          }
          return ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Row(
                  children: [
                    _Metric('Beds', '${data.stats.totalBeds}', AppTheme.primary),
                    _Metric('Free', '${data.stats.availableBeds}', AppTheme.success),
                    _Metric('Occupied', '${data.stats.occupiedBeds}', AppTheme.warning),
                    _Metric('Occupancy', '${data.stats.occupancyPercent}%',
                        const Color(0xFF8B5CF6)),
                  ],
                ),
              ),
              if (data.stats.criticalPatients > 0)
                Card(
                  color: AppTheme.danger.withValues(alpha: 0.06),
                  child: ListTile(
                    leading: const Icon(Icons.monitor_heart, color: AppTheme.danger),
                    title: Text(
                      '${data.stats.criticalPatients} patient(s) with critical vitals in the last 24h',
                      style: const TextStyle(
                          fontWeight: FontWeight.w600, color: AppTheme.danger, fontSize: 13),
                    ),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: ['All', 'Available', 'Occupied', 'Cleaning', 'Maintenance']
                        .map((status) => Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(status),
                                selected: _filter == status,
                                onSelected: (_) => setState(() => _filter = status),
                              ),
                            ))
                        .toList(),
                  ),
                ),
              ),
              ...wards.entries.map((entry) => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
                        child: Text(
                          '${entry.key} · ${entry.value.where((b) => b.isAvailable).length}/${entry.value.length} free',
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                        ),
                      ),
                      ...entry.value.map((bed) => _BedCard(
                            bed: bed,
                            onOpen: bed.admissionId == null
                                ? null
                                : () => _openAdmission(bed.admissionId!),
                          )),
                    ],
                  )),
              if (data.admissions.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(20),
                  child: Center(
                    child: Text('No patients are admitted right now.',
                        style: TextStyle(color: Colors.black54)),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _openAdmission(int admissionId) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AdmissionScreen(client: widget.client, admissionId: admissionId),
      ),
    );
    _reload();
  }
}

class _WardData {
  const _WardData({required this.beds, required this.stats, required this.admissions});
  final List<BedTile> beds;
  final IpdStats stats;
  final List<Map<String, dynamic>> admissions;
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value, this.color);
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          children: [
            Text(value,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: const TextStyle(fontSize: 10, color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}

class _BedCard extends StatelessWidget {
  const _BedCard({required this.bed, this.onOpen});
  final BedTile bed;
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(bed.status);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 4,
              height: 54,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(bed.bedCode,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(width: 8),
                      StatusChip(bed.status, compact: true),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text('${bed.wardName ?? ''} · Room ${bed.roomNumber ?? '—'}',
                      style: const TextStyle(fontSize: 11, color: Colors.black54)),
                  if (bed.isOccupied && bed.patientName != null) ...[
                    const SizedBox(height: 6),
                    Text(bed.patientName!,
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    if (bed.attendingDoctor != null)
                      Text(bed.attendingDoctor!,
                          style: const TextStyle(fontSize: 11, color: Colors.black45)),
                  ],
                ],
              ),
            ),
            if (onOpen != null)
              TextButton(
                onPressed: onOpen,
                child: const Text('Open', style: TextStyle(fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }
}

/// A single admission: vitals history, charting form and medication list.
class AdmissionScreen extends StatefulWidget {
  const AdmissionScreen({super.key, required this.client, required this.admissionId});
  final ApiClient client;
  final int admissionId;

  @override
  State<AdmissionScreen> createState() => _AdmissionScreenState();
}

class _AdmissionScreenState extends State<AdmissionScreen> {
  AdmissionDetail? _detail;
  String? _error;
  bool _busy = false;

  final _temperature = TextEditingController();
  final _pulse = TextEditingController();
  final _systolic = TextEditingController();
  final _diastolic = TextEditingController();
  final _spo2 = TextEditingController();
  String _shift = 'Morning';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_temperature, _pulse, _systolic, _diastolic, _spo2]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final detail = await widget.client.admissionDetail(widget.admissionId);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _chart() async {
    setState(() => _busy = true);
    try {
      await widget.client.chartVitals(widget.admissionId, {
        'shift': _shift,
        'temperature': _temperature.text,
        'pulse': _pulse.text,
        'bp_systolic': _systolic.text,
        'bp_diastolic': _diastolic.text,
        'spo2': _spo2.text,
      });
      for (final c in [_temperature, _pulse, _systolic, _diastolic, _spo2]) {
        c.clear();
      }
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Vitals recorded')));
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message), backgroundColor: AppTheme.danger));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _administer(MedicationOrder order, String status) async {
    try {
      await widget.client.administer(order.id, status);
      await _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      appBar: AppBar(title: Text(detail?.patientName ?? 'Ward record')),
      body: detail == null
          ? _error != null
              ? StateView(
                  icon: Icons.cloud_off,
                  title: 'Could not load the record',
                  message: _error,
                  action: FilledButton(onPressed: _load, child: const Text('Retry')),
                )
              : const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(detail.patientName ?? '—',
                                  style: const TextStyle(
                                      fontSize: 16, fontWeight: FontWeight.bold)),
                            ),
                            StatusChip(detail.status, compact: true),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '${detail.patientAge ?? '—'}y ${detail.patientGender ?? ''} · '
                          'Bed ${detail.bedCode ?? '—'} · ${detail.wardNumber ?? ''} ${detail.roomNumber ?? ''}',
                          style: const TextStyle(fontSize: 12, color: Colors.black54),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Admitted ${prettyDateTime(detail.admissionDate)} · '
                          'Day ${detail.lengthOfStayDays} · ${detail.admissionType}',
                          style: const TextStyle(fontSize: 12, color: Colors.black54),
                        ),
                        if (detail.reasonForAdmission != null &&
                            detail.reasonForAdmission!.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text('Reason: ${detail.reasonForAdmission}',
                              style: const TextStyle(fontSize: 12)),
                        ],
                      ],
                    ),
                  ),
                ),
                if (detail.isAdmitted) ...[
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Chart vitals',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                          const SizedBox(height: 10),
                          DropdownButtonFormField<String>(
                            initialValue: _shift,
                            decoration: const InputDecoration(labelText: 'Shift'),
                            items: const ['Morning', 'Evening', 'Night']
                                .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                                .toList(),
                            onChanged: (v) => setState(() => _shift = v ?? 'Morning'),
                          ),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              _NumberField(_temperature, 'Temp °C'),
                              const SizedBox(width: 10),
                              _NumberField(_pulse, 'Pulse'),
                            ],
                          ),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              _NumberField(_systolic, 'BP sys'),
                              const SizedBox(width: 10),
                              _NumberField(_diastolic, 'BP dia'),
                            ],
                          ),
                          const SizedBox(height: 10),
                          _NumberField(_spo2, 'SpO₂ %'),
                          const SizedBox(height: 14),
                          FilledButton.icon(
                            onPressed: _busy ? null : _chart,
                            icon: const Icon(Icons.save_outlined, size: 18),
                            label: const Text('Save vitals'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (detail.medicationOrders.isNotEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Medication',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                            const SizedBox(height: 6),
                            ...detail.medicationOrders.map(
                              (order) => Padding(
                                padding: const EdgeInsets.symmetric(vertical: 6),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Expanded(
                                          child: Text(
                                            '${order.medicineName}'
                                            '${order.dose != null ? ' · ${order.dose}' : ''}',
                                            style: const TextStyle(
                                                fontWeight: FontWeight.w600, fontSize: 13),
                                          ),
                                        ),
                                        StatusChip(order.status, compact: true),
                                      ],
                                    ),
                                    Text(
                                      '${order.route ?? ''} · ${order.frequency ?? ''}',
                                      style: const TextStyle(fontSize: 11, color: Colors.black45),
                                    ),
                                    if (order.isActive)
                                      Row(
                                        children: [
                                          _MiniButton('Given', () => _administer(order, 'Given')),
                                          _MiniButton('Held', () => _administer(order, 'Held')),
                                          _MiniButton('Refused', () => _administer(order, 'Refused')),
                                        ],
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Vitals history',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                        const SizedBox(height: 8),
                        if (detail.nursingNotes.isEmpty)
                          const Text('No vitals charted yet.',
                              style: TextStyle(fontSize: 12, color: Colors.black54))
                        else
                          ...detail.nursingNotes.map(
                            (note) => Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: note.isCritical
                                    ? AppTheme.danger.withValues(alpha: 0.07)
                                    : Colors.transparent,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: note.isCritical
                                      ? AppTheme.danger.withValues(alpha: 0.35)
                                      : AppTheme.border,
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          '${prettyDateTime(note.recordedAt)} · ${note.shift}',
                                          style: const TextStyle(
                                              fontSize: 11, color: Colors.black54),
                                        ),
                                      ),
                                      if (note.isCritical)
                                        const Icon(Icons.warning_amber_rounded,
                                            size: 16, color: AppTheme.danger),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    [
                                      if (note.temperature != null) 'Temp ${note.temperature}°C',
                                      if (note.pulse != null) 'Pulse ${note.pulse}',
                                      'BP ${note.bp}',
                                      if (note.spo2 != null) 'SpO₂ ${note.spo2}%',
                                    ].join('  ·  '),
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: note.isCritical
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                    ),
                                  ),
                                  if (note.recordedBy != null)
                                    Text('by ${note.recordedBy}',
                                        style: const TextStyle(
                                            fontSize: 10, color: Colors.black38)),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField(this.controller, this.label);
  final TextEditingController controller;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: TextField(
        controller: controller,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(labelText: label),
      ),
    );
  }
}

class _MiniButton extends StatelessWidget {
  const _MiniButton(this.label, this.onTap);
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8, top: 6),
      child: OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
          minimumSize: const Size(0, 30),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        child: Text(label, style: const TextStyle(fontSize: 11)),
      ),
    );
  }
}
