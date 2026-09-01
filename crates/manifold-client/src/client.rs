use crate::error::ManifoldClientError;
use crate::types::{Bet, BetsQuery, Market};

const DEFAULT_BASE_URL: &str = "https://api.manifold.markets/v0";

/// REST client for Manifold's public API. All read endpoints wrapped here need no
/// authentication (verified live — see `docs/metaculus-tos-check.md` for the equivalent
/// Manifold check and `implementation.md` §6).
pub struct ManifoldClient {
    http: reqwest::Client,
    base_url: String,
}

impl Default for ManifoldClient {
    fn default() -> Self {
        Self::new()
    }
}

impl ManifoldClient {
    pub fn new() -> Self {
        Self {
            http: reqwest::Client::new(),
            base_url: DEFAULT_BASE_URL.to_string(),
        }
    }

    /// Points the client at a different base URL — used in tests to target a mock server.
    pub fn with_base_url(base_url: impl Into<String>) -> Self {
        Self {
            http: reqwest::Client::new(),
            base_url: base_url.into(),
        }
    }

    pub async fn get_markets(&self) -> Result<Vec<Market>, ManifoldClientError> {
        let url = format!("{}/markets", self.base_url);
        let response = self.http.get(url).send().await?.error_for_status()?;
        Ok(response.json().await?)
    }

    pub async fn get_bets(&self, query: &BetsQuery) -> Result<Vec<Bet>, ManifoldClientError> {
        let url = format!("{}/bets", self.base_url);
        let response = self
            .http
            .get(url)
            .query(query)
            .send()
            .await?
            .error_for_status()?;
        Ok(response.json().await?)
    }

    pub async fn get_resolved_markets(&self) -> Result<Vec<Market>, ManifoldClientError> {
        let url = format!("{}/search-markets", self.base_url);
        let response = self
            .http
            .get(url)
            .query(&[("term", ""), ("filter", "resolved")])
            .send()
            .await?
            .error_for_status()?;
        Ok(response.json().await?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use wiremock::matchers::{method, path, query_param};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    #[tokio::test]
    async fn get_markets_deserializes_binary_market() {
        let server = MockServer::start().await;
        let fixture = serde_json::json!([{
            "id": "abc123",
            "question": "Will it rain?",
            "closeTime": 1798761540000i64,
            "createdTime": 1788141435574i64,
            "outcomeType": "BINARY",
            "mechanism": "cpmm-1",
            "probability": 0.65,
            "isResolved": false,
            "volume": 100.0,
            "totalLiquidity": 1000.0
        }]);
        Mock::given(method("GET"))
            .and(path("/markets"))
            .respond_with(ResponseTemplate::new(200).set_body_json(fixture))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        let markets = client.get_markets().await.unwrap();

        assert_eq!(markets.len(), 1);
        assert_eq!(markets[0].id, "abc123");
        assert_eq!(markets[0].probability, Some(0.65));
        assert!(!markets[0].is_resolved);
    }

    #[tokio::test]
    async fn get_markets_handles_multiple_choice_market_without_probability() {
        let server = MockServer::start().await;
        // Real fixture: MULTIPLE_CHOICE markets have no top-level `probability` or `pool`.
        let fixture = serde_json::json!([{
            "id": "0l8Puy5UtA",
            "question": "August 2026 AI model releases",
            "closeTime": 1788220740000i64,
            "createdTime": 1785592643401i64,
            "outcomeType": "MULTIPLE_CHOICE",
            "mechanism": "cpmm-multi-1",
            "isResolved": true,
            "resolution": "MKT",
            "resolutionTime": 1788228668859i64,
            "volume": 39678.93,
            "totalLiquidity": 1913.0
        }]);
        Mock::given(method("GET"))
            .and(path("/markets"))
            .respond_with(ResponseTemplate::new(200).set_body_json(fixture))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        let markets = client.get_markets().await.unwrap();

        assert_eq!(markets[0].probability, None);
        assert_eq!(markets[0].resolution.as_deref(), Some("MKT"));
    }

    #[tokio::test]
    async fn get_bets_sends_contract_id_query_param_and_deserializes() {
        let server = MockServer::start().await;
        let fixture = serde_json::json!([{
            "id": "bet1",
            "contractId": "abc123",
            "createdTime": 1788229750724i64,
            "probBefore": 0.5,
            "probAfter": 0.52,
            "amount": 10.0,
            "shares": 19.2,
            "isFilled": true,
            "isCancelled": false
        }]);
        Mock::given(method("GET"))
            .and(path("/bets"))
            .and(query_param("contractId", "abc123"))
            .respond_with(ResponseTemplate::new(200).set_body_json(fixture))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        let query = BetsQuery {
            contract_id: Some("abc123".to_string()),
            ..Default::default()
        };
        let bets = client.get_bets(&query).await.unwrap();

        assert_eq!(bets.len(), 1);
        assert_eq!(bets[0].contract_id, "abc123");
        assert_eq!(bets[0].prob_after, 0.52);
    }

    #[tokio::test]
    async fn get_bets_deserializes_unfilled_limit_order() {
        let server = MockServer::start().await;
        // Real fixture: a pending (unfilled) limit order has amount=shares=0 and probBefore ==
        // probAfter, plus a limitProb field absent from AMM-cleared bets.
        let fixture = serde_json::json!([{
            "id": "Z2hO5S5OuP2t",
            "contractId": "Df90dc2c2e",
            "createdTime": 1788229750724i64,
            "probBefore": 0.46,
            "probAfter": 0.46,
            "amount": 0,
            "shares": 0,
            "isFilled": false,
            "isCancelled": false,
            "limitProb": 0.55
        }]);
        Mock::given(method("GET"))
            .and(path("/bets"))
            .respond_with(ResponseTemplate::new(200).set_body_json(fixture))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        let bets = client.get_bets(&BetsQuery::default()).await.unwrap();

        assert_eq!(bets[0].limit_prob, Some(0.55));
        assert_eq!(bets[0].is_filled, Some(false));
    }

    #[tokio::test]
    async fn get_resolved_markets_sends_expected_query_and_deserializes() {
        let server = MockServer::start().await;
        let fixture = serde_json::json!([{
            "id": "resolved1",
            "question": "Did X happen?",
            "closeTime": 1788211854501i64,
            "createdTime": 1787970333676i64,
            "outcomeType": "BINARY",
            "mechanism": "cpmm-1",
            "probability": 0.99,
            "isResolved": true,
            "resolution": "YES",
            "resolutionTime": 1788211854501i64,
            "volume": 500.0,
            "totalLiquidity": 1000.0
        }]);
        Mock::given(method("GET"))
            .and(path("/search-markets"))
            .and(query_param("filter", "resolved"))
            .respond_with(ResponseTemplate::new(200).set_body_json(fixture))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        let markets = client.get_resolved_markets().await.unwrap();

        assert_eq!(markets.len(), 1);
        assert!(markets[0].is_resolved);
        assert_eq!(markets[0].resolution.as_deref(), Some("YES"));
    }

    #[tokio::test]
    async fn non_2xx_response_returns_error() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .and(path("/markets"))
            .respond_with(ResponseTemplate::new(500))
            .mount(&server)
            .await;

        let client = ManifoldClient::with_base_url(server.uri());
        assert!(client.get_markets().await.is_err());
    }
}
