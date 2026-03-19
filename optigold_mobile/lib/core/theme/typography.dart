import 'package:flutter/material.dart';
import 'colors.dart';

class AppTypography {
  AppTypography._();

  // Numbers — monospaced feel for financial data
  static const TextStyle priceHero = TextStyle(
    fontSize: 42,
    fontWeight: FontWeight.w700,
    color: AppColors.gold,
    letterSpacing: -2,
    height: 1.0,
  );

  static const TextStyle priceNormal = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: -0.5,
  );

  static const TextStyle scoreNumber = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w800,
    color: AppColors.primary,
    letterSpacing: -1,
  );

  static const TextStyle metricValue = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  // Labels
  static const TextStyle sectionLabel = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: AppColors.textMuted,
    letterSpacing: 1.2,
  );

  static const TextStyle metricLabel = TextStyle(
    fontSize: 10,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    letterSpacing: 0.8,
  );

  // Body
  static const TextStyle bodyRegular = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
    height: 1.65,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    color: AppColors.textPrimary,
  );

  // Strategy / action
  static const TextStyle strategyName = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: 0.2,
  );

  static const TextStyle actionText = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: 0.5,
  );

  // Nav / chip
  static const TextStyle navLabel = TextStyle(
    fontSize: 10,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.3,
  );

  static const TextStyle chipLabel = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
  );
}
