import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/colors.dart';
import '../../core/theme/typography.dart';
import '../../core/utils/constants.dart';
import '../../providers/prefs_provider.dart';
import '../../providers/profile_provider.dart';
import '../../providers/signal_provider.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _pageController = PageController();
  int _page = 0;

  // Form state
  double _capital = 1000;
  double _maxLoss = 20; // 2% of default $1k capital
  String _experience = 'beginner';
  bool _acceptsOptions = true;
  bool _acceptsMargin  = false;
  bool _acceptsMultiLeg = false;
  String _horizon = 'monthly';

  final _steps = ['Capital', 'Max Loss', 'Experience', 'Strategies', 'Horizon'];

  void _next() {
    if (_page < _steps.length - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOut,
      );
    } else {
      _finish();
    }
  }

  void _back() {
    if (_page > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOut,
      );
    }
  }

  Future<void> _finish() async {
    // Synchronous — prefs already loaded in main()
    await ref.read(sharedPreferencesProvider).setBool(AppConstants.onboardedKey, true);

    // Best-effort sync to backend; don't block navigation on failure
    try {
      await ref.read(profileProvider.notifier).patch({
        'capital':            _capital,
        'max_loss_per_trade': _maxLoss,
        'accepts_options':    _acceptsOptions,
        'accepts_margin':     _acceptsMargin,
        'accepts_multi_leg':  _acceptsMultiLeg,
        'experience_level':   _experience,
        'time_horizon':       _horizon,
      });
      // Regenerate signal for new profile; push result directly into latestSignalProvider
      // (no invalidate needed — avoids triggering a loading state on home screen)
      final newSignal = await ref.read(signalRefreshProvider.future);
      ref.read(latestSignalProvider.notifier).state = AsyncData(newSignal);
    } catch (_) {
      // Backend unavailable — profile will sync when backend is reachable
    }

    if (mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildProgressBar(),
              Expanded(
                child: PageView(
                  controller: _pageController,
                  physics: const NeverScrollableScrollPhysics(),
                  onPageChanged: (i) => setState(() => _page = i),
                  children: [
                    _StepCapital(value: _capital, onChanged: (v) => setState(() => _capital = v)),
                    _StepMaxLoss(value: _maxLoss, capital: _capital, onChanged: (v) => setState(() => _maxLoss = v)),
                    _StepExperience(selected: _experience, onChanged: (v) => setState(() => _experience = v)),
                    _StepStrategies(
                      acceptsOptions: _acceptsOptions,
                      acceptsMargin: _acceptsMargin,
                      acceptsMultiLeg: _acceptsMultiLeg,
                      onOptionsChanged:   (v) => setState(() => _acceptsOptions  = v),
                      onMarginChanged:    (v) => setState(() => _acceptsMargin   = v),
                      onMultiLegChanged:  (v) => setState(() => _acceptsMultiLeg = v),
                    ),
                    _StepHorizon(selected: _horizon, onChanged: (v) => setState(() => _horizon = v)),
                  ],
                ),
              ),
              _buildButtons(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() => Padding(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
        child: Row(
          children: [
            Text(
              'OptiGold',
              style: AppTypography.strategyName.copyWith(
                color: AppColors.primary,
                fontSize: 22,
                letterSpacing: 1,
              ),
            ),
            const Spacer(),
            Text(
              '${_page + 1} / ${_steps.length}',
              style: AppTypography.metricLabel,
            ),
          ],
        ),
      );

  Widget _buildProgressBar() => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: (_page + 1) / _steps.length,
            minHeight: 3,
            backgroundColor: AppColors.surface,
            valueColor: const AlwaysStoppedAnimation(AppColors.primary),
          ),
        ),
      );

  Widget _buildButtons() => Padding(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
        child: Row(
          children: [
            if (_page > 0)
              GestureDetector(
                onTap: _back,
                child: Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.divider),
                  ),
                  child: const Icon(Icons.arrow_back, color: AppColors.textSecondary),
                ),
              ),
            const SizedBox(width: 12),
            Expanded(
              child: Platform.isIOS
                  ? CupertinoButton(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(14),
                      onPressed: _next,
                      child: Text(
                        _page == _steps.length - 1 ? 'Start Trading' : 'Continue',
                        style: AppTypography.actionText,
                      ),
                    )
                  : FilledButton(
                      onPressed: _next,
                      child: Text(
                        _page == _steps.length - 1 ? 'Start Trading' : 'Continue',
                      ),
                    ),
            ),
          ],
        ),
      );
}

// ── Step widgets ────────────────────────────────────────────

class _StepCapital extends StatefulWidget {
  final double value;
  final ValueChanged<double> onChanged;
  const _StepCapital({required this.value, required this.onChanged});

  @override
  State<_StepCapital> createState() => _StepCapitalState();
}

class _StepCapitalState extends State<_StepCapital> {
  late double _local;

  @override
  void initState() {
    super.initState();
    _local = widget.value;
  }

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      icon: '💰',
      title: 'Account Capital',
      subtitle: 'How much capital are you trading with?',
      child: Column(
        children: [
          Text(
            '\$${_local.toStringAsFixed(0)}',
            style: AppTypography.priceHero.copyWith(fontSize: 36),
          ),
          const SizedBox(height: 24),
          Slider(
            value: _local,
            min: 100,
            max: 5000,
            divisions: 49,
            activeColor: AppColors.primary,
            inactiveColor: AppColors.surface,
            onChanged: (v) => setState(() => _local = v),
            onChangeEnd: widget.onChanged,
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('\$100', style: AppTypography.metricLabel),
              Text('\$5,000', style: AppTypography.metricLabel),
            ],
          ),
        ],
      ),
    );
  }
}

class _StepMaxLoss extends StatefulWidget {
  final double value;
  final double capital;
  final ValueChanged<double> onChanged;
  const _StepMaxLoss({required this.value, required this.capital, required this.onChanged});

  @override
  State<_StepMaxLoss> createState() => _StepMaxLossState();
}

class _StepMaxLossState extends State<_StepMaxLoss> {
  late double _local;

  double get _minLoss => (widget.capital * 0.005).clamp(10.0, 50.0);

  @override
  void initState() {
    super.initState();
    _local = widget.value;
  }

  @override
  Widget build(BuildContext context) {
    final pct = (_local / widget.capital * 100).toStringAsFixed(1);
    return _StepWrapper(
      icon: '🛡️',
      title: 'Max Loss Per Trade',
      subtitle: 'Maximum you\'re willing to lose on a single trade',
      child: Column(
        children: [
          Text(
            '\$${_local.toStringAsFixed(0)}',
            style: AppTypography.priceHero.copyWith(fontSize: 36, color: AppColors.loss),
          ),
          Text(
            '$pct% of capital',
            style: AppTypography.bodyRegular.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),
          Slider(
            value: _local.clamp(_minLoss, widget.capital * 0.5),
            min: _minLoss,
            max: widget.capital * 0.5,
            activeColor: AppColors.loss,
            inactiveColor: AppColors.surface,
            onChanged: (v) => setState(() => _local = v),
            onChangeEnd: widget.onChanged,
          ),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.primary.withOpacity(0.2)),
            ),
            child: Text(
              '💡 Recommended: 2–5% of capital (\$${(widget.capital * 0.02).toStringAsFixed(0)}–\$${(widget.capital * 0.05).toStringAsFixed(0)})',
              style: AppTypography.bodyRegular.copyWith(color: AppColors.primary, fontSize: 12),
            ),
          ),
          if (_local < 50) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.warning.withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.warning.withOpacity(0.3)),
              ),
              child: Text(
                '⚠ \$${_local.toStringAsFixed(0)} 低于期权交易最低风险阈值（约 \$50）。系统可能无法推荐任何策略，将显示"观望"信号。',
                style: AppTypography.bodyRegular.copyWith(color: AppColors.warning, fontSize: 12),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StepExperience extends StatelessWidget {
  final String selected;
  final ValueChanged<String> onChanged;
  const _StepExperience({required this.selected, required this.onChanged});

  static const _options = [
    (value: 'beginner',     icon: '🌱', title: 'Beginner', sub: 'New to options trading'),
    (value: 'intermediate', icon: '📈', title: 'Intermediate', sub: 'Traded options before'),
    (value: 'advanced',     icon: '🎯', title: 'Advanced', sub: 'Multi-leg strategies, Greeks'),
  ];

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      icon: '🎓',
      title: 'Experience Level',
      subtitle: 'We\'ll tailor strategy complexity to your level',
      child: Column(
        children: _options.map((o) {
          final isSelected = o.value == selected;
          return GestureDetector(
            onTap: () => onChanged(o.value),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary.withOpacity(0.1) : AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected ? AppColors.primary : AppColors.divider,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Row(
                children: [
                  Text(o.icon, style: const TextStyle(fontSize: 28)),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(o.title, style: AppTypography.bodyMedium),
                        Text(o.sub, style: AppTypography.bodyRegular.copyWith(fontSize: 12)),
                      ],
                    ),
                  ),
                  if (isSelected)
                    const Icon(Icons.check_circle, color: AppColors.primary, size: 20),
                ],
              ),
            ).animate(target: isSelected ? 1 : 0)
             .scaleXY(begin: 1, end: 1.01, duration: 150.ms),
          );
        }).toList(),
      ),
    );
  }
}

class _StepStrategies extends StatelessWidget {
  final bool acceptsOptions;
  final bool acceptsMargin;
  final bool acceptsMultiLeg;
  final ValueChanged<bool> onOptionsChanged;
  final ValueChanged<bool> onMarginChanged;
  final ValueChanged<bool> onMultiLegChanged;

  const _StepStrategies({
    required this.acceptsOptions,
    required this.acceptsMargin,
    required this.acceptsMultiLeg,
    required this.onOptionsChanged,
    required this.onMarginChanged,
    required this.onMultiLegChanged,
  });

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      icon: '📋',
      title: 'Strategy Permissions',
      subtitle: 'What types of strategies are you comfortable with?',
      child: Column(
        children: [
          _ToggleRow(
            icon: '📊',
            title: 'Options Trading',
            sub: 'Calls, puts, spreads',
            value: acceptsOptions,
            onChanged: onOptionsChanged,
          ),
          _ToggleRow(
            icon: '🏦',
            title: 'Margin / Collateral',
            sub: 'Cash-secured puts require margin',
            value: acceptsMargin,
            onChanged: onMarginChanged,
          ),
          _ToggleRow(
            icon: '🔀',
            title: 'Multi-Leg Strategies',
            sub: 'Spreads, iron condors',
            value: acceptsMultiLeg,
            onChanged: onMultiLegChanged,
          ),
        ],
      ),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final String icon;
  final String title;
  final String sub;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleRow({
    required this.icon,
    required this.title,
    required this.sub,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.divider),
      ),
      child: Row(
        children: [
          Text(icon, style: const TextStyle(fontSize: 24)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTypography.bodyMedium),
                Text(sub, style: AppTypography.metricLabel),
              ],
            ),
          ),
          Platform.isIOS
              ? CupertinoSwitch(
                  value: value,
                  activeColor: AppColors.primary,
                  onChanged: onChanged,
                )
              : Switch(
                  value: value,
                  activeColor: AppColors.primary,
                  onChanged: onChanged,
                ),
        ],
      ),
    );
  }
}

class _StepHorizon extends StatelessWidget {
  final String selected;
  final ValueChanged<String> onChanged;
  const _StepHorizon({required this.selected, required this.onChanged});

  static const _options = [
    (value: 'weekly',    icon: '⚡', title: 'Weekly', sub: '7-day options (higher risk)'),
    (value: 'monthly',   icon: '📅', title: 'Monthly', sub: '30-day options (recommended)'),
    (value: 'quarterly', icon: '🗓️', title: 'Quarterly', sub: '60-day options (more stable)'),
  ];

  @override
  Widget build(BuildContext context) {
    return _StepWrapper(
      icon: '⏰',
      title: 'Trading Horizon',
      subtitle: 'Preferred option expiration timeframe',
      child: Column(
        children: _options.map((o) {
          final isSelected = o.value == selected;
          return GestureDetector(
            onTap: () => onChanged(o.value),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary.withOpacity(0.1) : AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected ? AppColors.primary : AppColors.divider,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Row(
                children: [
                  Text(o.icon, style: const TextStyle(fontSize: 26)),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(o.title, style: AppTypography.bodyMedium),
                        Text(o.sub, style: AppTypography.bodyRegular.copyWith(fontSize: 12)),
                      ],
                    ),
                  ),
                  if (isSelected)
                    const Icon(Icons.check_circle, color: AppColors.primary, size: 20),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ── Shared step wrapper ─────────────────────────────────────
class _StepWrapper extends StatelessWidget {
  final String icon;
  final String title;
  final String subtitle;
  final Widget child;

  const _StepWrapper({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(icon, style: const TextStyle(fontSize: 48))
              .animate()
              .fadeIn(duration: 300.ms)
              .slideY(begin: 0.2, end: 0),
          const SizedBox(height: 16),
          Text(title, style: AppTypography.strategyName)
              .animate()
              .fadeIn(delay: 50.ms, duration: 300.ms)
              .slideY(begin: 0.2, end: 0),
          const SizedBox(height: 6),
          Text(subtitle, style: AppTypography.bodyRegular)
              .animate()
              .fadeIn(delay: 100.ms, duration: 300.ms),
          const SizedBox(height: 32),
          child.animate().fadeIn(delay: 150.ms, duration: 350.ms).slideY(begin: 0.1, end: 0),
        ],
      ),
    );
  }
}
