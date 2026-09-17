use common::BetSample;

/// Number of bets per second over the trailing `window_ns`, counted relative to the timestamp of
/// the most recent event (not wall-clock "now" — the pipeline has no independent clock input
/// here, only the event stream itself).
///
/// # Preconditions
/// `recent_events` must be sorted oldest-to-newest — the order `BetHistory::iter()` yields.
///
/// # Edge cases
/// Returns `0.0` if `recent_events` is empty or `window_ns` is `0`.
pub fn bet_arrival_rate(recent_events: &[BetSample], window_ns: u64) -> f64 {
    if window_ns == 0 {
        return 0.0;
    }
    let Some(latest) = recent_events.last() else {
        return 0.0;
    };
    let window_start = latest.ts_ns.saturating_sub(window_ns);
    // Sorted oldest→newest, so the in-window count is just the length of the suffix at/after
    // `window_start` — an O(log n) binary search instead of an O(n) scan.
    let count = recent_events.len() - recent_events.partition_point(|e| e.ts_ns < window_start);
    let window_secs = window_ns as f64 / 1_000_000_000.0;
    count as f64 / window_secs
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(ts_ns: u64) -> BetSample {
        BetSample {
            ts_ns,
            prob_before: 0.5,
            prob_after: 0.5,
            amount: 1.0,
            shares: 1.0,
            is_limit_order: false,
        }
    }

    const ONE_SEC: u64 = 1_000_000_000;

    #[test]
    fn empty_events_returns_zero() {
        assert_eq!(bet_arrival_rate(&[], ONE_SEC), 0.0);
    }

    #[test]
    fn zero_window_returns_zero() {
        assert_eq!(bet_arrival_rate(&[bet(0)], 0), 0.0);
    }

    #[test]
    fn single_event_over_one_second_window_is_one_per_second() {
        let rate = bet_arrival_rate(&[bet(ONE_SEC)], ONE_SEC);
        assert!((rate - 1.0).abs() < 1e-9, "expected 1.0, got {rate}");
    }

    #[test]
    fn counts_only_events_within_window() {
        let events = vec![
            bet(0),                 // t=0s: outside (window starts at t=2s)
            bet(2_500_000_000),     // t=2.5s: within window
            bet(3 * ONE_SEC),       // t=3s: latest, within window
        ];
        let rate = bet_arrival_rate(&events, ONE_SEC); // window_start = 3s - 1s = 2s
        assert!((rate - 2.0).abs() < 1e-9, "expected 2.0, got {rate}");
    }

    #[test]
    fn all_events_within_a_wide_window() {
        let events = vec![bet(0), bet(ONE_SEC), bet(2 * ONE_SEC)];
        let rate = bet_arrival_rate(&events, 10 * ONE_SEC); // 10s window, all 3 qualify
        assert!((rate - 0.3).abs() < 1e-9, "expected 0.3, got {rate}");
    }
}
