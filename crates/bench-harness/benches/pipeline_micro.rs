//! Criterion micro-benchmarks for the pipeline's hot inner operations (Task 5.4).
//!
//! These complement the end-to-end load test (`run_load_test`): the load test measures whole-
//! pipeline latency including channel and storage, while these isolate the pure compute of
//! `MarketState::apply` and the feature calculations. Run with `cargo bench -p bench-harness`.

use common::{BetEvent, BetSample, MarketState};
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use feature_engine::{bet_arrival_rate, compute_snapshot, prob_velocity, realized_volatility};
use probability_engine::MarketTracker;

/// Deterministic synthetic bet events: a bounded probability walk, timestamps 1ms apart.
fn make_events(n: usize) -> Vec<BetEvent> {
    let mut events = Vec::with_capacity(n);
    let mut prob = 0.5;
    for i in 0..n {
        let prev = prob;
        // Deterministic, dependency-free wiggle in roughly [-0.02, 0.02].
        let step = (i as f64 * 0.123).sin() * 0.02;
        prob = (prob + step).clamp(0.01, 0.99);
        events.push(BetEvent {
            market_id: "m".to_string(),
            ts_ns: 1_700_000_000_000_000_000 + i as u64 * 1_000_000,
            prob_before: prev,
            prob_after: prob,
            amount: 10.0,
            shares: 20.0,
            is_limit_order: false,
        });
    }
    events
}

fn bench_market_state_apply(c: &mut Criterion) {
    let events = make_events(4);
    let event = &events[1];
    let mut state = MarketState::new("m");
    c.bench_function("MarketState::apply", |b| {
        b.iter(|| {
            state.apply(black_box(event));
            black_box(&state);
        });
    });
}

fn bench_feature_calcs(c: &mut Criterion) {
    // 512 = the collector's default per-market history capacity.
    let events = make_events(512);
    // The feature fns operate on the ring buffer's `BetSample`s (Task 6.2).
    let samples: Vec<BetSample> = events.iter().map(BetSample::from).collect();
    let window_ns = 60_000_000_000u64;

    c.bench_function("prob_velocity/512", |b| {
        b.iter(|| black_box(prob_velocity(black_box(&samples), black_box(window_ns))));
    });
    c.bench_function("bet_arrival_rate/512", |b| {
        b.iter(|| black_box(bet_arrival_rate(black_box(&samples), black_box(window_ns))));
    });
    c.bench_function("realized_volatility/512", |b| {
        b.iter(|| black_box(realized_volatility(black_box(&samples), black_box(window_ns))));
    });

    let mut tracker = MarketTracker::new("m", 512);
    for e in &events {
        tracker.apply(e);
    }
    c.bench_function("compute_snapshot/512", |b| {
        b.iter(|| black_box(compute_snapshot(black_box(&tracker), black_box(window_ns))));
    });
}

criterion_group!(benches, bench_market_state_apply, bench_feature_calcs);
criterion_main!(benches);
