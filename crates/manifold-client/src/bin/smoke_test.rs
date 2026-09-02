//! Manual smoke test: connects to the real Manifold WebSocket, subscribes to `global/new-bet`,
//! and logs raw events to stdout for 30 seconds. Not run in CI — this hits the live network.
//!
//! Run with: `cargo run -p manifold-client --bin smoke_test`

use futures_util::StreamExt;
use manifold_client::{connect, ManifoldWsEvent};
use std::time::Duration;

#[tokio::main]
async fn main() {
    println!("connecting to Manifold WebSocket, subscribing to global/new-bet...");
    let stream = connect(vec!["global/new-bet".to_string()]);
    tokio::pin!(stream);

    let mut ack_count = 0u32;
    let mut bet_count = 0u32;
    let deadline = tokio::time::sleep(Duration::from_secs(30));
    tokio::pin!(deadline);

    loop {
        tokio::select! {
            _ = &mut deadline => break,
            event = stream.next() => {
                match event {
                    Some(ManifoldWsEvent::Ack { txid, success }) => {
                        ack_count += 1;
                        println!("[ack #{ack_count}] txid={txid} success={success}");
                    }
                    Some(ManifoldWsEvent::NewBets { topic, bets }) => {
                        bet_count += bets.len() as u32;
                        for bet in &bets {
                            println!(
                                "[bet] topic={topic} contract={} probBefore={:.4} probAfter={:.4}",
                                bet.contract_id, bet.prob_before, bet.prob_after
                            );
                        }
                    }
                    None => {
                        println!("stream ended unexpectedly");
                        break;
                    }
                }
            }
        }
    }

    println!("--- summary: {ack_count} connection(s) (acks), {bet_count} bet event(s) over 30s ---");
}
