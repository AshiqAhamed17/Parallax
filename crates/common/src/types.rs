use serde::{Deserialize, Serialize};

/// A single bet observed on a Manifold market, normalized for the probability engine.
///
/// This is the internal, storage-facing shape (see `implementation.md` §5, the `bets` table),
/// distinct from `manifold_client::Bet`, which mirrors Manifold's wire format. The collector
/// converts the wire type into this before handing it to the probability engine, so the engine
/// and everything downstream depend only on `common`, not on the client crate's API surface.
///
/// `prob_before`/`prob_after` are the market-implied probability immediately before and after
/// this bet applied — on Manifold's CPMM these are the primary signal, since there is no order
/// book to reconstruct depth from (see `implementation.md` §7).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BetEvent {
    pub market_id: String,
    /// Nanoseconds since the Unix epoch. Manifold's API reports millisecond `createdTime`; the
    /// collector scales it to nanoseconds so all timestamps in the pipeline share one unit.
    pub ts_ns: u64,
    pub prob_before: f64,
    pub prob_after: f64,
    pub amount: f64,
    pub shares: f64,
    /// True if this bet came from Manifold's limit-order layer rather than clearing directly
    /// against the AMM curve. Kept as a minor secondary signal only (see `implementation.md` §6).
    pub is_limit_order: bool,
}

/// The numeric payload of a `BetEvent` with the `market_id` dropped — a `Copy`, allocation-free
/// record for the per-market rolling history buffer (`probability_engine::BetHistory`) and the
/// feature calculations.
///
/// Every bet stored in a market's history necessarily has that same `market_id`, so keeping a
/// heap-allocated `String` copy of it in every buffered entry is pure waste (it dominated the v1
/// profile — see `benchmarks/v1-profile-notes.md`). `BetSample` holds only the fields the feature
/// engine actually reads, is `Copy`, and never touches the heap, so pushing into the ring buffer
/// and snapshotting the window are allocation-free.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct BetSample {
    pub ts_ns: u64,
    pub prob_before: f64,
    pub prob_after: f64,
    pub amount: f64,
    pub shares: f64,
    pub is_limit_order: bool,
}

impl From<&BetEvent> for BetSample {
    fn from(e: &BetEvent) -> Self {
        Self {
            ts_ns: e.ts_ns,
            prob_before: e.prob_before,
            prob_after: e.prob_after,
            amount: e.amount,
            shares: e.shares,
            is_limit_order: e.is_limit_order,
        }
    }
}

/// The current probability state of a single market, maintained by the probability engine as
/// bets stream in. This is the compact "where is the market right now" snapshot; the rolling
/// window of recent `BetEvent`s used to derive velocity/volatility features lives alongside it in
/// the `probability-engine` crate (Task 2.3), not here.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MarketState {
    pub market_id: String,
    /// Latest market-implied probability, in [0.0, 1.0].
    pub current_prob: f64,
    /// `ts_ns` of the most recent bet applied to this state (nanoseconds since the Unix epoch).
    pub last_updated_ns: u64,
}

impl MarketState {
    /// A fresh state for `market_id` with no bets applied yet. `current_prob` starts at 0.5 (the
    /// uninformative prior) and `last_updated_ns` at 0; both are overwritten by the first `apply`.
    pub fn new(market_id: impl Into<String>) -> Self {
        Self {
            market_id: market_id.into(),
            current_prob: 0.5,
            last_updated_ns: 0,
        }
    }

    /// Applies a bet to this state: the post-bet market-implied probability becomes
    /// `event.prob_after`, and `last_updated_ns` advances to the event's timestamp.
    ///
    /// This is the pure scalar update — it does NOT touch any rolling bet-history buffer, since
    /// `MarketState` is the compact, serializable snapshot (see `implementation.md` §7). The
    /// buffer-aware update lives on `probability_engine::MarketTracker::apply`, which calls this.
    ///
    /// Assumes events are applied in chronological order (last-write-wins); the collector feeds
    /// events in receive order and the backtester replays them chronologically, so this holds.
    pub fn apply(&mut self, event: &BetEvent) {
        self.current_prob = event.prob_after;
        self.last_updated_ns = event.ts_ns;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bet_event_round_trips_through_json() {
        let event = BetEvent {
            market_id: "abc123".to_string(),
            ts_ns: 1_788_230_563_750_000_000,
            prob_before: 0.9,
            prob_after: 0.8734432128081484,
            amount: -621.52,
            shares: -700.38,
            is_limit_order: false,
        };

        let json = serde_json::to_string(&event).unwrap();
        let decoded: BetEvent = serde_json::from_str(&json).unwrap();

        assert_eq!(event, decoded);
    }

    #[test]
    fn bet_event_round_trips_a_limit_order() {
        let event = BetEvent {
            market_id: "Df90dc2c2e".to_string(),
            ts_ns: 1_788_229_750_724_000_000,
            prob_before: 0.46,
            prob_after: 0.46,
            amount: 0.0,
            shares: 0.0,
            is_limit_order: true,
        };

        let decoded: BetEvent = serde_json::from_str(&serde_json::to_string(&event).unwrap()).unwrap();

        assert_eq!(event, decoded);
        assert!(decoded.is_limit_order);
    }

    fn bet(ts_ns: u64, prob_after: f64) -> BetEvent {
        BetEvent {
            market_id: "m".to_string(),
            ts_ns,
            prob_before: 0.5,
            prob_after,
            amount: 10.0,
            shares: 15.0,
            is_limit_order: false,
        }
    }

    #[test]
    fn bet_sample_drops_market_id_but_keeps_numeric_fields() {
        let event = bet(1_234, 0.73);
        let sample: BetSample = (&event).into();
        assert_eq!(sample.ts_ns, event.ts_ns);
        assert_eq!(sample.prob_before, event.prob_before);
        assert_eq!(sample.prob_after, event.prob_after);
        assert_eq!(sample.amount, event.amount);
        assert_eq!(sample.shares, event.shares);
        assert_eq!(sample.is_limit_order, event.is_limit_order);
    }

    #[test]
    fn new_market_state_starts_at_uninformative_prior() {
        let state = MarketState::new("m");
        assert_eq!(state.current_prob, 0.5);
        assert_eq!(state.last_updated_ns, 0);
        assert_eq!(state.market_id, "m");
    }

    #[test]
    fn apply_sets_current_prob_to_prob_after_and_advances_timestamp() {
        let mut state = MarketState::new("m");
        state.apply(&bet(100, 0.7));
        assert_eq!(state.current_prob, 0.7);
        assert_eq!(state.last_updated_ns, 100);

        state.apply(&bet(200, 0.42));
        assert_eq!(state.current_prob, 0.42);
        assert_eq!(state.last_updated_ns, 200);
    }

    #[test]
    fn market_state_round_trips_through_json() {
        let state = MarketState {
            market_id: "abc123".to_string(),
            current_prob: 0.65,
            last_updated_ns: 1_788_230_563_750_000_000,
        };

        let json = serde_json::to_string(&state).unwrap();
        let decoded: MarketState = serde_json::from_str(&json).unwrap();

        assert_eq!(state, decoded);
    }
}
