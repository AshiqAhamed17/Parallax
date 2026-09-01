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
