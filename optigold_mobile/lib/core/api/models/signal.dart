class SignalModel {
  final String id;
  final DateTime generatedAt;
  final String action;
  final String? instrument;
  final double? strikeA;
  final double? strikeB;
  final String? expiry;
  final int? quantity;
  final double? premiumCollected;
  final double? maxProfit;
  final double? maxLoss;
  final double? breakevenA;
  final double? breakevenB;
  final double? probabilityOfProfit;
  final double? expectedValue;
  final double? kellyFraction;
  final double? compositeScore;
  final String? confidence;
  final double? ivRank;
  final double? ivPercentile;
  final String? marketRegime;
  final String? marketBias;
  final String? reasoningPlain;
  final String? reasoningDetail;
  final Map<String, dynamic>? greeks;
  final Map<String, dynamic>? scoreBreakdown;
  final Map<String, dynamic>? altSignal;

  const SignalModel({
    required this.id,
    required this.generatedAt,
    required this.action,
    this.instrument,
    this.strikeA,
    this.strikeB,
    this.expiry,
    this.quantity,
    this.premiumCollected,
    this.maxProfit,
    this.maxLoss,
    this.breakevenA,
    this.breakevenB,
    this.probabilityOfProfit,
    this.expectedValue,
    this.kellyFraction,
    this.compositeScore,
    this.confidence,
    this.ivRank,
    this.ivPercentile,
    this.marketRegime,
    this.marketBias,
    this.reasoningPlain,
    this.reasoningDetail,
    this.greeks,
    this.scoreBreakdown,
    this.altSignal,
  });

  factory SignalModel.fromJson(Map<String, dynamic> j) => SignalModel(
        id:                  j['id'] as String,
        generatedAt:         DateTime.parse(j['generated_at'] as String),
        action:              j['action'] as String,
        instrument:          j['instrument'] as String?,
        strikeA:             (j['strike_a'] as num?)?.toDouble(),
        strikeB:             (j['strike_b'] as num?)?.toDouble(),
        expiry:              j['expiry'] as String?,
        quantity:            j['quantity'] as int?,
        premiumCollected:    (j['premium_collected'] as num?)?.toDouble(),
        maxProfit:           (j['max_profit'] as num?)?.toDouble(),
        maxLoss:             (j['max_loss'] as num?)?.toDouble(),
        breakevenA:          (j['breakeven_a'] as num?)?.toDouble(),
        breakevenB:          (j['breakeven_b'] as num?)?.toDouble(),
        probabilityOfProfit: (j['probability_of_profit'] as num?)?.toDouble(),
        expectedValue:       (j['expected_value'] as num?)?.toDouble(),
        kellyFraction:       (j['kelly_fraction'] as num?)?.toDouble(),
        compositeScore:      (j['composite_score'] as num?)?.toDouble(),
        confidence:          j['confidence'] as String?,
        ivRank:              (j['iv_rank'] as num?)?.toDouble(),
        ivPercentile:        (j['iv_percentile'] as num?)?.toDouble(),
        marketRegime:        j['market_regime'] as String?,
        marketBias:          j['market_bias'] as String?,
        reasoningPlain:      j['reasoning_plain'] as String?,
        reasoningDetail:     j['reasoning_detail'] as String?,
        greeks:              j['greeks'] as Map<String, dynamic>?,
        scoreBreakdown:      j['score_breakdown'] as Map<String, dynamic>?,
        altSignal:           j['alt_signal'] as Map<String, dynamic>?,
      );

  // Derived helpers
  bool get isBullish   => marketBias?.toLowerCase() == 'bullish';
  bool get isBearish   => marketBias?.toLowerCase() == 'bearish';
  bool get isHighConf  => confidence?.toLowerCase() == 'high';
  bool get isMedConf   => confidence?.toLowerCase() == 'medium';

  String get formattedRegime {
    if (marketRegime == null) return 'Unknown';
    return marketRegime!.replaceAll('_', ' ').split(' ')
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  double get pop => probabilityOfProfit ?? 0.0;
  double get score => compositeScore ?? 0.0;
}

class SignalListItem {
  final String id;
  final DateTime generatedAt;
  final String action;
  final String? instrument;
  final double? strikeA;
  final double? strikeB;
  final String? expiry;
  final int? quantity;
  final double? compositeScore;
  final String? confidence;
  final String? marketRegime;

  const SignalListItem({
    required this.id,
    required this.generatedAt,
    required this.action,
    this.instrument,
    this.strikeA,
    this.strikeB,
    this.expiry,
    this.quantity,
    this.compositeScore,
    this.confidence,
    this.marketRegime,
  });

  factory SignalListItem.fromJson(Map<String, dynamic> j) => SignalListItem(
        id:             j['id'] as String,
        generatedAt:    DateTime.parse(j['generated_at'] as String),
        action:         j['action'] as String,
        instrument:     j['instrument'] as String?,
        strikeA:        (j['strike_a'] as num?)?.toDouble(),
        strikeB:        (j['strike_b'] as num?)?.toDouble(),
        expiry:         j['expiry'] as String?,
        quantity:       j['quantity'] as int?,
        compositeScore: (j['composite_score'] as num?)?.toDouble(),
        confidence:     j['confidence'] as String?,
        marketRegime:   j['market_regime'] as String?,
      );
}
