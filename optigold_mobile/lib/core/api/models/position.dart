class PositionModel {
  final int id;
  final String? signalId;
  final DateTime? confirmedAt;
  final String? instrument;
  final String? strategy;
  final double? strikeA;
  final double? strikeB;
  final String? expiry;
  final int? quantity;
  final double? entryPrice;
  final String status;
  final double? closePrice;
  final DateTime? closedAt;
  final double? realizedPnl;
  final String? closeReason;
  final double? actualEntryPrice;
  final double? entryDeviationPct;
  final String? notes;

  const PositionModel({
    required this.id,
    required this.status,
    this.signalId,
    this.confirmedAt,
    this.instrument,
    this.strategy,
    this.strikeA,
    this.strikeB,
    this.expiry,
    this.quantity,
    this.entryPrice,
    this.closePrice,
    this.closedAt,
    this.realizedPnl,
    this.closeReason,
    this.actualEntryPrice,
    this.entryDeviationPct,
    this.notes,
  });

  factory PositionModel.fromJson(Map<String, dynamic> j) => PositionModel(
        id:          j['id'] as int,
        status:      j['status'] as String,
        signalId:    j['signal_id'] as String?,
        confirmedAt: j['confirmed_at'] != null
            ? DateTime.parse(j['confirmed_at'] as String)
            : null,
        instrument:  j['instrument'] as String?,
        strategy:    j['strategy'] as String?,
        strikeA:     (j['strike_a'] as num?)?.toDouble(),
        strikeB:     (j['strike_b'] as num?)?.toDouble(),
        expiry:      j['expiry'] as String?,
        quantity:    j['quantity'] as int?,
        entryPrice:  (j['entry_price'] as num?)?.toDouble(),
        closePrice:       (j['close_price'] as num?)?.toDouble(),
        closedAt:         j['closed_at'] != null
            ? DateTime.parse(j['closed_at'] as String)
            : null,
        realizedPnl:      (j['realized_pnl'] as num?)?.toDouble(),
        closeReason:      j['close_reason'] as String?,
        actualEntryPrice: (j['actual_entry_price'] as num?)?.toDouble(),
        entryDeviationPct:(j['entry_deviation_pct'] as num?)?.toDouble(),
        notes:            j['notes'] as String?,
      );

  bool get isOpen   => status == 'open';
  bool get isClosed => status == 'closed';

  String get formattedStrategy {
    if (strategy == null) return 'Unknown';
    return strategy!.replaceAll('_', ' ').split(' ')
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }
}
