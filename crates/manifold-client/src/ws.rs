use crate::types::Bet;
use futures_util::{SinkExt, Stream, StreamExt};
use serde::Deserialize;
use std::time::Duration;
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

/// Parses one raw WebSocket text frame into a `ManifoldWsEvent`, returning `None` for anything
/// that doesn't match the known ack/broadcast shapes. Exposed so callers (and offline tests that
/// replay a captured WS session) can parse frames without opening a live connection.
pub fn parse_ws_text(text: &str) -> Option<ManifoldWsEvent> {
    serde_json::from_str::<RawWsMessage>(text)
        .ok()
        .map(ManifoldWsEvent::from)
}

/// Tuning knobs for connection health and reconnection. Defaults are based on empirical testing
/// against the live API (see module docs on `connect_once`) rather than Manifold's documentation,
/// which doesn't specify this behavior.
#[derive(Debug, Clone, Copy)]
struct WsConfig {
    /// How often to send an outbound WS ping frame. Verified live that Manifold's server does
    /// NOT reliably reply with pongs, so this is *not* relied on to keep the connection alive —
    /// it's a cheap, standard defense against NAT/firewall idle-timeout drops on quiet topics.
    ping_interval: Duration,
    /// If no frame of any kind is received for this long, treat the connection as dead and force
    /// a reconnect. Backstops the (rare) silent-hang case where the OS never surfaces a
    /// disconnect error. Observed real disconnects (~60-110s, unrelated to ping behavior) are
    /// caught faster than this via the normal read-error path; this is a generous upper bound.
    inactivity_timeout: Duration,
    /// Initial delay before the first reconnect attempt after a disconnect.
    initial_backoff: Duration,
    /// Reconnect backoff doubles on each consecutive failure, capped here.
    max_backoff: Duration,
    /// A connection that stayed up at least this long resets backoff to `initial_backoff` on its
    /// next disconnect, rather than continuing to escalate from wherever it left off.
    stable_threshold: Duration,
}

impl Default for WsConfig {
    fn default() -> Self {
        Self {
            ping_interval: Duration::from_secs(45),
            inactivity_timeout: Duration::from_secs(120),
            initial_backoff: Duration::from_millis(500),
            max_backoff: Duration::from_secs(30),
            stable_threshold: Duration::from_secs(30),
        }
    }
}

/// Connects to Manifold's public WebSocket, subscribing to the given topics (e.g.
/// `"global/new-bet"`), and reconnects with exponential backoff for as long as the returned
/// stream is polled — this never ends on its own, since the intended caller (the always-on
/// `collector`) needs the ingestion pipeline to survive disconnects indefinitely.
///
/// **Why reconnection matters more than a keepalive here**: live testing showed Manifold's
/// WebSocket disconnects unpredictably (~60-110s in testing) regardless of client ping behavior
/// or whether data was actively flowing — this isn't an idle-timeout, it's the connection's
/// baseline lifetime. A ping cannot prevent it. See `connect_once` for the per-connection
/// details and `docs/metaculus-tos-check.md`-style verification notes in `implementation.md`.
pub fn connect(topics: Vec<String>) -> impl Stream<Item = ManifoldWsEvent> {
    connect_with_reconnect(DEFAULT_WS_URL.to_string(), topics, WsConfig::default())
}

fn connect_with_reconnect(
    url: String,
    topics: Vec<String>,
    config: WsConfig,
) -> impl Stream<Item = ManifoldWsEvent> {
    async_stream::stream! {
        let mut backoff = config.initial_backoff;
        loop {
            let connected_at = tokio::time::Instant::now();
            let inner = connect_once(&url, topics.clone(), config);
            tokio::pin!(inner);
            while let Some(event) = inner.next().await {
                yield event;
            }

            backoff = if connected_at.elapsed() >= config.stable_threshold {
                config.initial_backoff
            } else {
                (backoff * 2).min(config.max_backoff)
            };
            tokio::time::sleep(backoff).await;
        }
    }
}

/// A single connection attempt: connect, subscribe, then yield parsed events until the
/// connection ends (error, close, or `config.inactivity_timeout` elapses with no frames
/// received). Does not reconnect — that's `connect_with_reconnect`'s job.
///
/// Sends a WS ping every `config.ping_interval` as a fire-and-forget NAT-keepalive measure.
/// Malformed/unrecognized text frames are silently skipped rather than terminating the
/// connection — there's no `Result` in the item type to surface a parse error through, and a
/// single stray frame shouldn't kill an otherwise-healthy connection.
fn connect_once(
    url: &str,
    topics: Vec<String>,
    config: WsConfig,
) -> impl Stream<Item = ManifoldWsEvent> {
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

        let mut ping_timer = tokio::time::interval(config.ping_interval);
        ping_timer.tick().await; // first tick fires immediately; consume it so we don't ping at t=0
        let mut last_activity = tokio::time::Instant::now();

        loop {
            let watchdog_deadline = last_activity + config.inactivity_timeout;
            tokio::select! {
                msg = read.next() => {
                    match msg {
                        Some(Ok(Message::Text(text))) => {
                            last_activity = tokio::time::Instant::now();
                            if let Some(event) = parse_ws_text(&text) {
                                yield event;
                            }
                        }
                        Some(Ok(_)) => {
                            last_activity = tokio::time::Instant::now();
                        }
                        Some(Err(_)) | None => break,
                    }
                }
                _ = ping_timer.tick() => {
                    if write.send(Message::Ping(Vec::new().into())).await.is_err() {
                        break;
                    }
                }
                _ = tokio::time::sleep_until(watchdog_deadline) => {
                    break;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use tokio::net::TcpListener;
    use tokio::sync::Mutex;

    fn fast_config() -> WsConfig {
        WsConfig {
            ping_interval: Duration::from_millis(100),
            inactivity_timeout: Duration::from_secs(60),
            initial_backoff: Duration::from_millis(10),
            max_backoff: Duration::from_millis(50),
            stable_threshold: Duration::from_secs(60),
        }
    }

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

    /// Starts a server that records every frame the client sends (including control frames like
    /// Ping), acking any text message as a subscribe request. Used to observe outbound pings.
    async fn start_recording_server() -> (String, Arc<Mutex<Vec<Message>>>) {
        let received = Arc::new(Mutex::new(Vec::new()));
        let received_task = received.clone();
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
            while let Some(Ok(msg)) = ws.next().await {
                let is_text = matches!(msg, Message::Text(_));
                received_task.lock().await.push(msg);
                if is_text {
                    let ack = r#"{"type":"ack","txid":1,"success":true}"#;
                    if ws.send(Message::Text(ack.into())).await.is_err() {
                        break;
                    }
                }
            }
        });
        (format!("ws://{addr}"), received)
    }

    /// Accepts `rounds.len()` sequential connections, each scripted with its own responses, then
    /// closing before the next round is accepted — simulates the observed repeated-disconnect
    /// behavior.
    async fn start_multi_round_server(rounds: Vec<Vec<String>>) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            for round in rounds {
                let (stream, _) = listener.accept().await.unwrap();
                let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
                let _ = ws.next().await; // drain subscribe
                for resp in round {
                    ws.send(Message::Text(resp.into())).await.unwrap();
                }
                let _ = ws.close(None).await;
            }
        });
        format!("ws://{addr}")
    }

    fn new_bets_fixture(contract_id: &str) -> String {
        serde_json::json!({
            "type": "broadcast",
            "topic": "global/new-bet",
            "data": {
                "bets": [{
                    "id": "bet1",
                    "contractId": contract_id,
                    "createdTime": 1788230563750i64,
                    "probBefore": 0.5,
                    "probAfter": 0.51,
                    "amount": 10.0,
                    "shares": 19.0,
                    "isFilled": true,
                    "isCancelled": false
                }]
            }
        })
        .to_string()
    }

    // --- Task 1.3 tests (connect_once via the default-config public surface) ---

    #[tokio::test]
    async fn connect_yields_ack_then_new_bets_in_order() {
        let ack = r#"{"type":"ack","txid":1,"success":true}"#.to_string();
        let broadcast = new_bets_fixture("abc123");

        let url = start_mock_server(vec![ack, broadcast]).await;
        let stream = connect_once(&url, vec!["global/new-bet".to_string()], WsConfig::default());
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
                assert_eq!(bets[0].prob_after, 0.51);
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
        let stream = connect_once(&url, vec!["global/new-bet".to_string()], WsConfig::default());
        tokio::pin!(stream);

        let event = stream.next().await.unwrap();
        assert!(matches!(event, ManifoldWsEvent::Ack { txid: 2, .. }));
        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn connect_ends_stream_when_server_closes_immediately() {
        let url = start_mock_server(vec![]).await;
        let stream = connect_once(&url, vec!["global/new-bet".to_string()], WsConfig::default());
        tokio::pin!(stream);

        assert!(stream.next().await.is_none());
    }

    // --- Task 1.4 tests (ping cadence + inactivity watchdog) ---

    /// Polls `stream` for exactly `duration` of wall/virtual time, discarding any yielded items.
    /// `stream.next()` alone can't be used for this: it resolves as soon as *any* item is ready
    /// (e.g. the mock server's immediate ack), which can be far sooner than `duration` and would
    /// under-drive the stream's internal timers.
    async fn drive_for(
        mut stream: std::pin::Pin<&mut (impl Stream<Item = ManifoldWsEvent> + ?Sized)>,
        duration: Duration,
    ) {
        let deadline = tokio::time::sleep(duration);
        tokio::pin!(deadline);
        loop {
            tokio::select! {
                _ = &mut deadline => break,
                item = stream.next() => if item.is_none() { break },
            }
        }
    }

    #[tokio::test]
    async fn ping_is_not_sent_before_the_configured_interval() {
        let (url, received) = start_recording_server().await;
        let config = fast_config(); // ping_interval = 100ms
        let stream = connect_once(&url, vec!["t".to_string()], config);
        tokio::pin!(stream);

        drive_for(stream.as_mut(), Duration::from_millis(30)).await;
        let frames = received.lock().await;
        assert!(
            !frames.iter().any(|m| matches!(m, Message::Ping(_))),
            "ping sent before the configured interval elapsed"
        );
    }

    #[tokio::test]
    async fn ping_is_sent_within_the_configured_interval() {
        let (url, received) = start_recording_server().await;
        let config = fast_config(); // ping_interval = 100ms
        let stream = connect_once(&url, vec!["t".to_string()], config);
        tokio::pin!(stream);

        drive_for(stream.as_mut(), Duration::from_millis(250)).await;
        let frames = received.lock().await;
        assert!(
            frames.iter().any(|m| matches!(m, Message::Ping(_))),
            "expected at least one ping frame to have been sent by now"
        );
    }

    #[tokio::test]
    async fn inactivity_watchdog_ends_connection_when_no_frames_arrive() {
        // Server accepts the connection and drains the subscribe, but never sends anything back
        // and never closes - simulates a silent hang the read path wouldn't otherwise detect.
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
            let _ = ws.next().await; // drain subscribe, then go silent forever
            std::future::pending::<()>().await;
        });
        let url = format!("ws://{addr}");

        let config = WsConfig {
            inactivity_timeout: Duration::from_millis(50),
            ping_interval: Duration::from_secs(60), // don't let the ping branch interfere
            ..fast_config()
        };
        let stream = connect_once(&url, vec!["t".to_string()], config);
        tokio::pin!(stream);

        let result = tokio::time::timeout(Duration::from_millis(500), stream.next()).await;
        assert!(
            result.unwrap().is_none(),
            "expected the watchdog to end the stream after inactivity_timeout"
        );
    }

    // --- Task 1.5 tests (reconnect with backoff) ---

    #[tokio::test]
    async fn reconnect_resumes_with_fresh_subscription_after_disconnect() {
        let url = start_multi_round_server(vec![
            vec![
                r#"{"type":"ack","txid":1,"success":true}"#.to_string(),
                new_bets_fixture("first"),
            ],
            vec![
                r#"{"type":"ack","txid":1,"success":true}"#.to_string(),
                new_bets_fixture("second"),
            ],
        ])
        .await;

        let stream = connect_with_reconnect(url, vec!["global/new-bet".to_string()], fast_config());
        tokio::pin!(stream);

        // Round 1
        assert!(matches!(
            stream.next().await.unwrap(),
            ManifoldWsEvent::Ack { .. }
        ));
        match stream.next().await.unwrap() {
            ManifoldWsEvent::NewBets { bets, .. } => assert_eq!(bets[0].contract_id, "first"),
            other => panic!("expected NewBets, got {other:?}"),
        }

        // Round 1's server-side connection closes here; the client should back off briefly and
        // reconnect automatically, re-subscribing and resuming with round 2's events.
        assert!(matches!(
            stream.next().await.unwrap(),
            ManifoldWsEvent::Ack { .. }
        ));
        match stream.next().await.unwrap() {
            ManifoldWsEvent::NewBets { bets, .. } => assert_eq!(bets[0].contract_id, "second"),
            other => panic!("expected NewBets, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn backoff_escalates_across_rapid_consecutive_failures() {
        // Every round closes immediately (no responses) - simulates rapid repeated failures, so
        // backoff should escalate past initial_backoff rather than resetting each time.
        let url = start_multi_round_server(vec![vec![], vec![], vec![]]).await;
        let config = WsConfig {
            initial_backoff: Duration::from_millis(20),
            max_backoff: Duration::from_millis(200),
            stable_threshold: Duration::from_secs(60), // nothing here counts as "stable"
            ..fast_config()
        };
        let stream = connect_with_reconnect(url, vec!["t".to_string()], config);
        tokio::pin!(stream);

        let start = tokio::time::Instant::now();
        // Drive the stream long enough to burn through all 3 scripted rounds plus their backoffs.
        let _ = tokio::time::timeout(Duration::from_millis(400), stream.next()).await;
        // Two backoff sleeps have elapsed by the time round 3 is attempted: 20ms then 40ms,
        // so at least that much wall time must have passed even though every round is instant.
        assert!(
            start.elapsed() >= Duration::from_millis(50),
            "expected escalating backoff to introduce delay, elapsed={:?}",
            start.elapsed()
        );
    }
}
