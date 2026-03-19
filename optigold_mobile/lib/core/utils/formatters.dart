import 'package:intl/intl.dart';

class Fmt {
  Fmt._();

  static final _currency = NumberFormat.currency(symbol: '\$', decimalDigits: 2);
  static final _compact  = NumberFormat.compact();
  static final _pct      = NumberFormat('0.0#');
  static final _date     = DateFormat('MMM d, yyyy');
  static final _dateShort = DateFormat('MMM d');
  static String currency(double? v) => v == null ? '--' : _currency.format(v);

  static String compactCurrency(double? v) {
    if (v == null) return '--';
    if (v.abs() >= 1000) return '\$${_compact.format(v)}';
    return _currency.format(v);
  }

  static String percent(double? v) => v == null ? '--' : '${_pct.format(v)}%';

  static String date(dynamic v) {
    if (v == null) return '--';
    if (v is DateTime) return _date.format(v);
    try {
      return _date.format(DateTime.parse(v.toString()));
    } catch (_) {
      return v.toString();
    }
  }

  static String dateShort(dynamic v) {
    if (v == null) return '--';
    if (v is DateTime) return _dateShort.format(v);
    try {
      return _dateShort.format(DateTime.parse(v.toString()));
    } catch (_) {
      return v.toString();
    }
  }

  static String timeAgo(DateTime? t) {
    if (t == null) return '--';
    final diff = DateTime.now().difference(t);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return _dateShort.format(t);
  }

  static String priceChange(double? v) {
    if (v == null) return '--';
    final sign = v >= 0 ? '+' : '';
    return '$sign${_pct.format(v)}%';
  }

  static String score(double? v) => v == null ? '--' : v.toStringAsFixed(1);
}
