use crate::types::Bet;
use futures_util::{Stream, StreamExt, SinkExt};
use serde::Deserialize;
use tokio_tungstenite::tungstenite::Message;

const DEFAULT_WS_URL: &str = "wss://api.manifold.markets/ws";

/// A parsed message from Manifold's WebSocket, verified live against the real API:
/// `{"type":"ack","txid":1,"success":true}` confirms a subscribe request, and
/// `{"type":"broadcast","topic":"global/new-bet","data":{"bets":[...]}}` carries one or more
/// bets (a single broadcast can contain multiple bets, e.g. from a bet group).
#[derive(Debug, Clone)]
pub enum ManifoldWsEvent {
    Ack { txid: u64, success: bool },
    NewBets { topic: String, bets: Vec<Bet> },
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum RawWsMessage {
    Ack { txid: u64, success: bool },
    Broadcast { topic: String, data: BroadcastData },
}

#[derive(Debug, Deserialize)]
struct BroadcastData {
    #[serde(default)]
    bets: Vec<Bet>,
}

impl From<RawWsMessage> for ManifoldWsEvent {
    fn from(raw: RawWsMessage) -> Self {
        match raw {
            RawWsMessage::Ack { txid, success } => ManifoldWsEvent::Ack { txid, success },
            RawWsMessage::Broadcast { topic, data } => ManifoldWsEvent::NewBets {
                topic,
                bets: data.bets,
            },
        }
    }
}

/// Connects to Manifold's public WebSocket and subscribes to the given topics (e.g.
/// `"global/new-bet"`). The returned stream yields both `Ack` (subscription confirmation) and
/// `NewBets` events in the order received; it ends when the connection closes or errors.
///
/// Malformed/unrecognized text frames are silently skipped rather than terminating the stream —
/// there's no `Result` in the item type to surface a parse error through, and a single stray
/// frame shouldn't kill an otherwise-healthy connection. Non-text frames (ping/pong/binary) are
/// also skipped; the underlying `tokio-tungstenite` connection answers protocol-level pings
/// automatically.
pub fn connect(topics: Vec<String>) -> impl Stream<Item = ManifoldWsEvent> {
    connect_to(DEFAULT_WS_URL, topics)
}

fn connect_to(url: &str, topics: Vec<String>) -> impl Stream<Item = ManifoldWsEvent> {
    let url = url.to_string();
    async_stream::stream! {
        let Ok((ws_stream, _)) = tokio_tungstenite::connect_async(&url).await else {
            return;
        };
        let (mut write, mut read) = ws_stream.split();

        let subscribe = serde_json::json!({
            "type": "subscribe",
            "txid": 1,
            "topics": topics,
        });
        if write.send(Message::Text(subscribe.to_string().into())).await.is_err() {
            return;
        }

        while let Some(msg) = read.next().await {
            let Ok(Message::Text(text)) = msg else {
                match msg {
                    Ok(_) => continue,
                    Err(_) => break,
                }
            };
            if let Ok(raw) = serde_json::from_str::<RawWsMessage>(&text) {
                yield ManifoldWsEvent::from(raw);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::net::TcpListener;

    /// Starts a one-shot local WS server that accepts a single connection, drains the client's
    /// subscribe message, sends each of `responses` in order, then closes.
    async fn start_mock_server(responses: Vec<String>) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
            let _ = ws.next().await; // drain the subscribe request
            for resp in responses {
                ws.send(Message::Text(resp.into())).await.unwrap();
            }
            let _ = ws.close(None).await;
        });
        format!("ws://{addr}")
    }

    #[tokio::test]
    async fn connect_yields_ack_then_new_bets_in_order() {
        let ack = r#"{"type":"ack","txid":1,"success":true}"#.to_string();
        let broadcast = serde_json::json!({
            "type": "broadcast",
            "topic": "global/new-bet",
            "data": {
                "bets": [{
                    "id": "bet1",
                    "contractId": "abc123",
                    "createdTime": 1788230563750i64,
                    "probBefore": 0.9,
                    "probAfter": 0.87,
                    "amount": -621.5,
                    "shares": -700.4,
                    "isFilled": true,
                    "isCancelled": false
                }]
            }
        })
        .to_string();

        let url = start_mock_server(vec![ack, broadcast]).await;
        let stream = connect_to(&url, vec!["global/new-bet".to_string()]);
        tokio::pin!(stream);

        let first = stream.next().await.unwrap();
        assert!(matches!(
            first,
            ManifoldWsEvent::Ack {
                txid: 1,
                success: true
            }
        ));

        let second = stream.next().await.unwrap();
        match second {
            ManifoldWsEvent::NewBets { topic, bets } => {
                assert_eq!(topic, "global/new-bet");
                assert_eq!(bets.len(), 1);
                assert_eq!(bets[0].contract_id, "abc123");
                assert_eq!(bets[0].prob_after, 0.87);
            }
            other => panic!("expected NewBets, got {other:?}"),
        }

        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn connect_skips_unparseable_messages() {
        let garbage = "not json".to_string();
        let ack = r#"{"type":"ack","txid":2,"success":true}"#.to_string();
        let url = start_mock_server(vec![garbage, ack]).await;
        let stream = connect_to(&url, vec!["global/new-bet".to_string()]);
        tokio::pin!(stream);

        let event = stream.next().await.unwrap();
        assert!(matches!(event, ManifoldWsEvent::Ack { txid: 2, .. }));
        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn connect_ends_stream_when_server_closes_immediately() {
        let url = start_mock_server(vec![]).await;
        let stream = connect_to(&url, vec!["global/new-bet".to_string()]);
        tokio::pin!(stream);

        assert!(stream.next().await.is_none());
    }
}
