import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/api/models/market_snapshot.dart';
import '../../core/api/models/signal.dart';
import '../../core/theme/colors.dart';
import '../../core/theme/typography.dart';
import '../../providers/signal_provider.dart';
import '../../providers/market_provider.dart';
import '../../widgets/loading_shimmer.dart';
import 'widgets/market_header.dart';
import 'widgets/signal_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<SignalModel> signalAsync = ref.watch(latestSignalProvider);
    final AsyncValue<MarketSnapshot> marketAsync = ref.watch(marketSnapshotProvider);

    return Platform.isIOS ? _buildIOS(context, ref, signalAsync, marketAsync)
                          : _buildAndroid(context, ref, signalAsync, marketAsync);
  }

  Widget _buildIOS(BuildContext context, WidgetRef ref,
      AsyncValue<SignalModel> signalAsync, AsyncValue<MarketSnapshot> marketAsync) =>
      CupertinoPageScaffold(
        backgroundColor: AppColors.background,
        navigationBar: CupertinoNavigationBar(
          backgroundColor: AppColors.background,
          border: null,
          middle: Text(
            'OptiGold',
            style: AppTypography.actionText.copyWith(color: AppColors.primary, letterSpacing: 1.5),
          ),
          trailing: CupertinoButton(
            padding: EdgeInsets.zero,
            onPressed: () => _refresh(ref),
            child: const Icon(CupertinoIcons.refresh, color: AppColors.primary, size: 20),
          ),
        ),
        child: _body(context, ref, signalAsync, marketAsync),
      );

  Widget _buildAndroid(BuildContext context, WidgetRef ref,
      AsyncValue<SignalModel> signalAsync, AsyncValue<MarketSnapshot> marketAsync) =>
      Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          title: Text(
            'OptiGold',
            style: AppTypography.actionText.copyWith(color: AppColors.primary, letterSpacing: 1.5),
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh, color: AppColors.primary),
              onPressed: () => _refresh(ref),
            ),
          ],
        ),
        body: _body(context, ref, signalAsync, marketAsync),
      );

  Widget _body(BuildContext context, WidgetRef ref,
      AsyncValue<SignalModel> signalAsync, AsyncValue<MarketSnapshot> marketAsync) =>
      RefreshIndicator(
        color: AppColors.primary,
        backgroundColor: AppColors.surface,
        onRefresh: () async => _refresh(ref),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            // Market header
            marketAsync.when(
              data: (m) => MarketHeader(snapshot: m)
                  .animate()
                  .fadeIn(duration: 400.ms)
                  .slideY(begin: -0.05, end: 0),
              loading: () => const _MarketHeaderSkeleton(),
              error:   (_, __) => const _MarketHeaderError(),
            ),

            const SizedBox(height: 8),

            // Primary signal card
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: signalAsync.when(
                data: (signal) => Column(
                  children: [
                    // Primary recommendation (or no-trade card)
                    if (signal.action.toLowerCase() == 'no_trade')
                      _NoTradeCard(signal: signal).animate()
                    else
                    SignalCard(
                      signal: signal,
                      isPrimary: true,
                      onTap: () => context.push('/signal/${signal.id}'),
                    ).animate()
                     .fadeIn(delay: 100.ms, duration: 500.ms)
                     .slideY(begin: 0.08, end: 0, curve: Curves.easeOutCubic),

                    // Alt signal if present
                    if (signal.altSignal != null) ...[
                      const SizedBox(height: 12),
                      _AltSignalCard(alt: signal.altSignal!)
                          .animate()
                          .fadeIn(delay: 200.ms, duration: 400.ms)
                          .slideY(begin: 0.08, end: 0),
                    ],
                  ],
                ),
                loading: () => const SignalCardSkeleton(),
                error:   (e, _) => _SignalError(onRetry: () => ref.invalidate(latestSignalProvider)),
              ),
            ),

            const SizedBox(height: 20),

            // Market indicators row
            marketAsync.whenData((m) => _MarketIndicatorsRow(snapshot: m)).valueOrNull
                ?? const SizedBox.shrink(),

            const SizedBox(height: 24),

            // Refresh button (Android-style FAB inline)
            if (!Platform.isIOS)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: const BorderSide(color: AppColors.primary, width: 1),
                    minimumSize: const Size.fromHeight(48),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.auto_awesome, size: 16),
                  label: const Text('Generate New Signal'),
                  onPressed: () => _refresh(ref),
                ),
              ),

            const SizedBox(height: 32),
          ],
        ),
      );

  void _refresh(WidgetRef ref) {
    ref.invalidate(latestSignalProvider);
    ref.invalidate(marketSnapshotProvider);
  }
}

class _AltSignalCard extends StatelessWidget {
  final Map<String, dynamic> alt;
  const _AltSignalCard({required this.alt});

  @override
  Widget build(BuildContext context) {
    final strategy = (alt['strategy'] as String? ?? '').replaceAll('_', ' ').toUpperCase();
    final score    = (alt['composite_score'] as num?)?.toDouble();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.divider),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.surfaceElevated,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text('Alt B', style: AppTypography.chipLabel.copyWith(color: AppColors.textSecondary)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(strategy, style: AppTypography.bodyMedium),
          ),
          if (score != null)
            Text(
              '${score.toStringAsFixed(0)}/100',
              style: AppTypography.metricLabel.copyWith(color: AppColors.textSecondary),
            ),
        ],
      ),
    );
  }
}

class _MarketIndicatorsRow extends StatelessWidget {
  final snapshot;
  const _MarketIndicatorsRow({required this.snapshot});

  @override
  Widget build(BuildContext context) {
    final items = <_IndicatorItem>[
      if (snapshot.rsi14 != null)
        _IndicatorItem('RSI(14)', snapshot.rsi14!.toStringAsFixed(1),
            _rsiColor(snapshot.rsi14!)),
      if (snapshot.adx != null)
        _IndicatorItem('ADX', snapshot.adx!.toStringAsFixed(1), AppColors.textSecondary),
      if (snapshot.ema20 != null && snapshot.ema50 != null)
        _IndicatorItem(
          'EMA20/50',
          snapshot.ema20! > snapshot.ema50! ? '↑ Bull' : '↓ Bear',
          snapshot.ema20! > snapshot.ema50! ? AppColors.profit : AppColors.loss,
        ),
      if (snapshot.ivPremiumRatio != null)
        _IndicatorItem('IV/HV', '${snapshot.ivPremiumRatio!.toStringAsFixed(2)}x',
            AppColors.textSecondary),
    ];

    if (items.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: 72,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) => _IndicatorChip(item: items[i]),
      ),
    );
  }

  Color _rsiColor(double rsi) {
    if (rsi > 70) return AppColors.loss;
    if (rsi < 30) return AppColors.profit;
    return AppColors.textSecondary;
  }
}

class _IndicatorItem {
  final String label;
  final String value;
  final Color color;
  const _IndicatorItem(this.label, this.value, this.color);
}

class _IndicatorChip extends StatelessWidget {
  final _IndicatorItem item;
  const _IndicatorChip({required this.item});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(item.label, style: AppTypography.metricLabel),
          const SizedBox(height: 2),
          Text(item.value, style: AppTypography.metricValue.copyWith(color: item.color, fontSize: 14)),
        ],
      ),
    );
  }
}

class _MarketHeaderSkeleton extends StatelessWidget {
  const _MarketHeaderSkeleton();
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const LoadingShimmer(width: 100, height: 12),
            const SizedBox(height: 8),
            const LoadingShimmer(width: 200, height: 44),
            const SizedBox(height: 8),
            Row(children: const [
              LoadingShimmer(width: 80, height: 28),
              SizedBox(width: 10),
              LoadingShimmer(width: 80, height: 28),
              SizedBox(width: 10),
              LoadingShimmer(width: 80, height: 28),
            ]),
          ],
        ),
      );
}

class _MarketHeaderError extends StatelessWidget {
  const _MarketHeaderError();
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Text('Market data unavailable', style: AppTypography.bodyRegular),
      );
}

class _NoTradeCard extends StatelessWidget {
  final SignalModel signal;
  const _NoTradeCard({required this.signal});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.orange.withOpacity(0.6), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.pause_circle_outline, color: Colors.orange, size: 20),
              const SizedBox(width: 8),
              Text(
                '观望 · No Trade Recommended',
                style: AppTypography.bodyMedium.copyWith(color: Colors.orange),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            signal.reasoningPlain ?? '当前市场条件不适合新建仓位。',
            style: AppTypography.bodyRegular.copyWith(
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          if (signal.altSignal != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: AppColors.textMuted, size: 14),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '参考备选 (仅供研究): '
                      '${(signal.altSignal!['strategy'] as String? ?? '').replaceAll('_', ' ').toUpperCase()}',
                      style: AppTypography.metricLabel.copyWith(color: AppColors.textMuted),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SignalError extends StatelessWidget {
  final VoidCallback onRetry;
  const _SignalError({required this.onRetry});
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.divider),
        ),
        child: Column(
          children: [
            const Icon(Icons.wifi_off, color: AppColors.textMuted, size: 40),
            const SizedBox(height: 12),
            Text('Could not load signal', style: AppTypography.bodyMedium),
            Text('Make sure the backend is running', style: AppTypography.bodyRegular),
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
}
