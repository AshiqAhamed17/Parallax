//! Deliberately-inefficient reference implementation of single-market state, used ONLY as the
//! oracle for the differential property tests (Task 2.6). It is `#[cfg(test)]`-gated in `lib.rs`
//! so it never enters the production build.
//!
//! Where `common::MarketState` updates incrementally in O(1), `NaiveMarketState` keeps the entire
//! event log and recomputes its state from scratch by folding over every event on each `apply`.
//! Two independent implementations that must always agree is the whole point: if a future
//! optimization of the real engine (Phase 6) introduces a bug, the fold-from-scratch reference
//! won't share it, and the property test fails.

use common::BetEvent;

pub struct NaiveMarketState {
    market_id: String,
    events: Vec<BetEvent>,
    current_prob: f64,
    last_updated_ns: u64,
}

impl NaiveMarketState {
    pub fn new(market_id: impl Into<String>) -> Self {
        Self {
            market_id: market_id.into(),
            events: Vec::new(),
            current_prob: 0.5,
            last_updated_ns: 0,
        }
    }

    /// Appends the event, then recomputes state from scratch by folding the *entire* history.
    pub fn apply(&mut self, event: &BetEvent) {
        self.events.push(event.clone());

        let mut current_prob = 0.5;
        let mut last_updated_ns = 0;
        for e in &self.events {
            current_prob = e.prob_after;
            last_updated_ns = e.ts_ns;
        }
        self.current_prob = current_prob;
        self.last_updated_ns = last_updated_ns;
    }

    pub fn current_prob(&self) -> f64 {
        self.current_prob
    }

    pub fn last_updated_ns(&self) -> u64 {
        self.last_updated_ns
    }

    #[allow(dead_code)]
    pub fn market_id(&self) -> &str {
        &self.market_id
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(ts_ns: u64, prob_after: f64) -> BetEvent {
        BetEvent {
            market_id: "m".to_string(),
            ts_ns,
            prob_before: 0.5,
            prob_after,
            amount: 1.0,
            shares: 1.0,
            is_limit_order: false,
        }
    }

    #[test]
    fn fresh_state_starts_at_prior() {
        let naive = NaiveMarketState::new("m");
        assert_eq!(naive.current_prob(), 0.5);
        assert_eq!(naive.last_updated_ns(), 0);
    }

    #[test]
    fn folds_to_the_latest_event() {
        let mut naive = NaiveMarketState::new("m");
        naive.apply(&bet(100, 0.6));
        naive.apply(&bet(200, 0.42));
        naive.apply(&bet(300, 0.9));
        assert_eq!(naive.current_prob(), 0.9);
        assert_eq!(naive.last_updated_ns(), 300);
    }
}
