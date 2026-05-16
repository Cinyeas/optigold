import 'package:flutter/material.dart';
import '../../../core/api/models/signal.dart';
import '../../../core/theme/colors.dart';
import '../../../core/theme/typography.dart';
import '../../../core/utils/formatters.dart';
import '../../../widgets/animated_number.dart';

/// Primary signal card — Style A (dark card + purple border + scan-line top)
class SignalCard extends StatelessWidget {
  final SignalModel signal;
  final bool isPrimary;
  final VoidCallback? onTap;

  const SignalCard({
    super.key,
    required this.signal,
    this.isPrimary = true,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        children: [
          // Outer: border + shadow only (no color — ClipRRect inside handles fill)
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: isPrimary ? AppColors.cardBorder : AppColors.divider,
              ),
              boxShadow: isPrimary
                  ? [
                      BoxShadow(
                        color: AppColors.primary.withOpacity(0.08),
                        blurRadius: 20,
                        offset: const Offset(0, 4),
                      )
                    ]
                  : null,
            ),
            // Inner: ClipRRect ensures scan-line + content are clipped to rounded rect
            child: ClipRRect(
              borderRadius: BorderRadius.circular(19),
              child: ColoredBox(
                color: AppColors.surface,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Scan-line (no borderRadius needed — ClipRRect clips it)
                    if (isPrimary)
                      Container(
                        height: 2,
                        decoration: BoxDecoration(gradient: AppColors.cardScanLine),
                      ),
                    Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildTopRow(),
                          const SizedBox(height: 4),
                          Text(signal.action, style: AppTypography.strategyName),
                          const SizedBox(height: 2),
                          _buildSubtitle(),
                          const SizedBox(height: 16),
                          _buildScoreRow(),
                          const SizedBox(height: 14),
                          _buildMetricsGrid(),
                          if (signal.reasoningPlain != null && signal.reasoningPlain!.isNotEmpty) ...[
                            const SizedBox(height: 14),
                            _buildPlainText(),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Badge top-right
          if (isPrimary)
            Positioned(
              top: 14,
              right: 14,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.badge,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Primary A',
                  style: AppTypography.chipLabel.copyWith(
                    color: Colors.white,
                    fontSize: 10,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTopRow() => Row(
        children: [
          Text(
            signal.instrument ?? 'GLD',
            style: AppTypography.sectionLabel.copyWith(color: AppColors.primary),
          ),
          const Spacer(),
          // space for badge
          const SizedBox(width: 80),
        ],
      );

  Widget _buildSubtitle() {
    final parts = <String>[];
    if (signal.expiry != null) parts.add(Fmt.dateShort(signal.expiry));
    if (signal.quantity != null) parts.add('${signal.quantity} contract${signal.quantity! > 1 ? "s" : ""}');
    if (parts.isEmpty) return const SizedBox.shrink();
    return Text(parts.join(' · '), style: AppTypography.bodyRegular.copyWith(fontSize: 12));
  }

  Widget _buildScoreRow() {
    final score = signal.score;
    final conf  = signal.confidence ?? 'medium';
    return Row(
      children: [
        AnimatedNumber(
          value: score,
          formatter: (v) => v.toStringAsFixed(0),
          style: AppTypography.scoreNumber,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Score', style: AppTypography.metricLabel),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: score / 100),
                  duration: const Duration(milliseconds: 1200),
                  curve: Curves.easeOut,
                  builder: (_, v, __) => LinearProgressIndicator(
                    value: v,
                    minHeight: 6,
                    backgroundColor: AppColors.divider,
                    valueColor: AlwaysStoppedAnimation(_scoreColor(score)),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: AppColors.confidenceColor(conf).withOpacity(0.12),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            conf.toUpperCase(),
            style: AppTypography.chipLabel.copyWith(
              color: AppColors.confidenceColor(conf),
              fontSize: 10,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMetricsGrid() {
    final items = <_MetricPair>[];
    if (signal.maxLoss != null)
      items.add(_MetricPair('Max Loss', Fmt.currency(signal.maxLoss), AppColors.loss));
    if (signal.maxProfit != null && signal.maxProfit! > 0)
      items.add(_MetricPair('Max Profit', Fmt.currency(signal.maxProfit), AppColors.profit));
    if (signal.probabilityOfProfit != null)
      items.add(_MetricPair('P(Profit)', Fmt.percent(signal.probabilityOfProfit), AppColors.textPrimary));
    if (signal.breakevenA != null)
      items.add(_MetricPair('Breakeven', Fmt.currency(signal.breakevenA), AppColors.textPrimary));

    if (items.isEmpty) return const SizedBox.shrink();

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 2.0,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      children: items.map((m) => _MetricCell(pair: m)).toList(),
    );
  }

  Widget _buildPlainText() => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(10),
          border: Border(left: BorderSide(color: AppColors.primary, width: 3)),
        ),
        child: Text(
          signal.reasoningPlain!,
          style: AppTypography.bodyRegular.copyWith(fontSize: 12),
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
        ),
      );

  Color _scoreColor(double s) {
    if (s >= 72) return AppColors.profit;
    if (s >= 55) return AppColors.primary;
    return AppColors.warning;
  }
}

class _MetricPair {
  final String label;
  final String value;
  final Color color;
  const _MetricPair(this.label, this.value, this.color);
}

class _MetricCell extends StatelessWidget {
  final _MetricPair pair;
  const _MetricCell({required this.pair});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.divider),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(pair.label, style: AppTypography.metricLabel),
            Text(pair.value, style: AppTypography.metricValue.copyWith(color: pair.color)),
          ],
        ),
      );
}
