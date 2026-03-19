from __future__ import annotations

"""NYSE / US-equity market session utilities."""

from datetime import datetime, time, date
from typing import Literal
import pytz

NY_TZ = pytz.timezone("America/New_York")

# NYSE regular session times (Eastern)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
PRE_MARKET_OPEN = time(4, 0)
AFTER_MARKET_CLOSE = time(20, 0)

# Weekday integers (Monday=0, Sunday=6)
WEEKDAYS = {0, 1, 2, 3, 4}

# Simplified list of NYSE holidays for 2024-2026
NYSE_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 1),
    date(2024, 1, 15),
    date(2024, 2, 19),
    date(2024, 3, 29),
    date(2024, 5, 27),
    date(2024, 6, 19),
    date(2024, 7, 4),
    date(2024, 9, 2),
    date(2024, 11, 28),
    date(2024, 12, 25),
    # 2025
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 8, 31),
    date(2026, 11, 26),
    date(2026, 12, 25),
}

SessionType = Literal["pre_market", "regular", "after_hours", "closed"]


def now_eastern() -> datetime:
    """Return current UTC time converted to US/Eastern."""
    return datetime.now(tz=pytz.utc).astimezone(NY_TZ)


def is_trading_day(dt: datetime | None = None) -> bool:
    """Return True if *dt* (Eastern) falls on a NYSE trading day."""
    if dt is None:
        dt = now_eastern()
    local = dt.astimezone(NY_TZ)
    return local.weekday() in WEEKDAYS and local.date() not in NYSE_HOLIDAYS


def get_market_session(dt: datetime | None = None) -> SessionType:
    """Classify *dt* (Eastern) into a market session bucket."""
    if dt is None:
        dt = now_eastern()
    local = dt.astimezone(NY_TZ)

    if not is_trading_day(local):
        return "closed"

    t = local.time()
    if MARKET_OPEN <= t < MARKET_CLOSE:
        return "regular"
    if PRE_MARKET_OPEN <= t < MARKET_OPEN:
        return "pre_market"
    if MARKET_CLOSE <= t < AFTER_MARKET_CLOSE:
        return "after_hours"
    return "closed"


def is_market_open(dt: datetime | None = None) -> bool:
    """Return True only during regular NYSE trading hours."""
    return get_market_session(dt) == "regular"


def minutes_to_open(dt: datetime | None = None) -> int:
    """Return minutes until regular session open; 0 if already open."""
    if dt is None:
        dt = now_eastern()
    local = dt.astimezone(NY_TZ)
    session = get_market_session(local)
    if session == "regular":
        return 0
    # Next trading day open
    from datetime import timedelta

    candidate = local.replace(hour=9, minute=30, second=0, microsecond=0)
    if local.time() >= MARKET_OPEN and is_trading_day(local):
        candidate += timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    delta = candidate - local
    return max(0, int(delta.total_seconds() / 60))
