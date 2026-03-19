from __future__ import annotations

"""
Phase 1 hardcoded event calendar.

Lists upcoming macro and Fed events that affect GLD / gold options.
Each event carries an impact level used by the scoring engine's event-risk dimension.
"""

from datetime import date, timedelta
from typing import Any


# ── Hardcoded upcoming events (relative to a typical trading month) ────────────
# impact: "high" | "medium" | "low"
_STATIC_EVENTS: list[dict[str, Any]] = [
    {
        "name": "FOMC Rate Decision",
        "category": "fed",
        "impact": "high",
        "typical_month_day": 1,   # 1st Wednesday of month (approximate)
        "description": "Federal Open Market Committee interest rate decision and press conference.",
    },
    {
        "name": "US CPI Release",
        "category": "macro",
        "impact": "high",
        "typical_month_day": 10,
        "description": "Consumer Price Index month-over-month and year-over-year.",
    },
    {
        "name": "US Non-Farm Payrolls",
        "category": "macro",
        "impact": "high",
        "typical_month_day": 5,
        "description": "Monthly employment report — first Friday of the month.",
    },
    {
        "name": "US PPI Release",
        "category": "macro",
        "impact": "medium",
        "typical_month_day": 11,
        "description": "Producer Price Index — inflation at the producer level.",
    },
    {
        "name": "US GDP Advance Estimate",
        "category": "macro",
        "impact": "medium",
        "typical_month_day": 26,
        "description": "Advance GDP estimate for the previous quarter.",
    },
    {
        "name": "Fed Chair Speech / Jackson Hole",
        "category": "fed",
        "impact": "high",
        "typical_month_day": 22,
        "description": "Fed Chair keynote — major policy signals often revealed.",
    },
    {
        "name": "US Treasury Auction (10Y)",
        "category": "fixed_income",
        "impact": "low",
        "typical_month_day": 15,
        "description": "10-year Treasury note auction — affects rates and gold.",
    },
    {
        "name": "US Retail Sales",
        "category": "macro",
        "impact": "medium",
        "typical_month_day": 16,
        "description": "Month-over-month retail sales data.",
    },
]


def get_upcoming_events(
    from_date: date | None = None,
    window_days: int = 45,
) -> list[dict[str, Any]]:
    """
    Return a list of upcoming events within the next *window_days* days.

    Each returned dict has keys:
        name, category, impact, date, days_away, description

    Phase 1: Dates are approximated by offsetting from *from_date* using
    the typical_month_day of each event.
    """
    if from_date is None:
        from_date = date.today()

    events_with_dates: list[dict[str, Any]] = []

    for ev in _STATIC_EVENTS:
        # Build approximate next-occurrence date within this or next calendar month
        for month_offset in range(3):  # look up to ~3 months ahead
            year = from_date.year
            month = from_date.month + month_offset
            if month > 12:
                month -= 12
                year += 1
            try:
                event_date = date(year, month, ev["typical_month_day"])
            except ValueError:
                # Invalid date (e.g. Feb 30) — skip
                continue

            days_away = (event_date - from_date).days
            if 0 <= days_away <= window_days:
                events_with_dates.append(
                    {
                        "name": ev["name"],
                        "category": ev["category"],
                        "impact": ev["impact"],
                        "date": event_date.isoformat(),
                        "days_away": days_away,
                        "description": ev["description"],
                    }
                )
                break  # Only the soonest occurrence per event

    events_with_dates.sort(key=lambda e: e["days_away"])
    return events_with_dates


def get_high_impact_events(window_days: int = 30) -> list[dict[str, Any]]:
    """Return only high-impact events in the next *window_days* days."""
    return [
        e for e in get_upcoming_events(window_days=window_days)
        if e["impact"] == "high"
    ]
