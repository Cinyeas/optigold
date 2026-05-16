import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // ── Background layers ────────────────────────────────────
  static const Color background = Color(0xFF080808);
  static const Color surface = Color(0xFF111111);
  static const Color surfaceElevated = Color(0xFF1A1A1A);
  static const Color divider = Color(0xFF1E1E1E);

  // ── Primary — Purple (confirmed design choice) ───────────
  static const Color primary = Color(0xFF6C63FF);
  static const Color primaryDark = Color(0xFF4E46E5);
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF6C63FF), Color(0xFF4E46E5)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // Card accent: purple border + top scan line
  static const Color cardBorder = Color(0xFF6C63FF);
  static const LinearGradient cardScanLine = LinearGradient(
    colors: [Color(0xFF6C63FF), Color(0xFF4E46E5), Color(0x006C63FF)],
    stops: [0.0, 0.5, 1.0],
  );

  // ── Gold accent — price numbers only ────────────────────
  static const Color gold = Color(0xFFFFD700);
  static const Color goldSoft = Color(0xFFF5A623);

  // ── Semantic colours ─────────────────────────────────────
  static const Color profit = Color(0xFF00E676);  // green
  static const Color loss   = Color(0xFFFF1744);  // red
  static const Color warning = Color(0xFFFFAB00);

  // ── Text ─────────────────────────────────────────────────
  static const Color textPrimary   = Color(0xFFFFFFFF);
  static const Color textSecondary = Color(0xFF888888);
  static const Color textMuted     = Color(0xFF444444);

  // ── Badge ────────────────────────────────────────────────
  static const Color badge = Color(0xFF6C63FF);

  // ── Confidence tiers ─────────────────────────────────────
  static Color confidenceColor(String level) {
    switch (level.toLowerCase()) {
      case 'high':   return profit;
      case 'medium': return goldSoft;
      default:       return textSecondary;
    }
  }
}
