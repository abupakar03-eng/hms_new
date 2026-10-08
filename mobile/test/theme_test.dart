import 'package:flutter_test/flutter_test.dart';
import 'package:hospital_mobile/core/theme.dart';

void main() {
  group('rupees', () {
    test('formats small amounts without separators', () {
      expect(rupees(0), '₹0');
      expect(rupees(500), '₹500');
      expect(rupees(999), '₹999');
    });

    test('uses Indian grouping (last three, then pairs)', () {
      expect(rupees(1000), '₹1,000');
      expect(rupees(12345), '₹12,345');
      expect(rupees(123456), '₹1,23,456');
      expect(rupees(12345678), '₹1,23,45,678');
    });

    test('rounds paise to the nearest rupee', () {
      expect(rupees(499.4), '₹499');
      expect(rupees(499.6), '₹500');
    });

    test('keeps the sign for credit notes and refunds', () {
      expect(rupees(-1500), '-₹1,500');
    });
  });

  group('statusColor', () {
    test('separates healthy, in-progress and terminal states', () {
      expect(AppTheme.statusColor('Available'), AppTheme.success);
      expect(AppTheme.statusColor('Discharged'), AppTheme.success);
      expect(AppTheme.statusColor('Occupied'), AppTheme.warning);
      expect(AppTheme.statusColor('Cleaning'), isNot(AppTheme.success));
      expect(AppTheme.statusColor('Critical'), AppTheme.danger);
      expect(AppTheme.statusColor('Maintenance'), AppTheme.danger);
    });

    test('is case-insensitive and never throws on an unknown status', () {
      expect(AppTheme.statusColor('AVAILABLE'), AppTheme.success);
      expect(AppTheme.statusColor('something-new'), isNotNull);
    });
  });

  group('date formatting', () {
    test('renders a friendly date', () {
      final rendered = prettyDate('2026-10-01T09:30:00');
      expect(rendered, contains('2026'));
      expect(rendered, contains('Oct'));
    });

    test('shows a dash for missing or unparseable input', () {
      expect(prettyDate(null), '—');
      expect(prettyDate(''), '—');
      expect(prettyDate('not a date'), 'not a date');
      expect(prettyDateTime(null), '—');
    });

    test('uses a 12-hour clock', () {
      final rendered = prettyDateTime('2026-10-01T14:05:00');
      expect(rendered, contains('PM'));
    });
  });
}
