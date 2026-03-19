import 'package:flutter/material.dart';
import '../../../core/api/models/market_snapshot.dart';
import '../../../core/theme/colors.dart';
import '../../../core/theme/typography.dart';
import '../../../core/utils/formatters.dart';
import '../../../widgets/animated_number.dart';

class MarketHeader extends StatelessWidget {
  final MarketSnapshot snapshot;
  const MarketHeader({super.key, required this.snapshot});

  @override
  Widget build(BuildContext context) {
    final isUp = (snapshot.gld24hChangePct ?? 0) >= 0;

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.background,
            AppColors.primary.withOpacity(0.04),
          ],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Instrument label
          Text(
            'GLD · SPDR Gold ETF',
            style: AppTypography.sectionLabel,
          ),
          const SizedBox(height: 8),

          // Price + change row
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              // Animated price
              AnimatedNumber(
                value: snapshot.gldPrice ?? 0,
                formatter: (v) => '\$${v.toStringAsFixed(2)}',
                style: AppTypography.priceHero,
                duration: const Duration(milliseconds: 1000),
              ),
              const SizedBox(width: 12),
              // Change pill
              if (snapshot.gld24hChangePct != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: (isUp ? AppColors.profit : AppColors.loss).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${isUp ? "▲" : "▼"} ${Fmt.priceChange(snapshot.gld24hChangePct)}',
                    style: AppTypography.chipLabel.copyWith(
                      color: isUp ? AppColors.profit : AppColors.loss,
                    ),
                  ),
                ),
            ],
          ),

          const SizedBox(height: 14),

          // Chips row: regime + IV rank + session
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              if (snapshot.marketRegime != null)
                _RegimeChip(regime: snapshot.formattedRegime, isBull: snapshot.isBullish),
              if (snapshot.gldIvRank != null)
                _MetricChip(
                  label: 'IV Rank',
                  value: snapshot.gldIvRank!.toStringAsFixed(0),
                  color: _ivRankColor(snapshot.gldIvRank!),
                ),
              if (snapshot.rsi14 != null)
                _MetricChip(
                  label: 'RSI',
                  value: snapshot.rsi14!.toStringAsFixed(1),
                  color: AppColors.textSecondary,
                ),
            ],
          ),
        ],
      ),
    );
  }

  Color _ivRankColor(double ivr) {
    if (ivr >= 70) return AppColors.profit;   // High IV → good for selling
    if (ivr >= 40) return AppColors.goldSoft;
    return AppColors.textSecondary;
  }
}

class _RegimeChip extends StatelessWidget {
  final String regime;
  final bool isBull;
  const _RegimeChip({required this.regime, required this.isBull});

  @override
  Widget build(BuildContext context) {
    final color = isBull ? AppColors.profit : AppColors.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          PulsingDot(color: color, size: 6),
          const SizedBox(width: 6),
          Text(regime, style: AppTypography.chipLabel.copyWith(color: color)),
        ],
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _MetricChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.divider),
      ),
      child: Text(
        '$label $value',
        style: AppTypography.chipLabel.copyWith(color: color),
      ),
    );
  }
}
