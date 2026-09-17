use common::BetSample;

/// Rate of change of market-implied probability over the trailing `window_ns`, in probability
/// units per second (e.g. `0.1` means the probability is drifting +10 percentage points/second).
///
/// **Design (net drift, not total movement):** this measures *directional* change — the window's
/// starting probability vs. its ending probability, divided by the window's duration — not the
/// sum of every individual bet's price impact within the window. A market that goes 0.5 -> 0.6 ->
/// 0.5 over the window has velocity ~0 (it round-tripped), even though two bets moved the price.
/// That "how much total movement happened" question is `realized_volatility`'s job (Task 3.3),
/// not this one's — keeping the two features answering different questions is intentional.
///
/// # Preconditions
/// `recent_events` must be sorted oldest-to-newest — the order `BetHistory::iter()` yields.
/// This is not re-validated here (it would cost a sort on every feature calculation for a
/// precondition the caller already guarantees).
///
/// # Edge cases
/// Returns `0.0` if `recent_events` is empty, if `window_ns` is `0` (a zero-width window has no
/// meaningful rate), or if no event falls within the window (shouldn't happen if the caller
/// passes the tail of a `BetHistory`, but handled defensively rather than panicking).
pub fn prob_velocity(recent_events: &[BetSample], window_ns: u64) -> f64 {
    if window_ns == 0 {
        return 0.0;
    }
    let Some(latest) = recent_events.last() else {
        return 0.0;
    };
    let window_start = latest.ts_ns.saturating_sub(window_ns);
    // `recent_events` is sorted oldest→newest, so the in-window tail is a contiguous suffix found
    // in O(log n) — no per-call allocation (the old `Vec<&BetEvent>` collect was a hot-path alloc).
    let start = recent_events.partition_point(|e| e.ts_ns < window_start);
    let Some(first) = recent_events[start..].first() else {
        return 0.0;
    };
    let delta_prob = latest.prob_after - first.prob_before;
    let window_secs = window_ns as f64 / 1_000_000_000.0;
    delta_prob / window_secs
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(ts_ns: u64, prob_before: f64, prob_after: f64) -> BetSample {
        BetSample {
            ts_ns,
            prob_before,
            prob_after,
            amount: 1.0,
            shares: 1.0,
            is_limit_order: false,
        }
    }

    const ONE_SEC: u64 = 1_000_000_000;

    #[test]
    fn empty_events_returns_zero() {
        assert_eq!(prob_velocity(&[], ONE_SEC), 0.0);
    }

    #[test]
    fn zero_window_returns_zero() {
        let events = vec![bet(ONE_SEC, 0.5, 0.6)];
        assert_eq!(prob_velocity(&events, 0), 0.0);
    }

    #[test]
    fn single_event_in_window_uses_its_own_delta() {
        let events = vec![bet(5 * ONE_SEC, 0.5, 0.6)];
        let v = prob_velocity(&events, ONE_SEC);
        assert!((v - 0.1).abs() < 1e-9, "expected 0.1, got {v}");
    }

    #[test]
    fn events_outside_window_are_excluded() {
        let events = vec![
            bet(0, 0.4, 0.5),                // t=0s: outside a 1s window ending at t=2s
            bet(500_000_000, 0.5, 0.55),      // t=0.5s: also outside (window starts at t=1s)
            bet(2 * ONE_SEC, 0.6, 0.7),       // t=2s: latest, within window
        ];
        let v = prob_velocity(&events, ONE_SEC);
        // Only the t=2s event qualifies (window_start = 2s - 1s = 1s); its own delta applies.
        assert!((v - 0.1).abs() < 1e-9, "expected 0.1, got {v}");
    }

    #[test]
    fn multiple_events_in_window_uses_net_change_not_sum_of_deltas() {
        let events = vec![
            bet(0, 0.5, 0.6),
            bet(500_000_000, 0.6, 0.55),
            bet(ONE_SEC, 0.55, 0.8),
        ];
        let v = prob_velocity(&events, 2 * ONE_SEC);
        // Net change = last.prob_after(0.8) - first.prob_before(0.5) = 0.3, over 2s = 0.15/sec.
        // NOT the sum of individual |deltas| (0.1 + 0.05 + 0.25 = 0.4), which would answer a
        // "total movement" question rather than "net drift."
        assert!((v - 0.15).abs() < 1e-9, "expected 0.15, got {v}");
    }

    #[test]
    fn negative_drift_produces_negative_velocity() {
        let events = vec![bet(ONE_SEC, 0.8, 0.6)];
        let v = prob_velocity(&events, ONE_SEC);
        assert!((v - (-0.2)).abs() < 1e-9, "expected -0.2, got {v}");
    }
}
