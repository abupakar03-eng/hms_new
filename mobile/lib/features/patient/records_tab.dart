import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import 'dashboard_tab.dart' show Loader;

/// The patient's own clinical and financial record, grouped into sub-tabs.
class RecordsTab extends StatelessWidget {
  const RecordsTab({super.key, required this.client});
  final ApiClient client;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          automaticallyImplyLeading: false,
          title: const Text('My records'),
          bottom: const TabBar(
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white70,
            indicatorColor: Colors.white,
            tabs: [
              Tab(text: 'Rx', icon: Icon(Icons.medication_outlined, size: 18)),
              Tab(text: 'Reports', icon: Icon(Icons.science_outlined, size: 18)),
              Tab(text: 'Bills', icon: Icon(Icons.receipt_long_outlined, size: 18)),
              Tab(text: 'Docs', icon: Icon(Icons.folder_outlined, size: 18)),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _PrescriptionsTab(client: client),
            _LabReportsTab(client: client),
            _BillsTab(client: client),
            _DocumentsTab(client: client),
          ],
        ),
      ),
    );
  }
}

class _PrescriptionsTab extends StatefulWidget {
  const _PrescriptionsTab({required this.client});
  final ApiClient client;

  @override
  State<_PrescriptionsTab> createState() => _PrescriptionsTabState();
}

class _PrescriptionsTabState extends State<_PrescriptionsTab>
    with AutomaticKeepAliveClientMixin {
  late Future<List<Prescription>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _future = widget.client.prescriptions();
  }

  void _reload() => setState(() => _future = widget.client.prescriptions());

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Loader<List<Prescription>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      emptyIcon: Icons.medication_outlined,
      emptyTitle: 'No prescriptions yet',
      emptyMessage: 'Prescriptions from your consultations will appear here.',
      builder: (context, list) => RefreshIndicator(
        onRefresh: () async => _reload(),
        child: ListView.builder(
          padding: const EdgeInsets.only(top: 8, bottom: 24),
          itemCount: list.length,
          itemBuilder: (context, index) {
            final prescription = list[index];
            return Card(
              child: ExpansionTile(
                shape: const Border(),
                title: Text(prettyDate(prescription.date),
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                subtitle: Text(
                  [
                    if (prescription.doctorName != null) prescription.doctorName!,
                    '${prescription.medicines.length} medicine(s)',
                  ].join(' · '),
                  style: const TextStyle(fontSize: 12),
                ),
                children: [
                  if (prescription.diagnosis != null && prescription.diagnosis!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text('Diagnosis: ${prescription.diagnosis}',
                            style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      ),
                    ),
                  ...prescription.medicines.map(
                    (medicine) => ListTile(
                      dense: true,
                      leading: const Icon(Icons.medication, size: 20, color: AppTheme.primary),
                      title: Text(medicine.name,
                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                      subtitle: Text(
                        [
                          if (medicine.quantity != null) 'Qty ${medicine.quantity}',
                          medicine.timing,
                          if (medicine.instructions != null && medicine.instructions!.isNotEmpty)
                            medicine.instructions!,
                          if (medicine.duration != null && medicine.duration!.isNotEmpty)
                            medicine.duration!,
                        ].join(' · '),
                        style: const TextStyle(fontSize: 11),
                      ),
                    ),
                  ),
                  if (prescription.advice != null && prescription.advice!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text('Advice: ${prescription.advice}',
                            style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _LabReportsTab extends StatefulWidget {
  const _LabReportsTab({required this.client});
  final ApiClient client;

  @override
  State<_LabReportsTab> createState() => _LabReportsTabState();
}

class _LabReportsTabState extends State<_LabReportsTab> with AutomaticKeepAliveClientMixin {
  late Future<List<LabReport>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _future = widget.client.labReports();
  }

  void _reload() => setState(() => _future = widget.client.labReports());

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Loader<List<LabReport>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      emptyIcon: Icons.science_outlined,
      emptyTitle: 'No reports yet',
      emptyMessage: 'Verified laboratory reports will appear here.',
      builder: (context, list) => RefreshIndicator(
        onRefresh: () async => _reload(),
        child: ListView.builder(
          padding: const EdgeInsets.only(top: 8, bottom: 24),
          itemCount: list.length,
          itemBuilder: (context, index) {
            final report = list[index];
            return Card(
              child: ExpansionTile(
                shape: const Border(),
                leading: Icon(
                  report.isAbnormal ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                  color: report.isAbnormal ? AppTheme.danger : AppTheme.success,
                ),
                title: Text(report.testName,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                subtitle: Text(prettyDate(report.dateConducted) +
                    (report.verifiedBy != null ? ' · verified by ${report.verifiedBy}' : '')),                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Table(
                      columnWidths: const {
                        0: FlexColumnWidth(2.4),
                        1: FlexColumnWidth(1.4),
                        2: FlexColumnWidth(1.6),
                      },
                      border: TableBorder(
                        horizontalInside: BorderSide(color: AppTheme.border.withValues(alpha: 0.8)),
                      ),
                      children: [
                        const TableRow(children: [
                          _Cell('Parameter', bold: true),
                          _Cell('Result', bold: true),
                          _Cell('Reference', bold: true),
                        ]),
                        ...report.results.map(
                          (row) => TableRow(children: [
                            _Cell(row.parameter),
                            _Cell(
                              row.unit != null && row.unit!.isNotEmpty
                                  ? '${row.result ?? '—'} ${row.unit}'
                                  : (row.result ?? '—'),
                              color: row.isAbnormal ? AppTheme.danger : null,
                              bold: row.isAbnormal,
                            ),
                            _Cell(row.range ?? '—', muted: true),
                          ]),
                        ),
                      ],
                    ),
                  ),
                  if (report.interpretation != null && report.interpretation!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text(report.interpretation!,
                            style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      ),
                    )
                  else
                    const SizedBox(height: 12),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  const _Cell(this.text, {this.bold = false, this.muted = false, this.color});
  final String text;
  final bool bold;
  final bool muted;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 12,
          fontWeight: bold ? FontWeight.bold : FontWeight.normal,
          color: color ?? (muted ? Colors.black45 : Colors.black87),
        ),
      ),
    );
  }
}

class _BillsTab extends StatefulWidget {
  const _BillsTab({required this.client});
  final ApiClient client;

  @override
  State<_BillsTab> createState() => _BillsTabState();
}

class _BillsTabState extends State<_BillsTab> with AutomaticKeepAliveClientMixin {
  late Future<List<PortalBill>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _future = widget.client.bills();
  }

  void _reload() => setState(() => _future = widget.client.bills());

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Loader<List<PortalBill>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      emptyIcon: Icons.receipt_long_outlined,
      emptyTitle: 'No bills yet',
      emptyMessage: 'Charges raised by the hospital will show up here.',
      builder: (context, list) {
        final total = list.fold<double>(0, (sum, bill) => sum + bill.total);
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(
            padding: const EdgeInsets.only(top: 8, bottom: 24),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.account_balance_wallet, color: AppTheme.primary),
                      const SizedBox(width: 12),
                      const Text('Total billed', style: TextStyle(fontSize: 13)),
                      const Spacer(),
                      Text(rupees(total),
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
              ),
              ...list.map(
                (bill) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                bill.billType.replaceAll('_', ' ').toUpperCase(),
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold, fontSize: 13, letterSpacing: 0.4),
                              ),
                            ),
                            if (bill.status != null) StatusChip(bill.status!, compact: true),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text('${prettyDate(bill.billDate)} · #${bill.id}',
                            style: const TextStyle(fontSize: 11, color: Colors.black45)),
                        if (bill.items.isNotEmpty) ...[
                          const Divider(height: 20),
                          ...bill.items.map(
                            (item) => Padding(
                              padding: const EdgeInsets.symmetric(vertical: 2),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Text(item.name,
                                        style: const TextStyle(fontSize: 12)),
                                  ),
                                  Text(rupees(item.amount),
                                      style: const TextStyle(fontSize: 12)),
                                ],
                              ),
                            ),
                          ),
                        ],
                        const Divider(height: 20),
                        Row(
                          children: [
                            const Text('Total',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                            const Spacer(),
                            Text(rupees(bill.total),
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold, fontSize: 15)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _DocumentsTab extends StatefulWidget {
  const _DocumentsTab({required this.client});
  final ApiClient client;

  @override
  State<_DocumentsTab> createState() => _DocumentsTabState();
}

class _DocumentsTabState extends State<_DocumentsTab> with AutomaticKeepAliveClientMixin {
  late Future<List<PortalDocument>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _future = widget.client.documents();
  }

  void _reload() => setState(() => _future = widget.client.documents());

  IconData _iconFor(String type) {
    switch (type.toLowerCase()) {
      case 'prescription':
        return Icons.medication_outlined;
      case 'lab_report':
        return Icons.science_outlined;
      case 'bill':
        return Icons.receipt_long_outlined;
      case 'discharge_summary':
        return Icons.assignment_turned_in_outlined;
      case 'insurance':
        return Icons.shield_outlined;
      default:
        return Icons.description_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Loader<List<PortalDocument>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      emptyIcon: Icons.folder_open,
      emptyTitle: 'No documents yet',
      emptyMessage: 'Prescriptions, reports and discharge summaries are collected here.',
      builder: (context, list) => RefreshIndicator(
        onRefresh: () async => _reload(),
        child: ListView.builder(
          padding: const EdgeInsets.only(top: 8, bottom: 24),
          itemCount: list.length,
          itemBuilder: (context, index) {
            final document = list[index];
            return Card(
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                  child: Icon(_iconFor(document.type), color: AppTheme.primary, size: 20),
                ),
                title: Text(document.title,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                subtitle: Text(
                  [
                    document.type.replaceAll('_', ' '),
                    if (document.date != null) prettyDate(document.date),
                    if (document.subtitle != null) document.subtitle!,
                  ].join(' · '),
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
