class MarketSnapshot {
  final DateTime capturedAt;
  final double? gldPrice;
  final double? gld24hChangePct;
  final double? gldAtmIv;
  final double? gldIvRank;
  final double? gldIvPercentile;
  final double? gldHv20d;
  final double? vixLevel;
  final double? ivPremiumRatio;
  final double? putCallSkew;
  final String? marketRegime;
  final double? regimeConfidence;
  final double? ema20;
  final double? ema50;
  final double? rsi14;
  final double? adx;
  final String? marketSession;

  const MarketSnapshot({
    required this.capturedAt,
    this.gldPrice,
    this.gld24hChangePct,
    this.gldAtmIv,
    this.gldIvRank,
    this.gldIvPercentile,
    this.gldHv20d,
    this.vixLevel,
    this.ivPremiumRatio,
    this.putCallSkew,
    this.marketRegime,
    this.regimeConfidence,
    this.ema20,
    this.ema50,
    this.rsi14,
    this.adx,
    this.marketSession,
  });

  factory MarketSnapshot.fromJson(Map<String, dynamic> j) => MarketSnapshot(
        capturedAt:       DateTime.parse(j['captured_at'] as String),
        gldPrice:         (j['gld_price'] as num?)?.toDouble(),
        gld24hChangePct:  (j['gld_24h_change_pct'] as num?)?.toDouble(),
        gldAtmIv:         (j['gld_atm_iv'] as num?)?.toDouble(),
        gldIvRank:        (j['gld_iv_rank'] as num?)?.toDouble(),
        gldIvPercentile:  (j['gld_iv_percentile'] as num?)?.toDouble(),
        gldHv20d:         (j['gld_hv_20d'] as num?)?.toDouble(),
        vixLevel:         (j['vix_level'] as num?)?.toDouble(),
        ivPremiumRatio:   (j['iv_premium_ratio'] as num?)?.toDouble(),
        putCallSkew:      (j['put_call_skew'] as num?)?.toDouble(),
        marketRegime:     j['market_regime'] as String?,
        regimeConfidence: (j['regime_confidence'] as num?)?.toDouble(),
        ema20:            (j['ema20'] as num?)?.toDouble(),
        ema50:            (j['ema50'] as num?)?.toDouble(),
        rsi14:            (j['rsi_14'] as num?)?.toDouble(),
        adx:              (j['adx'] as num?)?.toDouble(),
        marketSession:    j['market_session'] as String?,
      );

  bool get isBullish => marketRegime?.contains('bull') == true;
  bool get isBearish => marketRegime?.contains('bear') == true;

  String get formattedRegime {
    if (marketRegime == null) return 'Unknown';
    return marketRegime!.replaceAll('_', ' ').split(' ')
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }
}
