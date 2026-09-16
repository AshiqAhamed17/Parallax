//! Synthetic load generation for the latency benchmark harness (Phase 5).
//!
//! [`SyntheticGenerator`] produces WS-shaped events — `ManifoldWsEvent::NewBets`, each carrying a
//! single synthetic `Bet` — that are byte-compatible with what the real Manifold WebSocket feeds
//! the collector pipeline. [`synthetic_stream`] wraps a generator in a rate-paced async `Stream`
//! so Task 5.3 can drive the real `run_ingest_loop`/`run_writer_loop` with instrumentation on and
//! measure per-stage latency under a controlled, reproducible load.
//!
//! Generation is fully deterministic given a seed (a tiny xorshift PRNG, no `rand` dependency), so
//! benchmark runs are reproducible. Pacing uses absolute deadlines (`start + i/rate`) rather than
//! per-event sleeps: intermediate timer over-sleep is absorbed by later events firing immediately
//! to catch up, so the *measured throughput over a run* converges to the requested rate even
//! though the OS timer granularity (~1ms) is coarser than the inter-event spacing at high rates.

use futures_util::Stream;
use manifold_client::{Bet, ManifoldWsEvent};
use std::time::Duration;

/// A deterministic, dependency-free PRNG (xorshift64*). Adequate for synthetic load — we need
/// reproducible pseudo-randomness, not cryptographic quality.
struct Xorshift64 {
    state: u64,
}

impl Xorshift64 {
    fn new(seed: u64) -> Self {
        // A zero state would make xorshift emit only zeros; nudge it off zero.
        Self { state: seed.max(1) }
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }

    /// A pseudo-random `f64` in `[0.0, 1.0)`.
    fn next_f64(&mut self) -> f64 {
        // Top 53 bits give a uniformly-distributed double in [0, 1).
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// Configuration for a synthetic load run.
#[derive(Debug, Clone)]
pub struct SyntheticConfig {
    /// Target events (== bets) per second. `<= 0` or non-finite means "as fast as possible".
    pub rate_per_sec: f64,
    /// Number of distinct markets bets are spread across (round-robin).
    pub num_markets: usize,
    /// PRNG seed — same seed yields the same event sequence.
    pub seed: u64,
}

impl Default for SyntheticConfig {
    fn default() -> Self {
        Self { rate_per_sec: 1000.0, num_markets: 16, seed: 42 }
    }
}

/// A fixed synthetic epoch (ms) so generated `created_time`s are deterministic and don't depend on
/// the wall clock. Values only need to be internally consistent and monotonically increasing.
const BASE_TIME_MS: i64 = 1_700_000_000_000;

/// Generates an endless sequence of WS-shaped synthetic events. Each call to [`next_event`]
/// advances a per-market probability random walk and emits one bet.
///
/// [`next_event`]: SyntheticGenerator::next_event
pub struct SyntheticGenerator {
    rng: Xorshift64,
    num_markets: usize,
    /// Current probability for each market, evolved as a bounded random walk.
    probs: Vec<f64>,
    /// Monotonic event counter, doubling as the per-event id and timestamp offset.
    seq: u64,
}

impl SyntheticGenerator {
    pub fn new(config: &SyntheticConfig) -> Self {
        let num_markets = config.num_markets.max(1);
        Self {
            rng: Xorshift64::new(config.seed),
            num_markets,
            probs: vec![0.5; num_markets],
            seq: 0,
        }
    }

    /// Produce the next synthetic `ManifoldWsEvent::NewBets` (one bet).
    ///
    /// The probability follows a bounded random walk in `[0.01, 0.99]`; `created_time` increases by
    /// 1ms per event so timestamps are strictly monotonic globally (and therefore per market too,
    /// which the pipeline's chronological-order assumption relies on).
    pub fn next_event(&mut self) -> ManifoldWsEvent {
        let idx = (self.seq as usize) % self.num_markets;
        let prob_before = self.probs[idx];
        let step = (self.rng.next_f64() - 0.5) * 0.1; // +/- 0.05
        let prob_after = (prob_before + step).clamp(0.01, 0.99);
        self.probs[idx] = prob_after;

        let amount = 10.0 + self.rng.next_f64() * 90.0;
        let shares = amount / prob_after; // prob_after >= 0.01, never divides by ~0

        let bet = Bet {
            id: format!("synthetic-{}", self.seq),
            contract_id: format!("synthetic-market-{idx}"),
            created_time: BASE_TIME_MS + self.seq as i64,
            prob_before,
            prob_after,
            amount,
            shares,
            is_filled: Some(true),
            is_cancelled: Some(false),
            limit_prob: None,
        };
        self.seq += 1;

        ManifoldWsEvent::NewBets { topic: "global/new-bet".to_string(), bets: vec![bet] }
    }
}

/// A rate-paced stream of `count` synthetic events.
///
/// Event `i` is released no earlier than `start + i / rate_per_sec`. Because the deadlines are
/// absolute, an over-sleep on one tick doesn't push every later event back — later events fire
/// immediately until the schedule is caught up — so throughput measured across the whole run
/// tracks the requested rate. With `rate_per_sec <= 0` or non-finite, events are produced with no
/// pacing (as fast as the consumer drains them).
pub fn synthetic_stream(config: SyntheticConfig, count: usize) -> impl Stream<Item = ManifoldWsEvent> {
    async_stream::stream! {
        let mut generator = SyntheticGenerator::new(&config);
        let paced = config.rate_per_sec.is_finite() && config.rate_per_sec > 0.0;
        let start = tokio::time::Instant::now();

        for i in 0..count {
            if paced {
                let deadline = start + Duration::from_secs_f64(i as f64 / config.rate_per_sec);
                tokio::time::sleep_until(deadline).await;
            }
            yield generator.next_event();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures_util::StreamExt;

    fn bets_of(event: &ManifoldWsEvent) -> &[Bet] {
        match event {
            ManifoldWsEvent::NewBets { bets, .. } => bets,
            ManifoldWsEvent::Ack { .. } => panic!("generator should never emit Ack"),
        }
    }

    #[test]
    fn generator_emits_valid_bets_with_monotonic_timestamps() {
        let mut generator = SyntheticGenerator::new(&SyntheticConfig::default());
        let mut last_ts = i64::MIN;
        for _ in 0..200 {
            let event = generator.next_event();
            let bets = bets_of(&event);
            assert_eq!(bets.len(), 1);
            let bet = &bets[0];
            assert!(bet.prob_before > 0.0 && bet.prob_before < 1.0);
            assert!(bet.prob_after >= 0.01 && bet.prob_after <= 0.99);
            assert!(bet.amount >= 10.0 && bet.amount <= 100.0);
            assert!(bet.created_time > last_ts, "created_time must strictly increase");
            assert!(bet.contract_id.starts_with("synthetic-market-"));
            last_ts = bet.created_time;
        }
    }

    #[test]
    fn generator_spreads_across_all_markets() {
        let mut generator = SyntheticGenerator::new(&SyntheticConfig {
            num_markets: 4,
            ..SyntheticConfig::default()
        });
        let mut seen = std::collections::HashSet::new();
        for _ in 0..16 {
            let event = generator.next_event();
            seen.insert(bets_of(&event)[0].contract_id.clone());
        }
        assert_eq!(seen.len(), 4, "all four markets should appear");
    }

    #[test]
    fn same_seed_produces_identical_sequences() {
        let config = SyntheticConfig { seed: 7, ..SyntheticConfig::default() };
        let mut a = SyntheticGenerator::new(&config);
        let mut b = SyntheticGenerator::new(&config);
        for _ in 0..50 {
            let ea = bets_of(&a.next_event())[0].clone();
            let eb = bets_of(&b.next_event())[0].clone();
            assert_eq!(ea.id, eb.id);
            assert_eq!(ea.contract_id, eb.contract_id);
            assert_eq!(ea.prob_after, eb.prob_after);
            assert_eq!(ea.amount, eb.amount);
        }
    }

    #[tokio::test]
    async fn measured_throughput_is_within_5_percent_of_requested() {
        let rate = 2000.0;
        let count = 1000; // ~0.5s run — long enough that timer jitter averages well under 5%
        let config = SyntheticConfig { rate_per_sec: rate, num_markets: 8, seed: 42 };

        let start = std::time::Instant::now();
        let mut stream = Box::pin(synthetic_stream(config, count));
        let mut n = 0usize;
        while stream.next().await.is_some() {
            n += 1;
        }
        let elapsed = start.elapsed().as_secs_f64();

        assert_eq!(n, count);
        let measured = n as f64 / elapsed;
        let rel_err = (measured - rate).abs() / rate;
        assert!(
            rel_err <= 0.05,
            "measured {measured:.1}/s vs requested {rate:.1}/s (error {:.2}%)",
            rel_err * 100.0
        );
    }

    #[tokio::test]
    async fn unpaced_stream_still_yields_every_event() {
        let config = SyntheticConfig { rate_per_sec: 0.0, ..SyntheticConfig::default() };
        let stream = synthetic_stream(config, 500);
        let events: Vec<_> = Box::pin(stream).collect().await;
        assert_eq!(events.len(), 500);
    }
}
