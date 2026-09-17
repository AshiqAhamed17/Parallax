use crate::history::BetHistory;
use common::{BetEvent, MarketState};

/// Owns the full runtime state for a single market: the compact `MarketState` snapshot plus the
/// rolling `BetHistory` window the feature engine reads. One tracker exists per market.
///
/// This is the buffer-aware counterpart to `common::MarketState::apply` (the pure scalar update).
/// `implementation.md` §7 keeps `MarketState` a serializable snapshot in `common` and locates the
/// ring buffer here in `probability-engine`; `MarketTracker` is where the two are combined.
#[derive(Debug, Clone)]
pub struct MarketTracker {
    state: MarketState,
    history: BetHistory,
}

impl MarketTracker {
    /// Creates a tracker for `market_id` whose history retains at most `history_capacity` bets.
    pub fn new(market_id: impl Into<String>, history_capacity: usize) -> Self {
        let market_id = market_id.into();
        Self {
            state: MarketState::new(market_id),
            history: BetHistory::new(history_capacity),
        }
    }

    /// Applies a bet: updates the scalar `MarketState` (via `MarketState::apply`) and pushes the
    /// event into the rolling history window (evicting the oldest if at capacity).
    ///
    /// Assumes events are applied in chronological order (see `MarketState::apply`). In debug
    /// builds, asserts the event belongs to this tracker's market — a mismatch means the collector
    /// routed a bet to the wrong tracker, which is a bug worth catching early.
    pub fn apply(&mut self, event: &BetEvent) {
        debug_assert_eq!(
            event.market_id, self.state.market_id,
            "bet for market {} applied to tracker for market {}",
            event.market_id, self.state.market_id
        );
        self.state.apply(event);
        // `BetSample::from(&BetEvent)` drops the redundant `market_id` and is a plain field copy —
        // no per-bet String allocation (the top v1 hotspot).
        self.history.push(event.into());
    }

    /// The current compact state snapshot.
    pub fn state(&self) -> &MarketState {
        &self.state
    }

    /// The rolling window of recent bets, oldest → newest.
    pub fn history(&self) -> &BetHistory {
        &self.history
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(market_id: &str, ts_ns: u64, prob_after: f64) -> BetEvent {
        BetEvent {
            market_id: market_id.to_string(),
            ts_ns,
            prob_before: 0.5,
            prob_after,
            amount: 10.0,
            shares: 15.0,
            is_limit_order: false,
        }
    }

    #[test]
    fn apply_updates_state_to_latest_bet() {
        let mut tracker = MarketTracker::new("m", 8);
        tracker.apply(&bet("m", 100, 0.6));
        tracker.apply(&bet("m", 200, 0.55));
        tracker.apply(&bet("m", 300, 0.8));

        assert_eq!(tracker.state().current_prob, 0.8);
        assert_eq!(tracker.state().last_updated_ns, 300);
        assert_eq!(tracker.state().market_id, "m");
    }

    #[test]
    fn apply_records_events_into_history_in_order() {
        let mut tracker = MarketTracker::new("m", 8);
        for (ts, p) in [(100, 0.6), (200, 0.55), (300, 0.8)] {
            tracker.apply(&bet("m", ts, p));
        }

        let seen: Vec<(u64, f64)> = tracker
            .history()
            .iter()
            .map(|e| (e.ts_ns, e.prob_after))
            .collect();
        assert_eq!(seen, vec![(100, 0.6), (200, 0.55), (300, 0.8)]);
    }

    #[test]
    fn history_stays_bounded_while_state_still_reflects_latest() {
        let mut tracker = MarketTracker::new("m", 2);
        for ts in 1..=5 {
            tracker.apply(&bet("m", ts, ts as f64 / 10.0));
        }

        // History is capped at 2, holding only the two most recent bets...
        assert_eq!(tracker.history().len(), 2);
        let ts: Vec<u64> = tracker.history().iter().map(|e| e.ts_ns).collect();
        assert_eq!(ts, vec![4, 5]);

        // ...but the scalar state still reflects the very latest bet, independent of the window.
        assert_eq!(tracker.state().current_prob, 0.5);
        assert_eq!(tracker.state().last_updated_ns, 5);
    }

    #[test]
    #[should_panic(expected = "applied to tracker for market")]
    fn applying_a_foreign_market_event_panics_in_debug() {
        let mut tracker = MarketTracker::new("m", 4);
        tracker.apply(&bet("other", 100, 0.6));
    }
}
