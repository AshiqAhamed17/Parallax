use serde::{Deserialize, Serialize};

/// A market as returned by Manifold's `/v0/markets` and `/v0/search-markets`.
///
/// `probability`, `pool`, and `total_liquidity` are absent on non-BINARY markets (e.g.
/// `MULTIPLE_CHOICE`), so they're optional rather than causing deserialization to fail.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Market {
    pub id: String,
    pub question: String,
    pub close_time: Option<i64>,
    pub created_time: i64,
    pub outcome_type: String,
    pub mechanism: String,
    #[serde(default)]
    pub probability: Option<f64>,
    pub is_resolved: bool,
    #[serde(default)]
    pub resolution: Option<String>,
    #[serde(default)]
    pub resolution_time: Option<i64>,
    #[serde(default)]
    pub volume: Option<f64>,
    #[serde(default)]
    pub total_liquidity: Option<f64>,
}

/// A bet as returned by Manifold's `/v0/bets`. Covers both AMM-cleared bets and limit orders
/// (`limit_prob` is present only for the latter; see `implementation.md` §6).
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Bet {
    pub id: String,
    pub contract_id: String,
    pub created_time: i64,
    pub prob_before: f64,
    pub prob_after: f64,
    pub amount: f64,
    pub shares: f64,
    #[serde(default)]
    pub is_filled: Option<bool>,
    #[serde(default)]
    pub is_cancelled: Option<bool>,
    #[serde(default)]
    pub limit_prob: Option<f64>,
}

/// Converts a Manifold wire `Bet` into the pipeline's internal `common::BetEvent`. This is the
/// wire→domain boundary: everything downstream (probability engine, collector, backtester) works
/// in `common` types, never in `manifold-client`'s wire types.
///
/// - `created_time` is Manifold's millisecond epoch; scaled to nanoseconds (clamped at 0 to guard
///   against a nonsensical negative timestamp rather than wrapping through `as u64`).
/// - `is_limit_order` is derived from the presence of `limit_prob`: Manifold only sets it on bets
///   originating from the limit-order layer, not AMM-cleared bets (see `implementation.md` §6).
impl From<&Bet> for common::BetEvent {
    fn from(bet: &Bet) -> Self {
        common::BetEvent {
            market_id: bet.contract_id.clone(),
            ts_ns: (bet.created_time.max(0) as u64) * 1_000_000,
            prob_before: bet.prob_before,
            prob_after: bet.prob_after,
            amount: bet.amount,
            shares: bet.shares,
            is_limit_order: bet.limit_prob.is_some(),
        }
    }
}

/// Query parameters for `GET /v0/bets`. Fields left as `None` are omitted from the request.
#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BetsQuery {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub contract_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub before: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_bet() -> Bet {
        Bet {
            id: "bet1".to_string(),
            contract_id: "mkt1".to_string(),
            created_time: 1_788_230_563_750, // ms
            prob_before: 0.5,
            prob_after: 0.52,
            amount: 10.0,
            shares: 19.2,
            is_filled: Some(true),
            is_cancelled: Some(false),
            limit_prob: None,
        }
    }

    #[test]
    fn amm_bet_converts_to_bet_event_with_ms_scaled_to_ns() {
        let event: common::BetEvent = (&base_bet()).into();
        assert_eq!(event.market_id, "mkt1");
        assert_eq!(event.ts_ns, 1_788_230_563_750_000_000); // ms * 1_000_000
        assert_eq!(event.prob_before, 0.5);
        assert_eq!(event.prob_after, 0.52);
        assert_eq!(event.amount, 10.0);
        assert_eq!(event.shares, 19.2);
        assert!(!event.is_limit_order);
    }

    #[test]
    fn presence_of_limit_prob_marks_it_a_limit_order() {
        let bet = Bet {
            limit_prob: Some(0.55),
            ..base_bet()
        };
        let event: common::BetEvent = (&bet).into();
        assert!(event.is_limit_order);
    }

    #[test]
    fn negative_created_time_clamps_to_zero_instead_of_wrapping() {
        let bet = Bet {
            created_time: -1,
            ..base_bet()
        };
        let event: common::BetEvent = (&bet).into();
        assert_eq!(event.ts_ns, 0);
    }
}
