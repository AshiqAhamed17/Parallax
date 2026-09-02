//! Task 2.6 — differential property tests.
//!
//! Generates random `BetEvent` sequences and replays each through both the real
//! `common::MarketState` (incremental O(1) update) and the `NaiveMarketState` reference
//! (fold-from-scratch). After every single event, the two must agree on `current_prob` and
//! `last_updated_ns`. Run locally with `PROPTEST_CASES=10000` before considering Phase 2 done.

use crate::naive::NaiveMarketState;
use common::{BetEvent, MarketState};
use proptest::prelude::*;

/// A single bet for market "m". `prob_after` is constrained to a valid probability; `amount`/
/// `shares` are bounded finite values (their exact value doesn't affect the compared state, but
/// unbounded `any::<f64>()` would allow NaN and muddy the fixture without adding coverage).
fn bet_strategy() -> impl Strategy<Value = BetEvent> {
    (
        any::<u64>(),
        0.0f64..=1.0,
        -1_000_000.0f64..=1_000_000.0,
        -1_000_000.0f64..=1_000_000.0,
        any::<bool>(),
    )
        .prop_map(
            |(ts_ns, prob_after, amount, shares, is_limit_order)| BetEvent {
                market_id: "m".to_string(),
                ts_ns,
                prob_before: 0.5,
                prob_after,
                amount,
                shares,
                is_limit_order,
            },
        )
}

proptest! {
    #[test]
    fn optimized_market_state_matches_naive_after_every_event(
        events in prop::collection::vec(bet_strategy(), 0..200)
    ) {
        let mut optimized = MarketState::new("m");
        let mut naive = NaiveMarketState::new("m");

        for event in &events {
            optimized.apply(event);
            naive.apply(event);
            // Exact equality is correct here: both paths assign `prob_after`/`ts_ns` verbatim
            // (no arithmetic), so any divergence is a real bug, not float drift.
            prop_assert_eq!(optimized.current_prob, naive.current_prob());
            prop_assert_eq!(optimized.last_updated_ns, naive.last_updated_ns());
        }
    }
}
