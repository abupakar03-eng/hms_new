import 'package:flutter/material.dart';

/// Visual language shared across the app. Mirrors the web console's palette so
/// staff moving between web and mobile see one product.
class AppTheme {
  static const Color primary = Color(0xFF2563EB);
  static const Color success = Color(0xFF10B981);
  static const Color warning = Color(0xFFF59E0B);
  static const Color danger = Color(0xFFEF4444);
  static const Color surface = Color(0xFFF8FAFC);
  static const Color border = Color(0xFFE2E8F0);

  static ThemeData light() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        primary: primary,
        error: danger,
      ),
      scaffoldBackgroundColor: surface,
      appBarTheme: const AppBarTheme(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: border),
        ),
        color: Colors.white,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: primary.withValues(alpha: 0.12),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  /// A small colour-coded chip used for statuses throughout the app.
  static Color statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'available':
      case 'completed':
      case 'discharged':
      case 'paid':
      case 'given':
      case 'approved':
      case 'final':
        return success;
      case 'occupied':
      case 'pending':
      case 'waiting':
      case 'active':
      case 'draft':
      case 'ordered':
      case 'collected':
        return warning;
      case 'cleaning':
      case 'in progress':
      case 'reserved':
      case 'partial':
        return const Color(0xFF0EA5E9);
      case 'cancelled':
      case 'critical':
      case 'abnormal':
      case 'blocked':
      case 'maintenance':
      case 'stopped':
        return danger;
      default:
        return const Color(0xFF64748B);
    }
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.label, {super.key, this.compact = false});
  final String label;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(label);
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 10, vertical: compact ? 2 : 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: compact ? 10 : 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

/// Consistent empty / error / loading states.
class StateView extends StatelessWidget {
  const StateView({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 52, color: Colors.black26),
            const SizedBox(height: 14),
            Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            if (message != null) ...[
              const SizedBox(height: 8),
              Text(message!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54, fontSize: 13)),
            ],
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}

/// Human-friendly date rendering for ISO strings coming from the API.
String prettyDate(String? iso) {
  if (iso == null || iso.isEmpty) return '—';
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) return iso;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final local = parsed.toLocal();
  return '${local.day} ${months[local.month - 1]} ${local.year}';
}

String prettyDateTime(String? iso) {
  if (iso == null || iso.isEmpty) return '—';
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) return iso;
  final local = parsed.toLocal();
  final hour12 = local.hour % 12 == 0 ? 12 : local.hour % 12;
  final ampm = local.hour < 12 ? 'AM' : 'PM';
  return '${prettyDate(iso)}, $hour12:${local.minute.toString().padLeft(2, '0')} $ampm';
}

String rupees(num amount) {
  // Indian grouping (1,23,456): last three digits, then pairs.
  final negative = amount < 0;
  final whole = amount.round().abs().toString();
  String grouped;
  if (whole.length <= 3) {
    grouped = whole;
  } else {
    final last3 = whole.substring(whole.length - 3);
    final rest = whole.substring(0, whole.length - 3);
    final parts = <String>[];
    for (var end = rest.length; end > 0; end -= 2) {
      final start = end - 2 < 0 ? 0 : end - 2;
      parts.insert(0, rest.substring(start, end));
    }
    grouped = '${parts.join(',')},$last3';
  }
  return '${negative ? '-' : ''}₹$grouped';
}
