use crate::{bet_arrival_rate, prob_velocity, realized_volatility};
use common::BetSample;
use probability_engine::MarketTracker;

/// A point-in-time bundle of all Phase 3 feature calculations for one market, matching the
/// `feature_snapshots` table (`implementation.md` §5).
#[derive(Debug, Clone, PartialEq)]
pub struct FeatureSnapshot {
    pub market_id: String,
    pub ts_ns: u64,
    pub prob_velocity: f64,
    pub bet_arrival_rate: f64,
    pub realized_vol: f64,
}

/// Computes a `FeatureSnapshot` for `tracker`'s current state, using the same `window_ns` for all
/// three feature calculations (a caller wanting different windows per feature can call
/// `prob_velocity`/`bet_arrival_rate`/`realized_volatility` directly instead).
///
/// `market_id` and `ts_ns` come from `tracker.state()` (the last-applied event), not from the
/// history window — this snapshot always describes "the market as of its most recent bet," even
/// if that bet fell outside the feature window for some calculation (which none of Phase 3's
/// functions do, since they all anchor the window to the latest event's own timestamp).
///
/// Intended call pattern (see the Task 3.4 integration test): after every
/// `MarketTracker::apply`, call this once to get the matching snapshot — that's what "one
/// `FeatureSnapshot` per state-changing event" means. The live loop that actually drives this
/// continuously belongs to the `collector` binary (Phase 4), per `implementation.md` §3; this
/// crate stays a pure, synchronous calculation library.
pub fn compute_snapshot(tracker: &MarketTracker, window_ns: u64) -> FeatureSnapshot {
    // The ring buffer isn't contiguous in logical order once it wraps, so we still linearize the
    // window — but into `BetSample`s (`Copy`), a single POD `Vec` rather than the per-event storm
    // of `String` allocations the old `iter().cloned()` over `BetEvent`s produced.
    let events: Vec<BetSample> = tracker.history().iter().copied().collect();
    FeatureSnapshot {
        market_id: tracker.state().market_id.clone(),
        ts_ns: tracker.state().last_updated_ns,
        prob_velocity: prob_velocity(&events, window_ns),
        bet_arrival_rate: bet_arrival_rate(&events, window_ns),
        realized_vol: realized_volatility(&events, window_ns),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use common::BetEvent;

    fn bet(market_id: &str, ts_ns: u64, prob_before: f64, prob_after: f64) -> BetEvent {
        BetEvent {
            market_id: market_id.to_string(),
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
    fn one_snapshot_emitted_per_applied_event() {
        let mut tracker = MarketTracker::new("m", 16);
        let events = [
            bet("m", 0, 0.5, 0.5),
            bet("m", ONE_SEC, 0.5, 0.6),
            bet("m", 2 * ONE_SEC, 0.6, 0.5),
        ];

        let mut snapshots = Vec::new();
        for event in &events {
            tracker.apply(event);
            snapshots.push(compute_snapshot(&tracker, 2 * ONE_SEC));
        }

        assert_eq!(snapshots.len(), events.len());
    }

    #[test]
    fn snapshot_fields_match_hand_computed_values() {
        // Same round-trip fixture used in the individual feature tests: 0.5 -> 0.6 -> 0.5.
        let mut tracker = MarketTracker::new("m", 16);
        tracker.apply(&bet("m", 0, 0.5, 0.5));
        tracker.apply(&bet("m", ONE_SEC, 0.5, 0.6));
        tracker.apply(&bet("m", 2 * ONE_SEC, 0.6, 0.5));

        let snapshot = compute_snapshot(&tracker, 2 * ONE_SEC);

        assert_eq!(snapshot.market_id, "m");
        assert_eq!(snapshot.ts_ns, 2 * ONE_SEC);
        // Net change over the window: last.prob_after(0.5) - first.prob_before(0.5) = 0.0.
        assert!(
            snapshot.prob_velocity.abs() < 1e-9,
            "expected ~0 velocity, got {}",
            snapshot.prob_velocity
        );
        // 3 bets within a 2s window -> 1.5/sec.
        assert!(
            (snapshot.bet_arrival_rate - 1.5).abs() < 1e-9,
            "expected 1.5, got {}",
            snapshot.bet_arrival_rate
        );
        // Returns +0.1, -0.1 -> RV = sqrt(0.02), nonzero despite zero net velocity.
        let expected_rv = 0.02_f64.sqrt();
        assert!(
            (snapshot.realized_vol - expected_rv).abs() < 1e-9,
            "expected {expected_rv}, got {}",
            snapshot.realized_vol
        );
    }

    #[test]
    fn snapshot_before_any_apply_is_all_defaults() {
        let tracker = MarketTracker::new("fresh", 16);
        let snapshot = compute_snapshot(&tracker, ONE_SEC);
        assert_eq!(snapshot.market_id, "fresh");
        assert_eq!(snapshot.ts_ns, 0);
        assert_eq!(snapshot.prob_velocity, 0.0);
        assert_eq!(snapshot.bet_arrival_rate, 0.0);
        assert_eq!(snapshot.realized_vol, 0.0);
    }
}
