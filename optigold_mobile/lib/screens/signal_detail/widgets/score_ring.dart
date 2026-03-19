import 'dart:math';
import 'package:flutter/material.dart';
import '../../../core/theme/colors.dart';
import '../../../core/theme/typography.dart';

/// Animated circular arc showing composite score (0–100).
/// Draws from 0 to the target score with easeOut curve.
class ScoreRing extends StatefulWidget {
  final double score;
  final double size;

  const ScoreRing({super.key, required this.score, this.size = 80});

  @override
  State<ScoreRing> createState() => _ScoreRingState();
}

class _ScoreRingState extends State<ScoreRing> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    _anim = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => SizedBox(
        width: widget.size,
        height: widget.size,
        child: CustomPaint(
          painter: _RingPainter(
            progress: _anim.value * (widget.score / 100),
            score: widget.score,
          ),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  (_anim.value * widget.score).toStringAsFixed(0),
                  style: AppTypography.scoreNumber.copyWith(
                    fontSize: widget.size * 0.26,
                  ),
                ),
                Text(
                  '/100',
                  style: AppTypography.metricLabel.copyWith(fontSize: widget.size * 0.11),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double progress; // 0.0 – 1.0
  final double score;

  const _RingPainter({required this.progress, required this.score});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width / 2) - 6;
    const startAngle = -pi / 2; // top
    final sweepAngle = 2 * pi * progress;

    // Background track
    final trackPaint = Paint()
      ..color = AppColors.divider
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, trackPaint);

    // Foreground arc
    final arcColor = _arcColor(score);
    final arcPaint = Paint()
      ..shader = SweepGradient(
        startAngle: startAngle,
        endAngle:   startAngle + 2 * pi,
        colors:     [arcColor, arcColor.withOpacity(0.7)],
      ).createShader(Rect.fromCircle(center: center, radius: radius))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      arcPaint,
    );
  }

  Color _arcColor(double s) {
    if (s >= 72) return AppColors.profit;
    if (s >= 55) return AppColors.primary;
    return AppColors.warning;
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.progress != progress;
}
