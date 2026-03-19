class UserProfile {
  final double capital;
  final double maxLossPerTrade;
  final bool acceptsOptions;
  final bool acceptsMargin;
  final bool acceptsUnlimitedRisk;
  final bool acceptsMultiLeg;
  final String timeHorizon;
  final String experienceLevel;
  final double riskMultiplier;
  final bool notificationsEnabled;

  const UserProfile({
    required this.capital,
    required this.maxLossPerTrade,
    required this.acceptsOptions,
    required this.acceptsMargin,
    required this.acceptsUnlimitedRisk,
    required this.acceptsMultiLeg,
    required this.timeHorizon,
    required this.experienceLevel,
    required this.riskMultiplier,
    required this.notificationsEnabled,
  });

  factory UserProfile.fromJson(Map<String, dynamic> j) => UserProfile(
        capital:               (j['capital'] as num).toDouble(),
        maxLossPerTrade:       (j['max_loss_per_trade'] as num).toDouble(),
        acceptsOptions:        j['accepts_options'] as bool,
        acceptsMargin:         j['accepts_margin'] as bool,
        acceptsUnlimitedRisk:  j['accepts_unlimited_risk'] as bool,
        acceptsMultiLeg:       j['accepts_multi_leg'] as bool,
        timeHorizon:           j['time_horizon'] as String,
        experienceLevel:       j['experience_level'] as String,
        riskMultiplier:        (j['risk_multiplier'] as num).toDouble(),
        notificationsEnabled:  j['notifications_enabled'] as bool,
      );

  Map<String, dynamic> toJson() => {
        'capital':                capital,
        'max_loss_per_trade':     maxLossPerTrade,
        'accepts_options':        acceptsOptions,
        'accepts_margin':         acceptsMargin,
        'accepts_unlimited_risk': acceptsUnlimitedRisk,
        'accepts_multi_leg':      acceptsMultiLeg,
        'time_horizon':           timeHorizon,
        'experience_level':       experienceLevel,
        'risk_multiplier':        riskMultiplier,
        'notifications_enabled':  notificationsEnabled,
      };

  UserProfile copyWith({
    double? capital,
    double? maxLossPerTrade,
    bool? acceptsOptions,
    bool? acceptsMargin,
    bool? acceptsUnlimitedRisk,
    bool? acceptsMultiLeg,
    String? timeHorizon,
    String? experienceLevel,
    double? riskMultiplier,
    bool? notificationsEnabled,
  }) =>
      UserProfile(
        capital:              capital ?? this.capital,
        maxLossPerTrade:      maxLossPerTrade ?? this.maxLossPerTrade,
        acceptsOptions:       acceptsOptions ?? this.acceptsOptions,
        acceptsMargin:        acceptsMargin ?? this.acceptsMargin,
        acceptsUnlimitedRisk: acceptsUnlimitedRisk ?? this.acceptsUnlimitedRisk,
        acceptsMultiLeg:      acceptsMultiLeg ?? this.acceptsMultiLeg,
        timeHorizon:          timeHorizon ?? this.timeHorizon,
        experienceLevel:      experienceLevel ?? this.experienceLevel,
        riskMultiplier:       riskMultiplier ?? this.riskMultiplier,
        notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      );

  static UserProfile get defaults => const UserProfile(
        capital:              10000,
        maxLossPerTrade:      500,
        acceptsOptions:       true,
        acceptsMargin:        false,
        acceptsUnlimitedRisk: false,
        acceptsMultiLeg:      false,
        timeHorizon:          'monthly',
        experienceLevel:      'beginner',
        riskMultiplier:       0.5,
        notificationsEnabled: true,
      );
}
