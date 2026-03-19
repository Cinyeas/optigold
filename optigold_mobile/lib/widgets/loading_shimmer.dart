import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../core/theme/colors.dart';

class LoadingShimmer extends StatelessWidget {
  final double width;
  final double height;
  final double radius;

  const LoadingShimmer({
    super.key,
    required this.width,
    required this.height,
    this.radius = 8,
  });

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor:  AppColors.surface,
      highlightColor: AppColors.surfaceElevated,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(radius),
        ),
      ),
    );
  }
}

/// Full card skeleton for signal card loading state
class SignalCardSkeleton extends StatelessWidget {
  const SignalCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor:     AppColors.surface,
      highlightColor: AppColors.surfaceElevated,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        padding: const EdgeInsets.all(20),
        height: 200,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(20),
        ),
      ),
    );
  }
}
