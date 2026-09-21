"""Live edge/EV tests (Task 10.5): hand-worked EV + negative-EV filtering."""

import sqlite3

import numpy as np
import pytest

from parallax_research.calibration import (
    compute_edge_ev,
    evaluate_and_store,
    evaluate_open_markets,
    store_predictions,
)
from parallax_research.storage import ensure_schema

# --- compute_edge_ev (hand-worked) -----------------------------------------------------------------

def test_yes_side_edge_and_ev():
    # model 0.7 vs market 0.5 -> bet YES. gross EV = 0.7*0.5 - 0.3*0.5 = 0.2 = edge.
    ee = compute_edge_ev(0.70, 0.50)
    assert ee.edge == pytest.approx(0.20)
    assert ee.side == "YES"
    assert ee.p_win == pytest.approx(0.70)
    assert ee.profit == pytest.approx(0.50)
    assert ee.gross_ev == pytest.approx(0.20)
    assert ee.ev == pytest.approx(0.20)
    assert ee.is_actionable


def test_no_side_edge_and_ev():
    # model 0.3 vs market 0.5 -> bet NO. gross EV = 0.7*0.5 - 0.3*0.5 = 0.2 = |edge|.
    ee = compute_edge_ev(0.30, 0.50)
    assert ee.edge == pytest.approx(-0.20)
    assert ee.side == "NO"
    assert ee.gross_ev == pytest.approx(0.20)
    assert ee.ev == pytest.approx(0.20)
    assert ee.is_actionable


def test_gross_ev_equals_abs_edge():
    for pm, pk in [(0.9, 0.4), (0.1, 0.6), (0.55, 0.5), (0.5, 0.5)]:
        ee = compute_edge_ev(pm, pk)
        assert ee.gross_ev == pytest.approx(abs(ee.edge))


def test_costs_make_a_small_edge_negative_ev():
    # edge 0.02, but fees+slippage = 0.04 -> net EV -0.02, not actionable.
    ee = compute_edge_ev(0.52, 0.50, fee=0.02, slippage=0.02)
    assert ee.edge == pytest.approx(0.02)
    assert ee.ev == pytest.approx(-0.02)
    assert not ee.is_actionable


def test_zero_edge_is_not_actionable():
    ee = compute_edge_ev(0.5, 0.5)
    assert ee.ev == pytest.approx(0.0)
    assert not ee.is_actionable  # ev must be strictly positive


# --- open-market evaluation + persistence + filtering ----------------------------------------------

class _StubModel:
    """A model that always predicts P(YES)=`value`, so edge = value - market_prob is controlled."""

    def __init__(self, value: float):
        self.value = value

    def predict_proba(self, df):
        return np.full(len(df), self.value, dtype=float)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _open_market(conn, market_id, market_prob, *, ts_ns=1000, resolved=None):
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES (?, 'manifold', 'q?', '2027-01-01T00:00:00Z', ?)",
        (market_id, resolved),
    )
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES (?, ?, 0.1, 1.0, 0.02)",
        (market_id, ts_ns),
    )
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, market_prob),
    )
    conn.commit()


def test_evaluate_open_markets_skips_resolved(conn):
    _open_market(conn, "open-a", 0.50)
    _open_market(conn, "resolved-b", 0.50, resolved=1)  # resolved -> excluded
    preds = evaluate_open_markets(conn, _StubModel(0.9))
    assert [p.market_id for p in preds] == ["open-a"]


def test_negative_ev_is_filtered_out_on_store(conn):
    # model always says 0.9. Market A (0.50): edge 0.40 -> big EV. Market B (0.88): edge 0.02 -> tiny.
    _open_market(conn, "big-edge", 0.50)
    _open_market(conn, "tiny-edge", 0.88)

    written = evaluate_and_store(conn, _StubModel(0.9), fee=0.03, slippage=0.02, min_ev=0.0)
    assert written == 1  # only the positive-EV market persisted

    rows = conn.execute("SELECT market_id, round(edge,3), round(ev,3) FROM model_predictions").fetchall()
    assert rows == [("big-edge", 0.4, 0.35)]  # tiny-edge (ev = 0.02-0.05 = -0.03) filtered out


def test_store_writes_all_when_min_ev_low_enough(conn):
    _open_market(conn, "big-edge", 0.50)
    _open_market(conn, "tiny-edge", 0.88)
    preds = evaluate_open_markets(conn, _StubModel(0.9))  # no costs -> both positive EV
    written = store_predictions(conn, preds, min_ev=0.0)
    assert written == 2


def test_market_with_no_price_is_skipped(conn):
    # feature snapshot but no probability_snapshots row -> market_prob NaN -> cannot compute edge.
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES ('no-price', 'manifold', 'q?', '2027-01-01T00:00:00Z', NULL)"
    )
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES ('no-price', 1000, 0.1, 1.0, 0.02)"
    )
    conn.commit()
    assert evaluate_open_markets(conn, _StubModel(0.9)) == []
