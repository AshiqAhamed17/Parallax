use common::BetSample;

/// Realized volatility of the probability series over the trailing `window_ns`.
///
/// **Design (root-sum-of-squared returns, not standard deviation):** this uses the standard
/// market-microstructure definition of realized volatility (Andersen & Bollerslev) —
/// `sqrt(Σ r_i²)` over consecutive returns within the window — not the sample/population
/// standard deviation of those returns. The difference matters: stdev mean-centers first, so a
/// steady one-directional drift (every return the same size) has *near-zero* stdev, while RV
/// correctly reports it as real, accumulated movement. Returns here are simple differences in
/// `prob_after` between consecutive bets (not log-returns): probability is bounded to `[0, 1]`,
/// where log-returns aren't the conventional treatment the way they are for unbounded prices.
///
/// **This is `prob_velocity`'s complement, not a duplicate:** a market that round-trips
/// 0.5 -> 0.6 -> 0.5 within the window has `prob_velocity` ~= 0 (no net drift) but nonzero
/// `realized_volatility` (real movement happened, it just cancelled out directionally). Together
/// the two features answer "which way, net?" and "how much did it actually move?" separately.
///
/// **Unlike `prob_velocity`/`bet_arrival_rate`, this is NOT normalized to a per-second rate** —
/// realized volatility is conventionally reported for the period it was measured over, not
/// annualized/rated here (a caller wanting a rate can divide by the window duration itself).
///
/// # Preconditions
/// `recent_events` must be sorted oldest-to-newest — the order `BetHistory::iter()` yields.
///
/// # Edge cases
/// Returns `0.0` if fewer than 2 events fall within the window (at least two `prob_after` values
/// are required to form a single return), or if `window_ns` is `0`.
pub fn realized_volatility(recent_events: &[BetSample], window_ns: u64) -> f64 {
    if window_ns == 0 {
        return 0.0;
    }
    let Some(latest) = recent_events.last() else {
        return 0.0;
    };
    let window_start = latest.ts_ns.saturating_sub(window_ns);
    // Sorted oldest→newest: the in-window events are the contiguous suffix from `start` on, found
    // in O(log n). Operate on that subslice directly — no `Vec<&BetEvent>` allocation per call.
    let start = recent_events.partition_point(|e| e.ts_ns < window_start);
    let windowed = &recent_events[start..];
    if windowed.len() < 2 {
        return 0.0;
    }

    let sum_sq_returns: f64 = windowed
        .windows(2)
        .map(|pair| {
            let r = pair[1].prob_after - pair[0].prob_after;
            r * r
        })
        .sum();
    sum_sq_returns.sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(ts_ns: u64, prob_after: f64) -> BetSample {
        BetSample {
            ts_ns,
            prob_before: prob_after,
            prob_after,
            amount: 1.0,
            shares: 1.0,
            is_limit_order: false,
        }
    }

    const ONE_SEC: u64 = 1_000_000_000;

    #[test]
    fn empty_events_returns_zero() {
        assert_eq!(realized_volatility(&[], ONE_SEC), 0.0);
    }

    #[test]
    fn zero_window_returns_zero() {
        let events = vec![bet(0, 0.5), bet(ONE_SEC, 0.6)];
        assert_eq!(realized_volatility(&events, 0), 0.0);
    }

    #[test]
    fn single_event_in_window_returns_zero() {
        // Only one event is within a 1s window (the second is 5s before the latest).
        let events = vec![bet(0, 0.5), bet(5 * ONE_SEC, 0.6)];
        assert_eq!(realized_volatility(&events, ONE_SEC), 0.0);
    }

    #[test]
    fn two_events_produce_single_return_magnitude() {
        let events = vec![bet(0, 0.5), bet(ONE_SEC, 0.6)];
        let rv = realized_volatility(&events, ONE_SEC);
        // Single return of 0.1 -> RV = sqrt(0.1^2) = 0.1
        assert!((rv - 0.1).abs() < 1e-9, "expected 0.1, got {rv}");
    }

    #[test]
    fn round_trip_has_nonzero_volatility_despite_zero_net_change() {
        // 0.5 -> 0.6 -> 0.5: net change is zero (prob_velocity would read ~0 here), but real
        // movement happened both ways, and RV must reflect that.
        let events = vec![bet(0, 0.5), bet(ONE_SEC, 0.6), bet(2 * ONE_SEC, 0.5)];
        let rv = realized_volatility(&events, 2 * ONE_SEC);
        // Returns: +0.1, -0.1 -> sum of squares = 0.02 -> RV = sqrt(0.02)
        let expected = 0.02_f64.sqrt();
        assert!((rv - expected).abs() < 1e-9, "expected {expected}, got {rv}");
    }

    #[test]
    fn root_sum_of_squares_not_standard_deviation() {
        // Two equal-magnitude returns in the same direction: population stdev of [0.1, 0.1] is
        // 0.0 (no dispersion around the mean), but realized volatility must be nonzero - this is
        // the specific property that distinguishes RV from a plain stdev-of-returns.
        let events = vec![bet(0, 0.5), bet(ONE_SEC, 0.6), bet(2 * ONE_SEC, 0.7)];
        let rv = realized_volatility(&events, 2 * ONE_SEC);
        let expected = (0.1_f64.powi(2) + 0.1_f64.powi(2)).sqrt();
        assert!((rv - expected).abs() < 1e-9, "expected {expected}, got {rv}");
        assert!(rv > 0.0, "RV must be nonzero for a steady drift, unlike stdev");
    }

    #[test]
    fn events_outside_window_are_excluded() {
        let events = vec![
            bet(0, 0.1),              // far outside a 1s window ending at t=3s
            bet(2_500_000_000, 0.5),  // within window (window starts at t=2s)
            bet(3 * ONE_SEC, 0.6),    // latest, within window
        ];
        let rv = realized_volatility(&events, ONE_SEC);
        // Only the 2.5s and 3s events qualify -> one return of 0.1 -> RV = 0.1
        assert!((rv - 0.1).abs() < 1e-9, "expected 0.1, got {rv}");
    }
}
