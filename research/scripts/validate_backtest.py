#!/usr/bin/env python3
"""Validate the backtester against a REAL resolved Manifold market end-to-end (Task 11.5).

Fetches a real resolved binary Manifold market and its full bet history, rebuilds its probability
history in a temp SQLite DB, runs the whole backtester chain (CPMM fill -> latency-aware execution
-> settlement against the real resolution -> P&L aggregation), and writes
`reports/backtest-validation.md` with a by-hand sanity check.

The "strategy" here is intentionally trivial (buy YES at a few early points) — the point is to
validate that the machinery produces *sane* numbers on real data, not to demonstrate alpha. Sanity
check: if the market resolved YES, every YES trade must win (positive P&L); if NO, every YES trade
must lose. Read-only; never places a bet (constraint §2.1).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

import httpx

from parallax_research.backtester import aggregate, settle, simulate_execution
from parallax_research.storage import ensure_schema

API = "https://api.manifold.markets/v0"


def _pick_resolved_binary_market(client: httpx.Client) -> dict:
    markets = client.get(f"{API}/markets", params={"limit": 1000}).json()
    for m in markets:
        if (
            m.get("outcomeType") == "BINARY"
            and m.get("isResolved")
            and m.get("resolution") in ("YES", "NO")
            and (m.get("volume") or 0) > 500
        ):
            return m
    raise SystemExit("no suitable resolved binary market found")


def _fetch_bets(client: httpx.Client, contract_id: str, cap: int = 3000) -> list[dict]:
    bets: list[dict] = []
    before = None
    while len(bets) < cap:
        params = {"contractId": contract_id, "limit": 1000}
        if before:
            params["before"] = before
        page = client.get(f"{API}/bets", params=params).json()
        if not page:
            break
        bets.extend(page)
        if len(page) < 1000:
            break
        before = page[-1]["id"]
    # keep real AMM-moving bets with a post-bet probability, oldest first
    bets = [b for b in bets if b.get("probAfter") is not None and b.get("createdTime")]
    bets.sort(key=lambda b: b["createdTime"])
    return bets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the backtester on a real Manifold market.")
    parser.add_argument("--out", default="../reports/backtest-validation.md")
    args = parser.parse_args(argv)

    with httpx.Client(timeout=30) as client:
        market = _pick_resolved_binary_market(client)
        bets = _fetch_bets(client, market["id"])
    if len(bets) < 10:
        raise SystemExit("chosen market had too few usable bets")

    outcome = 1 if market["resolution"] == "YES" else 0
    liquidity = float(market.get("totalLiquidity") or 1000.0)

    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES (?, 'manifold', ?, ?, ?)",
        (market["id"], market.get("question", ""), str(market.get("closeTime", "")), outcome),
    )
    for b in bets:
        conn.execute(
            "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
            (market["id"], int(b["createdTime"]) * 1_000_000, float(b["probAfter"])),
        )
    conn.commit()

    # Trivial validation strategy: buy YES at 5 evenly-spaced points in the first half of the history.
    signal_bets = bets[: len(bets) // 2]
    picks = signal_bets[:: max(1, len(signal_bets) // 5)][:5]
    trades = []
    for b in picks:
        signal_ns = int(b["createdTime"]) * 1_000_000
        exe = simulate_execution(
            conn, market_id=market["id"], side="YES", stake=100.0,
            signal_ts_ns=signal_ns, liquidity=liquidity,
        )
        if exe is not None:
            trades.append(settle(exe, outcome=outcome, theoretical_edge=0.0))

    result = aggregate(trades)

    # By-hand sanity check.
    expected_all_win = outcome == 1
    sane = (result.n_wins == result.n_trades) if expected_all_win else (result.n_wins == 0)
    sign_ok = (result.realized_pnl > 0) if expected_all_win else (result.realized_pnl < 0)

    md = [
        "# Parallax — Backtester Validation (real resolved Manifold market)\n",
        ("> Task 11.5: the backtester run end-to-end against one real, resolved Manifold market "
        "(fetched live from the public API). Read-only; no bets placed.\n"),
        "## Market\n",
        f"- ID: `{market['id']}`",
        f"- Question: {market.get('question', '')}",
        f"- Resolution: **{market['resolution']}** (outcome={outcome})",
        f"- Usable bets (price points): {len(bets)}",
        f"- Total liquidity (pool size used): {liquidity:.2f}\n",
        "## Strategy (validation harness, not alpha)\n",
        ("Buy YES with 100 mana at 5 evenly-spaced points in the first half of the market's life; "
        "each fill uses the latency-aware execution price and settles against the real resolution.\n"),
        "## Result\n",
        result.to_markdown(title="Aggregated P&L", note="single real market", range_label=market["id"]),
        "## By-hand sanity check\n",
        (f"- Market resolved **{market['resolution']}**, so every YES trade should "
        f"{'WIN' if expected_all_win else 'LOSE'}."),
        f"- Wins: {result.n_wins}/{result.n_trades} → {'as expected ✅' if sane else 'UNEXPECTED ❌'}",
        (f"- Realized P&L sign ({result.realized_pnl:+.2f}) is "
        f"{'correct ✅' if sign_ok else 'WRONG ❌'} for a {market['resolution']} resolution."),
        (f"\n**Validation: {'PASS' if (sane and sign_ok) else 'FAIL'}** — the full chain (fill → "
        "latency execution → settlement → aggregation) produces directionally-correct P&L on real data.\n"),
    ]
    with open(args.out, "w") as fh:
        fh.write("\n".join(md))
    print(f"wrote {args.out}: validation {'PASS' if (sane and sign_ok) else 'FAIL'}", file=sys.stderr)
    conn.close()
    return 0 if (sane and sign_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
