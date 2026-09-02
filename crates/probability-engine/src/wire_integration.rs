//! Task 2.7 — wire the probability engine to the Manifold WS event stream.
//!
//! Replays a captured WS session (`fixtures/ws_session.jsonl`, one JSON frame per line) through
//! the full offline path: parse each frame with `manifold_client::parse_ws_text`, convert each
//! bet in a `NewBets` broadcast into a `common::BetEvent`, and drive a `ProbabilityEngine`.
//! Asserts the final per-market state matches hand-computed expected values.
//!
//! The live async consumption loop (subscribe → stream → apply, running continuously) belongs to
//! the `collector` binary in Phase 4, per `implementation.md` §3; this test exercises the same
//! parse → convert → apply logic deterministically without a network connection.

use crate::ProbabilityEngine;
use common::BetEvent;
use manifold_client::{parse_ws_text, ManifoldWsEvent};

const SESSION: &str = include_str!("../fixtures/ws_session.jsonl");

#[test]
fn replaying_captured_ws_session_produces_expected_state() {
    let mut engine = ProbabilityEngine::new(64);

    for line in SESSION.lines().filter(|l| !l.trim().is_empty()) {
        let event = parse_ws_text(line).expect("every fixture frame should parse");
        // Acks carry no bets and must not affect market state; only NewBets drive the engine.
        if let ManifoldWsEvent::NewBets { bets, .. } = event {
            for bet in &bets {
                let domain: BetEvent = bet.into();
                engine.apply(&domain);
            }
        }
    }

    // Two distinct markets appeared across the session.
    assert_eq!(engine.market_count(), 2);

    // m1 saw b1 (0.60), b2 (0.55), b4 (0.72); final state is the last bet, ts in ns.
    let m1 = engine.market("m1").expect("m1 should be tracked");
    assert_eq!(m1.state().current_prob, 0.72);
    assert_eq!(m1.state().last_updated_ns, 3_000 * 1_000_000);
    assert_eq!(m1.history().len(), 3);

    // m2 saw only b3 (0.20).
    let m2 = engine.market("m2").expect("m2 should be tracked");
    assert_eq!(m2.state().current_prob, 0.2);
    assert_eq!(m2.state().last_updated_ns, 2_000 * 1_000_000);
    assert_eq!(m2.history().len(), 1);
}
