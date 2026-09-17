use crate::tracker::MarketTracker;
use common::BetEvent;
use std::collections::HashMap;

/// The multi-market probability engine: one `MarketTracker` per market, created lazily the first
/// time a bet for that market is seen. This is what the collector (Phase 4) drives from the live
/// Manifold event stream — it accepts `common::BetEvent`s and never touches Manifold wire types,
/// keeping the engine decoupled from `manifold-client` in production.
#[derive(Debug, Clone)]
pub struct ProbabilityEngine {
    /// Ring-buffer capacity handed to each market's `MarketTracker` on creation.
    history_capacity: usize,
    markets: HashMap<String, MarketTracker>,
}

impl ProbabilityEngine {
    /// Creates an engine whose per-market history windows each retain `history_capacity` bets.
    pub fn new(history_capacity: usize) -> Self {
        Self {
            history_capacity,
            markets: HashMap::new(),
        }
    }

    /// Routes `event` to its market's tracker, creating the tracker on first sight of that market.
    ///
    /// Looks the tracker up by reference first (`get_mut`) so the steady-state path — the market
    /// already exists — allocates nothing. `HashMap::entry` was cloning `market_id` into an owned
    /// `String` on *every* bet just to look it up; the clone now happens only on the rare
    /// first-sight insert.
    pub fn apply(&mut self, event: &BetEvent) {
        if let Some(tracker) = self.markets.get_mut(&event.market_id) {
            tracker.apply(event);
        } else {
            let mut tracker = MarketTracker::new(event.market_id.clone(), self.history_capacity);
            tracker.apply(event);
            self.markets.insert(event.market_id.clone(), tracker);
        }
    }

    /// The tracker for `market_id`, or `None` if no bet for it has been applied yet.
    pub fn market(&self, market_id: &str) -> Option<&MarketTracker> {
        self.markets.get(market_id)
    }

    /// Number of distinct markets currently tracked.
    pub fn market_count(&self) -> usize {
        self.markets.len()
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
            amount: 5.0,
            shares: 9.0,
            is_limit_order: false,
        }
    }

    #[test]
    fn routes_events_to_separate_markets() {
        let mut engine = ProbabilityEngine::new(16);
        engine.apply(&bet("a", 100, 0.6));
        engine.apply(&bet("b", 110, 0.3));
        engine.apply(&bet("a", 120, 0.7));

        assert_eq!(engine.market_count(), 2);
        assert_eq!(engine.market("a").unwrap().state().current_prob, 0.7);
        assert_eq!(engine.market("a").unwrap().state().last_updated_ns, 120);
        assert_eq!(engine.market("b").unwrap().state().current_prob, 0.3);
        // Market "a" saw two bets, "b" saw one.
        assert_eq!(engine.market("a").unwrap().history().len(), 2);
        assert_eq!(engine.market("b").unwrap().history().len(), 1);
    }

    #[test]
    fn unknown_market_returns_none() {
        let engine = ProbabilityEngine::new(16);
        assert!(engine.market("nope").is_none());
        assert_eq!(engine.market_count(), 0);
    }
}
