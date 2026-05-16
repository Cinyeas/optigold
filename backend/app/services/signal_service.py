from __future__ import annotations

"""
Signal generation service — orchestrates all 6 quant layers.

Layer 1: Market Data  (market_data_service)
Layer 2: IV Analysis  (iv_analysis)
Layer 3: Market Regime Detection  (market_regime)
Layer 4: Strategy Filtering  (user_profile_matcher + strategy_filter)
Layer 5: Parameter Generation + Scoring  (parameter_engine + scoring_engine)
Layer 6: Signal Formatting  (signal_formatter)
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db.signal import Signal
from app.models.db.market_snapshot import MarketSnapshot
from app.models.db.user_profile import UserProfile

from app.quant.iv_analysis import (
    iv_rank as compute_iv_rank,
    iv_percentile as compute_iv_percentile,
)
from app.quant.market_regime import detect_regime
from app.quant.user_profile_matcher import (
    UserProfile as QuantProfile,
    strategy_suitability_scores,
)
from app.quant.strategy_filter import filter_strategies
from app.quant.parameter_engine import generate_parameters
from app.quant.scoring_engine import score_strategy, rank_strategies
from app.quant.kelly_sizer import kelly_fraction, adjusted_kelly, position_size
from app.quant.signal_formatter import format_signal, FormattedSignal
from app.quant.eligibility_gate import apply_eligibility_gate
from app.quant.no_trade_detector import check_no_trade

from app.services.market_data_service import get_gld_snapshot, get_iv_history
from app.services.event_calendar import get_upcoming_events
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _build_quant_profile(db_profile: UserProfile) -> QuantProfile:
    return QuantProfile(
        capital=db_profile.capital,
        max_loss_per_trade=db_profile.max_loss_per_trade,
        accepts_options=db_profile.accepts_options,
        accepts_margin=db_profile.accepts_margin,
        accepts_unlimited_risk=db_profile.accepts_unlimited_risk,
        accepts_multi_leg=db_profile.accepts_multi_leg,
        time_horizon=db_profile.time_horizon,
        experience_level=db_profile.experience_level,
        risk_multiplier=db_profile.risk_multiplier,
    )


async def _get_or_create_profile(db: AsyncSession) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile()
        db.add(profile)
        await db.flush()
    return profile


async def generate_signal(db: AsyncSession) -> FormattedSignal:
    """
    Run all 6 layers and return a FormattedSignal, persisting it to the DB.
    """
    logger.info("Starting signal generation pipeline...")

    # ── Layer 1: Market Data ─────────────────────────────────────────────────
    snapshot = get_gld_snapshot()
    iv_history = get_iv_history()
    spot = snapshot["gld_price"]
    atm_iv = snapshot["gld_atm_iv"]

    # Persist market snapshot
    _DB_FIELDS = {c.name for c in MarketSnapshot.__table__.columns}
    ms = MarketSnapshot(**{k: v for k, v in snapshot.items()
                           if k in _DB_FIELDS and k != "captured_at"},
                        captured_at=snapshot["captured_at"])
    db.add(ms)
    await db.flush()
    snapshot_id = ms.id

    # ── Layer 2: IV Analysis ─────────────────────────────────────────────────
    ivr = compute_iv_rank(atm_iv, iv_history)
    ivp = compute_iv_percentile(atm_iv, iv_history)

    # ── Layer 3: Market Regime ────────────────────────────────────────────────
    regime = detect_regime(snapshot)
    logger.info("Regime: %s (bias=%s, confidence=%.0f%%)",
                regime.regime, regime.bias, regime.confidence * 100)

    # ── Layer 4: Strategy Filtering ───────────────────────────────────────────
    db_profile = await _get_or_create_profile(db)
    quant_profile = _build_quant_profile(db_profile)
    suitability = strategy_suitability_scores(quant_profile)
    candidates = filter_strategies(regime, suitability, top_n=5)

    # ── Layer 4b: Eligibility Hard Gate (crash_risk / event risk) ─────────────
    upcoming_events = get_upcoming_events()
    dte_target = _dte_for_horizon(quant_profile.time_horizon)

    eligible_names = apply_eligibility_gate(
        strategies=[c.name for c in candidates],
        regime=regime,
        upcoming_events=upcoming_events,
        dte=dte_target,
    )
    candidates = [c for c in candidates if c.name in eligible_names]

    if not candidates:
        logger.warning(
            "All candidates blocked by eligibility gate (regime=%s). "
            "No fallback — issuing no-trade signal.",
            regime.regime,
        )

    # ── Layer 4c: No-Trade Detection ──────────────────────────────────────────
    open_positions_count = await _count_open_positions(db)
    daily_move = abs(float(snapshot.get("gld_24h_change_pct") or 0.0))

    no_trade = check_no_trade(
        regime=regime,
        iv_rank=ivr,
        open_positions_count=open_positions_count,
        daily_move_pct=daily_move,
        candidate_strategy_names=[c.name for c in candidates],
    )

    if no_trade is not None:
        logger.info("No-trade signal triggered: %s", no_trade.reason_code)
        return await _persist_no_trade_signal(
            db=db,
            no_trade=no_trade,
            snapshot_id=snapshot_id,
            regime=regime,
            ivr=ivr,
            ivp=ivp,
            candidates=candidates if no_trade.allow_reference else [],
        )

    # ── Layer 5: Parameters + Scoring ────────────────────────────────────────

    _SINGLE_LEG_CREDIT = {"cash_secured_put", "covered_call"}

    # For low-capital profiles (max_loss_per_trade < $500), use tighter parameters:
    # - Lower delta target (15-delta) → more OTM, cheaper options
    # - Narrower spread width ($2) → max_loss ≈ $170, within the $300 limit
    # For standard profiles: 30-delta, default spread width (spot × 0.02)
    _is_low_capital = quant_profile.max_loss_per_trade < 500
    _delta_target = 0.15 if _is_low_capital else 0.30
    _spread_width = 3.0 if _is_low_capital else None   # $3 width: max_loss ≈ $255 < $300 limit

    scored = []
    for candidate in candidates:
        params = generate_parameters(
            strategy=candidate.name,
            spot=spot,
            atm_iv=atm_iv,
            dte_target=dte_target,
            delta_target_otm=_delta_target,
            spread_width=_spread_width,
        )

        # ── Risk gate: mirror backtest P0 filters ────────────────────────────
        # Single-leg credit: effective risk = 2× premium (Tastytrade 2× stop standard).
        # All other strategies: effective risk = max_loss (defined-risk cap).
        if candidate.name in _SINGLE_LEG_CREDIT:
            effective_risk = params.premium_collected * 2.0
        else:
            effective_risk = params.max_loss
        if effective_risk > quant_profile.max_loss_per_trade:
            logger.debug(
                "Skipping %s: effective_risk $%.0f > max_loss_per_trade $%.0f",
                candidate.name, effective_risk, quant_profile.max_loss_per_trade,
            )
            continue

        # Capital adequacy: CSP requires strike × 100 cash collateral.
        if candidate.name == "cash_secured_put":
            required_capital = (params.strike_a or spot * 0.90) * 100
            if required_capital > quant_profile.capital:
                logger.debug(
                    "Skipping CSP: required capital $%.0f > profile capital $%.0f",
                    required_capital, quant_profile.capital,
                )
                continue

        # Kelly sizing
        pop = params.probability_of_profit / 100
        avg_win = params.max_profit if params.max_profit > 0 else params.premium_collected
        avg_loss = params.max_loss if params.max_loss > 0 else params.premium_paid
        raw_kelly = kelly_fraction(pop, max(avg_win, 1), max(avg_loss, 1))
        adj_k = adjusted_kelly(raw_kelly, quant_profile.risk_multiplier)

        s = score_strategy(
            candidate=candidate,
            params=params,
            regime=regime,
            iv_rank=ivr,
            kelly_frac=adj_k,
            upcoming_events=upcoming_events,
        )
        scored.append((candidate, params, s, adj_k))

    ranked = sorted(scored, key=lambda x: x[2].composite, reverse=True)
    best_candidate, best_params, best_score, best_kelly = ranked[0]

    logger.info("Best strategy: %s (score=%.1f)", best_candidate.name, best_score.composite)

    # Alternative signal
    alt_signal_dict: Optional[dict] = None
    if len(ranked) >= 2:
        alt_c, alt_p, alt_s, _ = ranked[1]
        alt_signal_dict = {
            "strategy": alt_c.name,
            "composite_score": alt_s.composite,
            "action": alt_c.name.replace("_", " ").upper(),
        }

    # ── Layer 6: Signal Formatting ────────────────────────────────────────────
    signal_id = _make_signal_id()
    formatted = format_signal(
        strategy=best_candidate.name,
        params=best_params,
        score=best_score,
        regime=regime,
        iv_rank=ivr,
        iv_percentile=ivp,
        kelly_frac=best_kelly,
        spot=spot,
        signal_id=signal_id,
        alt_candidate=alt_signal_dict,
    )

    # ── Persist to DB ─────────────────────────────────────────────────────────
    db_dict = formatted.to_db_dict()
    db_dict["snapshot_id"] = snapshot_id
    signal_row = Signal(**db_dict)
    db.add(signal_row)
    await db.flush()

    logger.info("Signal %s persisted successfully.", signal_id)
    return formatted


def _dte_for_horizon(horizon: str) -> int:
    return {"weekly": 7, "monthly": 30, "quarterly": 60}.get(horizon, 30)


def _make_signal_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:6].upper()
    return f"SIG-{ts}-{uid}"


async def _count_open_positions(db: AsyncSession) -> int:
    from app.models.db.user_position import UserPosition
    from sqlalchemy import func
    result = await db.execute(
        select(func.count()).where(UserPosition.status == "open")
    )
    return result.scalar_one() or 0


async def _persist_no_trade_signal(
    db: AsyncSession,
    no_trade,
    snapshot_id: int,
    regime,
    ivr: float,
    ivp: float,
    candidates: list,
) -> FormattedSignal:
    """Persist a no-trade signal to DB and return as FormattedSignal."""
    from app.quant.no_trade_detector import NoTradeSignal

    signal_id = _make_signal_id()
    alt_signal_dict: Optional[dict] = None
    if candidates:
        # Reference-only candidate — shown as "for context" in UI
        alt_signal_dict = {
            "strategy": candidates[0].name,
            "composite_score": round(candidates[0].combined_score * 100, 1),
            "action": candidates[0].name.replace("_", " ").upper(),
            "reference_only": True,
        }

    formatted = FormattedSignal(
        signal_id=signal_id,
        generated_at=datetime.utcnow(),
        action="no_trade",
        instrument="GLD",
        market_regime=regime.regime,
        market_bias=regime.bias,
        composite_score=0.0,
        confidence="low",
        iv_rank=ivr,
        iv_percentile=ivp,
        plain_explanation=no_trade.reason_plain,
        detailed_reasoning=(
            f"[{no_trade.reason_code}] {no_trade.reason_plain}"
        ),
        alt_signal=alt_signal_dict,
    )

    db_dict = formatted.to_db_dict()
    db_dict["snapshot_id"] = snapshot_id
    signal_row = Signal(**db_dict)
    db.add(signal_row)
    await db.flush()

    logger.info("No-trade signal %s persisted (reason=%s).", signal_id, no_trade.reason_code)
    return formatted
