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
import '../../widgets/loading_shimmer.dart';

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(signalHistoryProvider);
    final positionsAsync = ref.watch(positionsProvider);

    final body = historyAsync.when(
      data: (items) => items.isEmpty
          ? _EmptyState()
          : Column(
              children: [
                _HistoryStatsBar(signals: items, positions: positionsAsync.valueOrNull ?? []),
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, i) => _HistoryRow(
                      item: items[i],
                      index: i,
                      onTap: () => context.push('/signal/${items[i].id}'),
                    ),
                  ),
                ),
              ],
            ),
      loading: () => ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: 6,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (_, __) => const LoadingShimmer(width: double.infinity, height: 72, radius: 14),
      ),
      error: (e, _) => Center(
        child: Text('Error loading history', style: AppTypography.bodyRegular),
      ),
    );

    return Platform.isIOS
        ? CupertinoPageScaffold(
            backgroundColor: AppColors.background,
            navigationBar: const CupertinoNavigationBar(
              backgroundColor: AppColors.background,
              border: null,
              middle: Text('Signal History'),
            ),
            child: SafeArea(child: body),
          )
        : Scaffold(
            backgroundColor: AppColors.background,
            appBar: AppBar(title: const Text('Signal History')),
            body: body,
          );
  }
}

class _HistoryStatsBar extends StatelessWidget {
  final List<dynamic> signals;
  final List<dynamic> positions;
  const _HistoryStatsBar({required this.signals, required this.positions});

  @override
  Widget build(BuildContext context) {
    final total = signals.length;
    final actionable = signals.where((s) => s.action != 'no_trade').length;
    final executed = positions.length;
    final execRate = actionable > 0 ? executed / actionable : 0.0;

    final closed = positions.where((p) => p.isClosed).toList();
    final winners = closed.where((p) => (p.realizedPnl ?? 0.0) > 0).length;
    final winRate = closed.isNotEmpty ? winners / closed.length : null;
    final totalPnl = closed.fold<double>(0.0, (sum, p) => sum + (p.realizedPnl ?? 0.0));

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.divider),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _StatCell(label: '总信号', value: '$total'),
          _StatDivider(),
          _StatCell(
            label: '执行率',
            value: actionable > 0 ? '${(execRate * 100).toStringAsFixed(0)}%' : '--',
            sub: '$executed/$actionable',
          ),
          _StatDivider(),
          _StatCell(
            label: '胜率',
            value: winRate != null ? '${(winRate * 100).toStringAsFixed(0)}%' : '--',
            sub: closed.isNotEmpty ? '$winners/${closed.length}笔' : '暂无平仓',
            valueColor: winRate != null
                ? (winRate >= 0.55 ? AppColors.profit : AppColors.loss)
                : null,
          ),
          _StatDivider(),
          _StatCell(
            label: '累计P&L',
            value: totalPnl >= 0 ? '+\$${totalPnl.toStringAsFixed(0)}' : '-\$${(-totalPnl).toStringAsFixed(0)}',
            valueColor: totalPnl >= 0 ? AppColors.profit : AppColors.loss,
          ),
        ],
      ),
    );
  }
}

class _StatCell extends StatelessWidget {
  final String label;
  final String value;
  final String? sub;
  final Color? valueColor;
  const _StatCell({required this.label, required this.value, this.sub, this.valueColor});

  @override
  Widget build(BuildContext context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(value,
              style: AppTypography.metricValue.copyWith(
                fontSize: 16,
                color: valueColor ?? AppColors.textPrimary,
              )),
          Text(label, style: AppTypography.metricLabel),
          if (sub != null)
            Text(sub!, style: AppTypography.metricLabel.copyWith(fontSize: 9, color: AppColors.textMuted)),
        ],
      );
}

class _StatDivider extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Container(
        height: 32,
        width: 1,
        color: AppColors.divider,
      );
}

class _HistoryRow extends StatelessWidget {
  final item;
  final int index;
  final VoidCallback onTap;
  const _HistoryRow({required this.item, required this.index, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final conf = item.confidence ?? 'medium';
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.divider),
        ),
        child: Row(
          children: [
            // Score circle
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.1),
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.primary.withOpacity(0.3)),
              ),
              child: Center(
                child: Text(
                  item.compositeScore?.toStringAsFixed(0) ?? '--',
                  style: AppTypography.metricValue.copyWith(color: AppColors.primary, fontSize: 13),
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Strategy + time
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.action, style: AppTypography.bodyMedium, overflow: TextOverflow.ellipsis),
                  Text(Fmt.timeAgo(item.generatedAt), style: AppTypography.metricLabel),
                ],
              ),
            ),
            // Confidence chip
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.confidenceColor(conf).withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                conf.toUpperCase(),
                style: AppTypography.chipLabel.copyWith(
                  color: AppColors.confidenceColor(conf),
                  fontSize: 9,
                ),
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right, color: AppColors.textMuted, size: 18),
          ],
        ),
      ).animate().fadeIn(delay: (index * 40).ms).slideY(begin: 0.05, end: 0),
    );
  }
}

class _EmptyState extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('📋', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 16),
            Text('No signals yet', style: AppTypography.bodyMedium),
            Text('Generate your first signal from the home screen',
                style: AppTypography.bodyRegular, textAlign: TextAlign.center),
          ],
        ),
      );
}
