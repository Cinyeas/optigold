import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/colors.dart';
import '../../core/theme/typography.dart';
import '../../core/utils/formatters.dart';
import '../../providers/signal_provider.dart';
import '../../providers/position_provider.dart';
import '../../providers/profile_provider.dart';
import '../../widgets/loading_shimmer.dart';
import 'widgets/score_ring.dart';

class SignalDetailScreen extends ConsumerWidget {
  final String signalId;
  const SignalDetailScreen({super.key, required this.signalId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signalAsync = ref.watch(signalDetailProvider(signalId));

    return Scaffold(
      backgroundColor: AppColors.background,
      body: signalAsync.when(
        data: (signal) => _DetailBody(signal: signal),
        loading: () => const _DetailSkeleton(),
        error: (e, _) => _ErrorView(error: e.toString()),
      ),
    );
  }
}

class _DetailBody extends ConsumerStatefulWidget {
  final signal;
  const _DetailBody({required this.signal});

  @override
  ConsumerState<_DetailBody> createState() => _DetailBodyState();
}

class _DetailBodyState extends ConsumerState<_DetailBody> {
  bool _showDetail = false;
  bool _confirming = false;

  @override
  Widget build(BuildContext context) {
    final s = widget.signal;

    return CustomScrollView(
      slivers: [
        // App bar
        SliverAppBar(
          backgroundColor: AppColors.background,
          surfaceTintColor: Colors.transparent,
          pinned: true,
          leading: IconButton(
            icon: Icon(
              Platform.isIOS ? CupertinoIcons.back : Icons.arrow_back,
              color: AppColors.primary,
            ),
            onPressed: () => context.pop(),
          ),
          title: Text(
            'Signal Detail',
            style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
          ),
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Text(
                Fmt.timeAgo(s.generatedAt),
                style: AppTypography.metricLabel,
              ),
            ),
          ],
        ),

        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          sliver: SliverList(
            delegate: SliverChildListDelegate([
              // Score ring + strategy name
              _buildHero(s),
              const SizedBox(height: 24),

              // Strategy parameters card
              _SectionCard(
                title: 'Trade Parameters',
                child: _buildParams(s),
              ).animate().fadeIn(delay: 100.ms).slideY(begin: 0.05, end: 0),
              const SizedBox(height: 12),

              // Financial summary card
              _SectionCard(
                title: 'Risk & Reward',
                child: _buildFinancials(s, ref.watch(profileProvider).valueOrNull?.experienceLevel ?? 'intermediate'),
              ).animate().fadeIn(delay: 150.ms).slideY(begin: 0.05, end: 0),
              const SizedBox(height: 12),

              // Scenarios card
              _SectionCard(
                title: '3 Scenarios',
                child: _buildScenarios(s),
              ).animate().fadeIn(delay: 200.ms).slideY(begin: 0.05, end: 0),
              const SizedBox(height: 12),

              // Reasoning
              _ReasoningSection(
                plain: s.reasoningPlain,
                detail: s.reasoningDetail,
                showDetail: _showDetail,
                onToggle: () => setState(() => _showDetail = !_showDetail),
              ).animate().fadeIn(delay: 250.ms),
              const SizedBox(height: 12),

              // Alt signal (if any)
              if (s.altSignal != null) ...[
                _AltSignalSection(alt: s.altSignal!),
                const SizedBox(height: 12),
              ],

              // Greeks (advanced)
              if (s.greeks != null && s.greeks!.isNotEmpty) ...[
                _GreeksSection(greeks: s.greeks!),
                const SizedBox(height: 12),
              ],

              // Confirm trade button
              _ConfirmButton(
                signal: s,
                confirming: _confirming,
                onConfirm: () => _confirmTrade(context, s),
              ).animate().fadeIn(delay: 300.ms),

              const SizedBox(height: 40),
            ]),
          ),
        ),
      ],
    );
  }

  Widget _buildHero(s) {
    return Row(
      children: [
        ScoreRing(score: s.score)
            .animate()
            .fadeIn(duration: 400.ms)
            .scaleXY(begin: 0.8, end: 1, curve: Curves.elasticOut),
        const SizedBox(width: 18),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Instrument + regime
              Row(
                children: [
                  Text(
                    s.instrument ?? 'GLD',
                    style: AppTypography.sectionLabel.copyWith(color: AppColors.primary),
                  ),
                  const SizedBox(width: 8),
                  if (s.confidence != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.confidenceColor(s.confidence!).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        s.confidence!.toUpperCase(),
                        style: AppTypography.chipLabel.copyWith(
                          color: AppColors.confidenceColor(s.confidence!),
                          fontSize: 9,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                s.action,
                style: AppTypography.strategyName.copyWith(fontSize: 18),
              ),
              if (s.marketBias != null)
                Text(
                  s.formattedRegime,
                  style: AppTypography.bodyRegular.copyWith(fontSize: 12),
                ),
            ],
          ).animate().fadeIn(delay: 50.ms).slideX(begin: 0.05, end: 0),
        ),
      ],
    );
  }

  Widget _buildParams(s) {
    return _GridMetrics(items: [
      if (s.strikeA != null)   _MI('Strike',   Fmt.currency(s.strikeA),  AppColors.gold),
      if (s.strikeB != null)   _MI('Strike B', Fmt.currency(s.strikeB),  AppColors.gold),
      if (s.expiry != null)    _MI('Expiry',   Fmt.date(s.expiry),       AppColors.textPrimary),
      if (s.quantity != null)  _MI('Qty',      '${s.quantity} contracts',AppColors.textPrimary),
    ]);
  }

  Widget _buildFinancials(s, String experienceLevel) {
    final isBeginner = experienceLevel == 'beginner';
    return _GridMetrics(items: [
      if (s.maxLoss   != null) _MI('Max Loss',   Fmt.currency(s.maxLoss),   AppColors.loss),
      if (s.maxProfit != null && s.maxProfit! > 0)
                               _MI('Max Profit', Fmt.currency(s.maxProfit), AppColors.profit),
      if (s.premiumCollected != null && s.premiumCollected! > 0)
                               _MI('Premium',    Fmt.currency(s.premiumCollected), AppColors.profit),
      if (s.breakevenA != null)_MI('Breakeven',  Fmt.currency(s.breakevenA),AppColors.textPrimary),
      if (s.probabilityOfProfit != null)
                               _MI('P(Profit)',  Fmt.percent(s.probabilityOfProfit), AppColors.textPrimary),
      if (s.kellyFraction != null && !isBeginner)
                               _MI('仓位上限 (Kelly)', Fmt.percent(s.kellyFraction! * 100), AppColors.textSecondary,
                                   subtitle: '⚠ 理论值，实际建议 ≤ 25%'),
      if (s.kellyFraction != null && isBeginner)
                               _MI('建议仓位', '1 合约起步', AppColors.textSecondary),
    ]);
  }

  Widget _buildScenarios(s) {
    return Row(
      children: [
        _ScenarioCell(
          label: 'Bear 🐻',
          desc: 'GLD drops >5%\nMax loss: ${Fmt.currency(s.maxLoss)}',
          color: AppColors.loss,
        ),
        const SizedBox(width: 8),
        _ScenarioCell(
          label: 'Base 📊',
          desc: 'GLD stays flat\nPartial profit',
          color: AppColors.primary,
        ),
        const SizedBox(width: 8),
        _ScenarioCell(
          label: 'Bull 🚀',
          desc: 'GLD rallies\nMax profit: ${s.maxProfit != null && s.maxProfit! > 0 ? Fmt.currency(s.maxProfit) : "Unlimited"}',
          color: AppColors.profit,
        ),
      ],
    );
  }

  Future<void> _confirmTrade(BuildContext context, s) async {
    final priceController = TextEditingController();
    final result = await showDialog<(bool, double?)>(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: Text('Confirm Trade', style: AppTypography.bodyMedium),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Record that you\'ve executed:\n${s.action}',
                style: AppTypography.bodyRegular,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: priceController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: '实际成交价（可选）',
                  hintText: s.premiumCollected != null ? '${s.premiumCollected}' : '0.00',
                  prefixText: '\$',
                  isDense: true,
                  border: const OutlineInputBorder(),
                  labelStyle: AppTypography.metricLabel,
                ),
                style: AppTypography.bodyRegular,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, (false, null)),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final price = double.tryParse(priceController.text.trim());
                Navigator.pop(ctx, (true, price));
              },
              child: const Text('Confirm'),
            ),
          ],
        ),
      ),
    );
    priceController.dispose();

    final confirmed = result?.$1 ?? false;
    final entryPrice = result?.$2;

    if (confirmed && mounted) {
      setState(() => _confirming = true);
      try {
        await ref.read(positionsProvider.notifier).confirmTrade(
          signalId:   s.id,
          instrument: s.instrument ?? 'GLD',
          strategy:   s.marketRegime ?? 'unknown',
          strikeA:    s.strikeA,
          strikeB:    s.strikeB,
          expiry:     s.expiry,
          quantity:   s.quantity,
          entryPrice: entryPrice,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Trade recorded in Positions')),
          );
          context.go('/positions');
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
      } finally {
        if (mounted) setState(() => _confirming = false);
      }
    }
  }
}

// ── Sub-widgets ─────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget child;
  const _SectionCard({required this.title, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.divider),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: AppTypography.sectionLabel.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: 14),
            child,
          ],
        ),
      );
}

typedef _MI = _MetricItem;

class _MetricItem {
  final String label;
  final String value;
  final Color color;
  final String? subtitle;
  const _MetricItem(this.label, this.value, this.color, {this.subtitle});
}

class _GridMetrics extends StatelessWidget {
  final List<_MetricItem> items;
  const _GridMetrics({required this.items});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: subtitle(items) ? 2.0 : 2.4,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      children: items.map((m) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.divider),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(m.label, style: AppTypography.metricLabel),
            Text(m.value, style: AppTypography.metricValue.copyWith(color: m.color, fontSize: 15)),
            if (m.subtitle != null)
              Text(m.subtitle!, style: AppTypography.metricLabel.copyWith(fontSize: 10, color: AppColors.textSecondary)),
          ],
        ),
      )).toList(),
    );
  }

  static bool subtitle(List<_MetricItem> items) => items.any((m) => m.subtitle != null);
}

class _ScenarioCell extends StatelessWidget {
  final String label;
  final String desc;
  final Color color;
  const _ScenarioCell({required this.label, required this.desc, required this.color});

  @override
  Widget build(BuildContext context) => Expanded(
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: color.withOpacity(0.06),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withOpacity(0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: AppTypography.chipLabel.copyWith(color: color)),
              const SizedBox(height: 6),
              Text(desc, style: AppTypography.metricLabel.copyWith(height: 1.5)),
            ],
          ),
        ),
      );
}

class _ReasoningSection extends StatelessWidget {
  final String? plain;
  final String? detail;
  final bool showDetail;
  final VoidCallback onToggle;
  const _ReasoningSection({
    this.plain, this.detail, required this.showDetail, required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    if (plain == null && detail == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('Reasoning', style: AppTypography.sectionLabel.copyWith(color: AppColors.textSecondary)),
              const Spacer(),
              if (detail != null)
                GestureDetector(
                  onTap: onToggle,
                  child: Text(
                    showDetail ? 'Simple ↑' : 'Advanced ↓',
                    style: AppTypography.chipLabel.copyWith(color: AppColors.primary),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            showDetail ? (detail ?? plain ?? '') : (plain ?? ''),
            style: AppTypography.bodyRegular,
          ),
        ],
      ),
    );
  }
}

class _AltSignalSection extends StatelessWidget {
  final Map<String, dynamic> alt;
  const _AltSignalSection({required this.alt});

  @override
  Widget build(BuildContext context) {
    final strategy = (alt['strategy'] as String? ?? '').replaceAll('_', ' ').toUpperCase();
    final score    = (alt['composite_score'] as num?)?.toDouble();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Alternative B', style: AppTypography.sectionLabel.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: Text(strategy, style: AppTypography.bodyMedium)),
              if (score != null)
                Text('${score.toStringAsFixed(0)}/100',
                    style: AppTypography.metricLabel),
            ],
          ),
        ],
      ),
    );
  }
}

class _GreeksSection extends StatelessWidget {
  final Map<String, dynamic> greeks;
  const _GreeksSection({required this.greeks});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      collapsedBackgroundColor: AppColors.surface,
      backgroundColor: AppColors.surface,
      collapsedShape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: AppColors.divider),
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: AppColors.divider),
      ),
      title: Text('Greeks (Advanced)', style: AppTypography.sectionLabel.copyWith(color: AppColors.textSecondary)),
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.4,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            children: greeks.entries.map((e) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.divider),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(e.key.toUpperCase(), style: AppTypography.metricLabel),
                  Text(
                    (e.value as num).toStringAsFixed(4),
                    style: AppTypography.metricValue.copyWith(fontSize: 13),
                  ),
                ],
              ),
            )).toList(),
          ),
        ),
      ],
    );
  }
}

class _ConfirmButton extends StatelessWidget {
  final signal;
  final bool confirming;
  final VoidCallback onConfirm;
  const _ConfirmButton({required this.signal, required this.confirming, required this.onConfirm});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: AppColors.primary.withOpacity(0.3), blurRadius: 16, offset: const Offset(0, 4)),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: confirming ? null : onConfirm,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Center(
              child: confirming
                  ? const SizedBox(
                      width: 20, height: 20,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                    )
                  : const Text(
                      '✓  I\'ve Executed This Trade',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.3,
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DetailSkeleton extends StatelessWidget {
  const _DetailSkeleton();
  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(24),
    child: Column(
      children: [
        LoadingShimmer(width: double.infinity, height: 80, radius: 20),
        SizedBox(height: 16),
        LoadingShimmer(width: double.infinity, height: 140, radius: 18),
        SizedBox(height: 12),
        LoadingShimmer(width: double.infinity, height: 120, radius: 18),
      ],
    ),
  );
}

class _ErrorView extends StatelessWidget {
  final String error;
  const _ErrorView({required this.error});
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline, color: AppColors.loss, size: 48),
        const SizedBox(height: 16),
        Text('Failed to load signal', style: AppTypography.bodyMedium),
        Text(error, style: AppTypography.bodyRegular),
      ],
    ),
  );
}
