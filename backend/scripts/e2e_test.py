#!/usr/bin/env python3
"""
OptiGold E2E Full-Chain Test Tool
==================================
Simulates real user behavior end-to-end through the backend API.
Covers: settings → market → signal generation → position lifecycle → error cases.

Usage:
    python scripts/e2e_test.py                    # defaults to localhost:8000
    python scripts/e2e_test.py --base http://10.0.2.2:8000
    python scripts/e2e_test.py --skip-slow        # skip signal refresh (slow)

Requirements:
    pip install requests rich
"""

import argparse
import sys
import time
import random
from datetime import date, timedelta
from typing import Any

import requests

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

    class Console:  # noqa: F811
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            # Strip Rich markup
            import re
            text = re.sub(r"\[.*?\]", "", text)
            print(text)

    console = Console()


# ─── Result tracking ────────────────────────────────────────────────────────

results: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    icon = "✅" if condition else "❌"
    status = "PASS" if condition else "FAIL"
    results.append({"name": name, "status": status, "detail": detail})
    color = "green" if condition else "red"
    console.print(f"  {icon} [{color}]{name}[/{color}]" + (f" — {detail}" if detail else ""))
    return condition


def step(title: str):
    console.print(f"\n[bold cyan]{title}[/bold cyan]")


def timed_request(method: str, url: str, **kwargs) -> tuple[requests.Response | None, float]:
    t0 = time.monotonic()
    try:
        resp = requests.request(method, url, timeout=kwargs.pop("timeout", 30), **kwargs)
        elapsed = time.monotonic() - t0
        return resp, round(elapsed, 2)
    except requests.ConnectionError:
        return None, round(time.monotonic() - t0, 2)


# ─── Phase helpers ──────────────────────────────────────────────────────────

def phase_a_settings(base: str) -> dict | None:
    step("Phase A — Settings & User Profile")

    # 1. GET default profile
    resp, t = timed_request("GET", f"{base}/api/v1/settings/")
    if resp is None:
        check("GET /settings/ reachable", False, "Connection refused — is the backend running?")
        return None
    check("GET /settings/ → 200", resp.status_code == 200, f"{t}s")

    # 2. PUT beginner profile
    payload = {
        "capital": 5000,
        "max_loss_per_trade": 200,
        "experience_level": "beginner",
        "time_horizon": "monthly",
        "accepts_options": True,
        "accepts_margin": False,
        "accepts_multi_leg": False,
        "accepts_unlimited_risk": False,
        "risk_multiplier": 0.5,
    }
    resp, t = timed_request("PUT", f"{base}/api/v1/settings/", json=payload)
    check("PUT /settings/ → 200", resp.status_code == 200, f"{t}s")

    # 3. Verify update persisted
    resp, t = timed_request("GET", f"{base}/api/v1/settings/")
    data = resp.json()
    check("capital updated to 5000", data.get("capital") == 5000)
    check("experience_level = beginner", data.get("experience_level") == "beginner")
    return data


def phase_b_market(base: str) -> dict | None:
    step("Phase B — Market Data")

    resp, t = timed_request("GET", f"{base}/api/v1/market/snapshot")
    check("GET /market/snapshot → 200", resp.status_code == 200, f"{t}s")
    snap = resp.json()
    required_fields = ["gld_price", "gld_atm_iv", "gld_iv_rank", "market_regime",
                       "gld_hv_20d", "rsi_14", "adx", "captured_at"]
    for f in required_fields:
        check(f"snapshot has '{f}'", f in snap, str(snap.get(f, "MISSING")))
    check("gld_price > 0", (snap.get("gld_price") or 0) > 0)
    check("iv_rank in [0, 100]", 0 <= (snap.get("gld_iv_rank") or 50) <= 100)

    resp2, t2 = timed_request("GET", f"{base}/api/v1/market/iv-rank")
    check("GET /market/iv-rank → 200", resp2.status_code == 200, f"{t2}s")
    iv = resp2.json()
    check("iv-rank has iv_rank field", "iv_rank" in iv)
    check("iv-rank has iv_percentile field", "iv_percentile" in iv)
    return snap


def phase_c_signals(base: str, skip_slow: bool) -> dict | None:
    step("Phase C — Signal Generation")

    if not skip_slow:
        console.print("  [dim]Generating new signal (may take 10–30s)...[/dim]")
        resp, t = timed_request("POST", f"{base}/api/v1/signals/refresh", timeout=60)
        check("POST /signals/refresh → 200", resp.status_code == 200, f"{t}s")
    else:
        console.print("  [dim](Skipping /signals/refresh — use --no-skip-slow to enable)[/dim]")

    resp, t = timed_request("GET", f"{base}/api/v1/signals/latest")
    check("GET /signals/latest → 200", resp.status_code == 200, f"{t}s")
    sig = resp.json()

    required = ["id", "action", "generated_at", "composite_score", "confidence",
                "market_regime", "reasoning_plain"]
    for f in required:
        check(f"signal has '{f}'", f in sig and sig[f] is not None, str(sig.get(f, "MISSING")))

    score = sig.get("composite_score") or 0
    check("composite_score in [0, 100]", 0 <= score <= 100, f"score={score:.1f}")

    # Fetch by ID
    sig_id = sig["id"]
    resp2, t2 = timed_request("GET", f"{base}/api/v1/signals/{sig_id}")
    check("GET /signals/{id} → 200", resp2.status_code == 200, f"{t2}s")
    check("same signal returned by ID", resp2.json().get("id") == sig_id)

    # Paginated list
    resp3, t3 = timed_request("GET", f"{base}/api/v1/signals/", params={"page": 1, "page_size": 5})
    check("GET /signals/ list → 200", resp3.status_code == 200, f"{t3}s")
    lst = resp3.json()
    check("list has 'items' key", "items" in lst)
    check("list has 'total' key", "total" in lst)
    check("items is list", isinstance(lst.get("items"), list))

    return sig


def phase_d_positions(base: str, signal: dict) -> int | None:
    step("Phase D — Position Lifecycle")

    # Derive entry price from signal
    entry_price = signal.get("premium_collected") or 2.50
    expiry = signal.get("expiry") or str(date.today() + timedelta(days=30))

    payload = {
        "signal_id": signal.get("id"),
        "instrument": signal.get("instrument", "GLD"),
        "strategy": signal.get("action", "bull_put_spread"),
        "strike_a": signal.get("strike_a"),
        "strike_b": signal.get("strike_b"),
        "expiry": expiry,
        "quantity": signal.get("quantity") or 1,
        "entry_price": entry_price,
        "notes": "E2E test trade",
    }

    resp, t = timed_request("POST", f"{base}/api/v1/positions/", json=payload)
    check("POST /positions/ → 201", resp.status_code == 201, f"{t}s")
    pos = resp.json()
    pos_id = pos.get("id")
    check("position has id", pos_id is not None)
    check("position status = open", pos.get("status") == "open")

    # List open positions
    resp2, t2 = timed_request("GET", f"{base}/api/v1/positions/", params={"status": "open"})
    check("GET /positions/?status=open → 200", resp2.status_code == 200, f"{t2}s")
    open_positions = resp2.json()
    ids = [p["id"] for p in open_positions]
    check("new position in open list", pos_id in ids)

    # Close position
    close_price = round(entry_price * (1 + random.uniform(-0.15, 0.10)), 2)
    resp3, t3 = timed_request(
        "PUT", f"{base}/api/v1/positions/{pos_id}/close",
        json={"close_price": close_price, "notes": "E2E test close"}
    )
    check("PUT /positions/{id}/close → 200", resp3.status_code == 200, f"{t3}s")
    closed = resp3.json()
    check("position status = closed", closed.get("status") == "closed")
    check("realized_pnl computed", closed.get("realized_pnl") is not None)

    # Verify closed list
    resp4, t4 = timed_request("GET", f"{base}/api/v1/positions/", params={"status": "closed"})
    check("GET /positions/?status=closed → 200", resp4.status_code == 200, f"{t4}s")
    closed_ids = [p["id"] for p in resp4.json()]
    check("position appears in closed list", pos_id in closed_ids)

    return pos_id


def phase_e_profiles(base: str, skip_slow: bool):
    step("Phase E — Multi-Profile Strategy Variation")

    profiles = [
        {
            "label": "Intermediate $50k",
            "capital": 50000, "max_loss_per_trade": 2500,
            "experience_level": "intermediate", "time_horizon": "monthly",
            "accepts_options": True, "accepts_margin": False,
            "accepts_multi_leg": True, "accepts_unlimited_risk": False,
            "risk_multiplier": 0.75,
        },
        {
            "label": "Advanced $200k, all flags",
            "capital": 200000, "max_loss_per_trade": 10000,
            "experience_level": "advanced", "time_horizon": "monthly",
            "accepts_options": True, "accepts_margin": True,
            "accepts_multi_leg": True, "accepts_unlimited_risk": True,
            "risk_multiplier": 1.0,
        },
    ]

    actions_seen: list[str] = []
    for prof in profiles:
        label = prof.pop("label")
        resp, _ = timed_request("PUT", f"{base}/api/v1/settings/", json=prof)
        check(f"PUT profile '{label}' → 200", resp.status_code == 200)

        if not skip_slow:
            resp2, t2 = timed_request("POST", f"{base}/api/v1/signals/refresh", timeout=60)
            check(f"Signal refresh for '{label}' → 200", resp2.status_code == 200, f"{t2}s")
            if resp2.status_code == 200:
                sig = resp2.json()
                actions_seen.append(sig.get("action", "?"))
                console.print(f"    → strategy: [yellow]{sig.get('action')}[/yellow], "
                               f"score: [cyan]{sig.get('composite_score', 0):.1f}[/cyan]")
        else:
            console.print(f"    [dim](Skipping refresh for '{label}')[/dim]")

    if len(actions_seen) >= 2:
        # Different profiles SHOULD sometimes pick different strategies
        console.print(f"  [dim]Strategies seen: {actions_seen}[/dim]")


def phase_f_errors(base: str):
    step("Phase F — Error & Edge Cases")

    # 404 on fake signal ID
    resp, t = timed_request("GET", f"{base}/api/v1/signals/FAKE-SIGNAL-ID-99999")
    check("GET /signals/FAKE-ID → 404", resp.status_code == 404, f"{t}s")

    # 404 on invalid position
    resp2, t2 = timed_request(
        "PUT", f"{base}/api/v1/positions/999999/close",
        json={"close_price": 1.0}
    )
    check("PUT /positions/999999/close → 404", resp2.status_code == 404, f"{t2}s")

    # Invalid settings field should be silently ignored (not 500)
    resp3, t3 = timed_request("PUT", f"{base}/api/v1/settings/",
                              json={"nonexistent_field": "garbage", "capital": 9999})
    check("PUT /settings/ with unknown field → not 500",
          resp3.status_code in (200, 422), f"got {resp3.status_code}")

    # Double-close should fail gracefully
    resp4, t4 = timed_request("GET", f"{base}/api/v1/positions/", params={"status": "closed"})
    if resp4.status_code == 200 and resp4.json():
        closed_id = resp4.json()[0]["id"]
        resp5, t5 = timed_request(
            "PUT", f"{base}/api/v1/positions/{closed_id}/close",
            json={"close_price": 1.0}
        )
        check("Double-close → 400 or 409",
              resp5.status_code in (400, 409), f"got {resp5.status_code}")


# ─── Phase G ────────────────────────────────────────────────────────────────

def phase_g_market_closed(base: str):
    step("Phase G — Market Closed / Stale Data")

    # 1. Market snapshot should always return data (cached) and never 500
    resp, t = timed_request("GET", f"{base}/api/v1/market/snapshot")
    check("GET /market/snapshot → not 500", resp is not None and resp.status_code != 500, f"{t}s")
    if resp and resp.status_code == 200:
        snap = resp.json()
        check("snapshot has captured_at timestamp", snap.get("captured_at") is not None,
              str(snap.get("captured_at", "MISSING")))
        # captured_at must be parseable as ISO datetime
        captured = snap.get("captured_at", "")
        try:
            from datetime import datetime
            datetime.fromisoformat(captured.replace("Z", "+00:00"))
            check("captured_at is valid ISO datetime", True, captured[:19])
        except Exception:
            check("captured_at is valid ISO datetime", False, f"unparseable: {captured}")

    # 2. Latest signal should have a generated_at (so frontend can show staleness)
    resp2, t2 = timed_request("GET", f"{base}/api/v1/signals/latest")
    check("GET /signals/latest → not 500", resp2 is not None and resp2.status_code != 500, f"{t2}s")
    if resp2 and resp2.status_code == 200:
        sig = resp2.json()
        check("signal has generated_at", sig.get("generated_at") is not None,
              str(sig.get("generated_at", "MISSING")))

    # 3. Closing an already-closed position returns a structured error, not 500
    resp3, t3 = timed_request("GET", f"{base}/api/v1/positions/", params={"status": "closed"})
    if resp3 and resp3.status_code == 200 and resp3.json():
        closed_id = resp3.json()[0]["id"]
        resp4, t4 = timed_request(
            "PUT", f"{base}/api/v1/positions/{closed_id}/close",
            json={"close_price": 1.0}
        )
        check(
            "Double-close → 400/409 (not 500)",
            resp4 is not None and resp4.status_code in (400, 409),
            f"got {resp4.status_code if resp4 else 'no response'}",
        )
    else:
        console.print("  [dim](Skipping double-close check — no closed positions)[/dim]")

    # 4. Validate that position close_reason field is accepted (new field)
    console.print("  [dim]Testing new close_reason field in position close...[/dim]")
    # create a throwaway position to test close_reason
    resp5, _ = timed_request("GET", f"{base}/api/v1/signals/latest")
    if resp5 and resp5.status_code == 200:
        sig = resp5.json()
        import random
        create_resp, _ = timed_request("POST", f"{base}/api/v1/positions/", json={
            "signal_id": sig.get("id"),
            "instrument": "GLD",
            "strategy": sig.get("action", "cash_secured_put"),
            "expiry": str(__import__("datetime").date.today() + __import__("datetime").timedelta(days=30)),
            "quantity": 1,
            "entry_price": 2.00,
        })
        if create_resp and create_resp.status_code == 201:
            new_id = create_resp.json()["id"]
            close_resp, _ = timed_request(
                "PUT", f"{base}/api/v1/positions/{new_id}/close",
                json={"close_price": 2.50, "close_reason": "profit_target", "notes": "Phase G test"},
            )
            check("close_reason field accepted → 200", close_resp is not None and close_resp.status_code == 200)
            if close_resp and close_resp.status_code == 200:
                closed_data = close_resp.json()
                check("close_reason persisted", closed_data.get("close_reason") == "profit_target",
                      str(closed_data.get("close_reason")))


# ─── Summary ────────────────────────────────────────────────────────────────

def print_summary():
    console.print("\n" + "─" * 60)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)

    if HAS_RICH:
        table = Table(title="E2E Test Summary", box=box.ROUNDED, show_header=True)
        table.add_column("Check", style="dim", width=45)
        table.add_column("Result", justify="center")
        for r in results:
            color = "green" if r["status"] == "PASS" else "red"
            table.add_row(r["name"], f"[{color}]{r['status']}[/{color}]")
        console.print(table)

    color = "green" if failed == 0 else "red"
    console.print(f"\n[{color}]Total: {passed}/{total} passed, {failed} failed[/{color}]")

    if failed == 0:
        console.print("[bold green]✅ All checks passed — backend API is healthy![/bold green]")
    else:
        console.print(f"[bold red]❌ {failed} check(s) failed — see details above.[/bold red]")

    return failed == 0


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OptiGold E2E API Test")
    parser.add_argument("--base", default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--skip-slow", action="store_true",
                        help="Skip POST /signals/refresh (slow, hits Alpaca API)")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    console.print(f"\n[bold]OptiGold E2E Test — {base}[/bold]")
    console.print("[dim]Testing all API endpoints with real user behavior simulation...[/dim]")

    # Phase A: Settings
    profile = phase_a_settings(base)
    if profile is None:
        console.print("\n[bold red]Cannot reach backend. Aborting.[/bold red]")
        sys.exit(1)

    # Phase B: Market
    phase_b_market(base)

    # Phase C: Signals
    signal = phase_c_signals(base, args.skip_slow)

    # Phase D: Positions (requires a signal)
    if signal:
        phase_d_positions(base, signal)
    else:
        console.print("  [yellow]Skipping position tests (no signal available)[/yellow]")

    # Phase E: Multi-profile
    phase_e_profiles(base, args.skip_slow)

    # Phase F: Errors
    phase_f_errors(base)

    # Phase G: Market closed / stale data / new fields
    phase_g_market_closed(base)

    # Summary
    ok = print_summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
