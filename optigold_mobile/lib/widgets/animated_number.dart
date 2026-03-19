import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

/// Animates a numeric value from 0 to [value], displaying it
/// with the given [formatter] (e.g. '\$449.23' or '58.3').
class AnimatedNumber extends StatelessWidget {
  final double value;
  final String Function(double) formatter;
  final TextStyle? style;
  final Duration duration;

  const AnimatedNumber({
    super.key,
    required this.value,
    required this.formatter,
    this.style,
    this.duration = const Duration(milliseconds: 1200),
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value),
      duration: duration,
      curve: Curves.easeOut,
      builder: (_, v, __) => Text(formatter(v), style: style),
    );
  }
}

/// Pulsing dot indicator (used in regime chips)
class PulsingDot extends StatelessWidget {
  final Color color;
  final double size;
  const PulsingDot({super.key, required this.color, this.size = 8});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    )
        .animate(onPlay: (c) => c.repeat())
        .scaleXY(begin: 1, end: 1.4, duration: 800.ms, curve: Curves.easeInOut)
        .then()
        .scaleXY(begin: 1.4, end: 1, duration: 800.ms, curve: Curves.easeInOut);
  }
}
