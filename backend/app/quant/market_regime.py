from __future__ import annotations

"""Market regime detection based on technical and volatility indicators."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketRegime:
    """Encapsulates the detected market regime and supporting evidence."""

    regime: str  # e.g. "low_vol_trend_up", "high_vol_range", "crash"
    bias: str    # "bullish", "bearish", "neutral"
    confidence: float  # 0.0 – 1.0

    # Supporting sub-signals
    trend_signal: str = "neutral"   # "up", "down", "flat"
    vol_signal: str = "normal"      # "low", "normal", "high", "extreme"
    momentum_signal: str = "neutral"  # "overbought", "neutral", "oversold"
    adx_signal: str = "weak"        # "weak", "moderate", "strong"

    description: str = ""


def detect_regime(snapshot: dict[str, Any]) -> MarketRegime:
    """
    Classify current market into a named regime from a market snapshot dict.

    Expected keys (all optional; defaults applied when missing):
        gld_price, ema20, ema50, rsi_14, adx, gld_iv_rank,
        vix_level, gld_24h_change_pct, put_call_skew

    Returns:
        MarketRegime dataclass.
    """
    price: float = float(snapshot.get("gld_price") or 220.0)
    ema20: float = float(snapshot.get("ema20") or price)
    ema50: float = float(snapshot.get("ema50") or price)
    rsi: float = float(snapshot.get("rsi_14") or 50.0)
    adx: float = float(snapshot.get("adx") or 20.0)
    iv_rank: float = float(snapshot.get("gld_iv_rank") or 50.0)
    vix: float = float(snapshot.get("vix_level") or 20.0)
    change_pct: float = float(snapshot.get("gld_24h_change_pct") or 0.0)
    skew: float = float(snapshot.get("put_call_skew") or 0.0)

    # ── Trend signal ──────────────────────────────────────────────────────────
    if price > ema20 > ema50:
        trend_signal = "up"
    elif price < ema20 < ema50:
        trend_signal = "down"
    else:
        trend_signal = "flat"

    # ── Volatility signal ─────────────────────────────────────────────────────
    if iv_rank >= 75 or vix >= 30:
        vol_signal = "high"
    elif iv_rank >= 50 or vix >= 22:
        vol_signal = "normal"
    elif vix >= 35 or iv_rank >= 85:
        vol_signal = "extreme"
    else:
        vol_signal = "low"

    # ── Momentum (RSI) ────────────────────────────────────────────────────────
    if rsi >= 70:
        momentum_signal = "overbought"
    elif rsi <= 30:
        momentum_signal = "oversold"
    else:
        momentum_signal = "neutral"

    # ── Trend strength (ADX) ──────────────────────────────────────────────────
    if adx >= 30:
        adx_signal = "strong"
    elif adx >= 20:
        adx_signal = "moderate"
    else:
        adx_signal = "weak"

    # ── Crash / crisis override ───────────────────────────────────────────────
    if vix >= 35 or (abs(change_pct) >= 3.0 and vol_signal == "high"):
        regime = "crash_risk"
        bias = "bearish" if change_pct < 0 else "neutral"
        confidence = 0.85
        return MarketRegime(
            regime=regime,
            bias=bias,
            confidence=confidence,
            trend_signal=trend_signal,
            vol_signal="extreme",
            momentum_signal=momentum_signal,
            adx_signal=adx_signal,
            description=(
                f"Elevated systemic risk detected: VIX {vix:.1f}, "
                f"GLD 24h move {change_pct:+.2f}%."
            ),
        )

    # ── Composite regime classification ───────────────────────────────────────
    confidence_parts: list[float] = []

    if vol_signal == "low" and trend_signal == "up" and adx_signal in ("moderate", "strong"):
        regime = "low_vol_trend_up"
        bias = "bullish"
        confidence_parts = [0.7, 0.1 if adx_signal == "strong" else 0.0]
    elif vol_signal == "low" and trend_signal == "down" and adx_signal in ("moderate", "strong"):
        regime = "low_vol_trend_down"
        bias = "bearish"
        confidence_parts = [0.65, 0.1 if adx_signal == "strong" else 0.0]
    elif vol_signal == "low" and adx_signal == "weak":
        regime = "low_vol_range"
        bias = "neutral"
        confidence_parts = [0.70]
    elif vol_signal == "high" and adx_signal in ("moderate", "strong") and trend_signal == "up":
        regime = "high_vol_trend_up"
        bias = "bullish"
        confidence_parts = [0.60]
    elif vol_signal == "high" and adx_signal in ("moderate", "strong") and trend_signal == "down":
        regime = "high_vol_trend_down"
        bias = "bearish"
        confidence_parts = [0.60]
    elif vol_signal == "high":
        regime = "high_vol_range"
        bias = "neutral"
        confidence_parts = [0.65]
    elif trend_signal == "up" and adx_signal == "strong":
        regime = "strong_trend_up"
        bias = "bullish"
        confidence_parts = [0.75]
    elif trend_signal == "down" and adx_signal == "strong":
        regime = "strong_trend_down"
        bias = "bearish"
        confidence_parts = [0.75]
    else:
        regime = "choppy"
        bias = "neutral"
        confidence_parts = [0.50]

    # Adjust confidence using RSI extremes and skew
    if momentum_signal == "overbought" and bias == "bullish":
        confidence_parts.append(-0.05)
    if momentum_signal == "oversold" and bias == "bearish":
        confidence_parts.append(-0.05)
    if skew > 3.0 and bias == "bearish":
        confidence_parts.append(0.05)

    confidence = float(min(1.0, max(0.0, sum(confidence_parts))))

    # Build human-readable description
    desc_parts = [
        f"GLD ${price:.2f}",
        f"EMA20/50 spread {price - ema50:.2f}",
        f"RSI {rsi:.1f}",
        f"ADX {adx:.1f}",
        f"IV Rank {iv_rank:.0f}",
        f"VIX {vix:.1f}",
    ]
    description = " | ".join(desc_parts)

    return MarketRegime(
        regime=regime,
        bias=bias,
        confidence=confidence,
        trend_signal=trend_signal,
        vol_signal=vol_signal,
        momentum_signal=momentum_signal,
        adx_signal=adx_signal,
        description=description,
    )
