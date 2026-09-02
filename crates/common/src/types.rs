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
