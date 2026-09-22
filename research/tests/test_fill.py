"""CPMM fill simulation tests (Task 11.2): hand-worked Maniswap scenarios + invariant preservation."""

import pytest

from parallax_research.backtester import CpmmPool, simulate_fill


def test_balanced_pool_prices_at_p():
    # yes == no -> probability equals the resting parameter p.
    assert CpmmPool(yes=100, no=100, p=0.5).probability == pytest.approx(0.5)
    assert CpmmPool(yes=100, no=100, p=0.6).probability == pytest.approx(0.6)


def test_from_probability_round_trip():
    for prob, p in [(0.7, 0.5), (0.3, 0.5), (0.7, 0.6), (0.25, 0.4)]:
        pool = CpmmPool.from_probability(prob, liquidity=100.0, p=p)
        assert pool.probability == pytest.approx(prob)
        assert pool.yes + pool.no == pytest.approx(100.0)


def test_yes_fill_hand_computed_p_half():
    # y=n=100, p=0.5, buy 10 mana YES.
    # shares = M(y+n+M)/(n+M) = 10*210/110 = 19.090909...
    # yes' = 100*(100/110) = 90.909..., no' = 110
    # prob_after = 0.5*110 / (0.5*110 + 0.5*90.909...) = 0.547511...
    fill = simulate_fill(CpmmPool(100, 100, 0.5), "YES", 10.0)
    assert fill.shares == pytest.approx(2100 / 110)
    assert fill.effective_price == pytest.approx(10.0 / (2100 / 110))
    assert fill.prob_before == pytest.approx(0.5)
    assert fill.prob_after == pytest.approx(0.547511, abs=1e-5)
    assert fill.pool_after.no == pytest.approx(110.0)
    assert fill.pool_after.yes == pytest.approx(90.909091, abs=1e-5)


def test_yes_fill_moves_probability_up_no_fill_moves_it_down():
    pool = CpmmPool(100, 100, 0.5)
    up = simulate_fill(pool, "YES", 25.0)
    down = simulate_fill(pool, "NO", 25.0)
    assert up.prob_after > 0.5
    assert down.prob_after < 0.5
    # Symmetric pool + equal stakes -> mirror-image probabilities and equal share counts.
    assert up.prob_after == pytest.approx(1.0 - down.prob_after)
    assert up.shares == pytest.approx(down.shares)


def test_fill_preserves_the_invariant_p_half():
    pool = CpmmPool(120, 80, 0.5)
    k0 = pool.invariant
    for side, stake in [("YES", 5.0), ("NO", 40.0), ("YES", 0.01)]:
        after = simulate_fill(pool, side, stake).pool_after
        assert after.invariant == pytest.approx(k0)


def test_fill_preserves_the_invariant_general_p():
    # Non-0.5 p exercises the general fractional-exponent formula.
    pool = CpmmPool.from_probability(0.4, liquidity=250.0, p=0.65)
    k0 = pool.invariant
    for side, stake in [("YES", 10.0), ("NO", 3.0)]:
        assert simulate_fill(pool, side, stake).pool_after.invariant == pytest.approx(k0)


def test_larger_stake_has_worse_effective_price_slippage():
    pool = CpmmPool(100, 100, 0.5)
    small = simulate_fill(pool, "YES", 1.0)
    large = simulate_fill(pool, "YES", 50.0)
    # A tiny YES buy prices near the current 0.5; a big buy pushes the average price higher.
    assert small.effective_price < large.effective_price
    assert small.effective_price >= 0.5  # never cheaper than the marginal price you start at


def test_effective_price_between_before_and_after_prob():
    fill = simulate_fill(CpmmPool(100, 100, 0.5), "YES", 20.0)
    # You pay an average price bounded by the pre- and post-fill marginal probabilities.
    assert fill.prob_before < fill.effective_price < fill.prob_after


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        CpmmPool(yes=0, no=100)
    with pytest.raises(ValueError):
        CpmmPool(yes=100, no=100, p=1.0)
    with pytest.raises(ValueError):
        simulate_fill(CpmmPool(100, 100), "YES", 0.0)
    with pytest.raises(ValueError):
        simulate_fill(CpmmPool(100, 100), "MAYBE", 10.0)
    with pytest.raises(ValueError):
        CpmmPool.from_probability(0.0, 100.0)
