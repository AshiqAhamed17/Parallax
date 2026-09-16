//! Per-stage latency instrumentation for the ingestion pipeline (Phase 5).
//!
//! One [`StageTimer`] travels alongside each bet as it crosses the pipeline. The pipeline calls
//! [`StageTimer::mark`] as the event reaches each stage boundary:
//! WS-receive → state-update → feature-calc → storage-write.
//!
//! In production the timer is [`StageTimer::Disabled`]: `mark` reads no clock and stores nothing,
//! so the instrumentation is genuinely zero-cost (a single branch the optimizer can fold away).
//! The latency benchmark harness constructs [`StageTimer::Enabled`] timers to capture the real
//! per-stage [`quanta::Instant`]s, then reads back segment durations and percentiles from them.
//!
//! This lives in `common` rather than `bench-harness` on purpose: the four stages it times all
//! live in the `collector` pipeline, so `collector` has to carry the timer, but `bench-harness`
//! depends on `collector` (it drives the pipeline with synthetic load), so `collector` cannot
//! depend on `bench-harness` without a cycle. `common` is the shared crate both already use.

use quanta::Instant;
use std::time::Duration;

/// The pipeline stages we time, in causal (chronological) order.
///
/// The discriminant doubles as the index into a [`StageTimer`]'s backing array, and the ordering
/// defines what "monotonic" means when validating a captured set of timestamps.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(usize)]
pub enum Stage {
    /// A bet event was received off the Manifold WebSocket (pipeline entry).
    WsReceive = 0,
    /// The probability engine finished applying the bet to its market state.
    StateUpdate = 1,
    /// The feature engine finished computing the snapshot for the bet.
    FeatureCalc = 2,
    /// The row(s) for the bet finished being written to storage (pipeline exit).
    StorageWrite = 3,
}

impl Stage {
    /// Every stage, in causal order.
    pub const ALL: [Stage; 4] = [
        Stage::WsReceive,
        Stage::StateUpdate,
        Stage::FeatureCalc,
        Stage::StorageWrite,
    ];

    /// Number of stages (the backing-array length).
    pub const COUNT: usize = 4;

    /// This stage's index into the backing array.
    #[inline]
    pub const fn index(self) -> usize {
        self as usize
    }
}

/// A per-event latency timer.
///
/// `Disabled` (the production default) captures nothing and touches no clock. `Enabled` records
/// the [`quanta::Instant`] at which each stage is first marked (first-write-wins, so a defensive
/// re-mark can't overwrite the true causal timestamp).
#[derive(Debug, Clone)]
pub enum StageTimer {
    Disabled,
    Enabled([Option<Instant>; Stage::COUNT]),
}

impl StageTimer {
    /// A disabled timer — the zero-cost production default.
    #[inline]
    pub fn disabled() -> Self {
        StageTimer::Disabled
    }

    /// An enabled timer with no stages marked yet.
    #[inline]
    pub fn enabled() -> Self {
        StageTimer::Enabled([None; Stage::COUNT])
    }

    /// An enabled timer whose [`Stage::WsReceive`] is pre-set to `ws_receive`.
    ///
    /// One Manifold broadcast can carry several bets; they share a single WS-receive instant but
    /// each gets its own timer for the later per-bet stages. This lets the caller read the clock
    /// once per broadcast and stamp every bet's timer with the same entry timestamp.
    #[inline]
    pub fn enabled_from(ws_receive: Instant) -> Self {
        let mut slots = [None; Stage::COUNT];
        slots[Stage::WsReceive.index()] = Some(ws_receive);
        StageTimer::Enabled(slots)
    }

    /// Whether this timer is capturing timestamps.
    #[inline]
    pub fn is_enabled(&self) -> bool {
        matches!(self, StageTimer::Enabled(_))
    }

    /// Records the current instant for `stage`. No-op — and, crucially, no clock read — when
    /// disabled. When enabled, records the first mark for a stage and ignores later marks for that
    /// same stage.
    #[inline]
    pub fn mark(&mut self, stage: Stage) {
        if let StageTimer::Enabled(slots) = self {
            let slot = &mut slots[stage.index()];
            if slot.is_none() {
                *slot = Some(Instant::now());
            }
        }
    }

    /// Records an explicit `instant` for `stage` (same first-write-wins semantics as [`mark`]).
    ///
    /// Used for the shared WS-receive instant across the bets in one broadcast.
    ///
    /// [`mark`]: StageTimer::mark
    #[inline]
    pub fn mark_at(&mut self, stage: Stage, instant: Instant) {
        if let StageTimer::Enabled(slots) = self {
            let slot = &mut slots[stage.index()];
            if slot.is_none() {
                *slot = Some(instant);
            }
        }
    }

    /// The captured instant for `stage`, if enabled and marked.
    #[inline]
    pub fn get(&self, stage: Stage) -> Option<Instant> {
        match self {
            StageTimer::Disabled => None,
            StageTimer::Enabled(slots) => slots[stage.index()],
        }
    }

    /// All four stage instants in causal order, but only if every stage was marked. Returns `None`
    /// if disabled or any stage is missing.
    pub fn timeline(&self) -> Option<[Instant; Stage::COUNT]> {
        let StageTimer::Enabled(slots) = self else {
            return None;
        };
        Some([slots[0]?, slots[1]?, slots[2]?, slots[3]?])
    }

    /// Whether every marked stage's timestamp is at or after the previous marked stage's — i.e.
    /// the captured timestamps respect causal order. Vacuously true if fewer than two stages are
    /// marked (including when disabled).
    pub fn is_monotonic(&self) -> bool {
        let StageTimer::Enabled(slots) = self else {
            return true;
        };
        let mut prev: Option<Instant> = None;
        for slot in slots.iter().flatten() {
            if let Some(p) = prev
                && *slot < p
            {
                return false;
            }
            prev = Some(*slot);
        }
        true
    }

    /// Elapsed time from stage `from` to stage `to`, if both were marked and `to` is at or after
    /// `from`. Returns `None` if disabled, either stage is unmarked, or `to` precedes `from`.
    pub fn duration_between(&self, from: Stage, to: Stage) -> Option<Duration> {
        let start = self.get(from)?;
        let end = self.get(to)?;
        (end >= start).then(|| end.duration_since(start))
    }

    /// Total pipeline latency: WS-receive to storage-write.
    pub fn total(&self) -> Option<Duration> {
        self.duration_between(Stage::WsReceive, Stage::StorageWrite)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_timer_captures_nothing() {
        let mut timer = StageTimer::disabled();
        timer.mark(Stage::WsReceive);
        timer.mark(Stage::StorageWrite);
        assert!(!timer.is_enabled());
        assert_eq!(timer.get(Stage::WsReceive), None);
        assert_eq!(timer.timeline(), None);
        assert_eq!(timer.total(), None);
        // A disabled timer is vacuously monotonic.
        assert!(timer.is_monotonic());
    }

    #[test]
    fn enabled_timer_marks_all_stages_monotonically() {
        let mut timer = StageTimer::enabled();
        for stage in Stage::ALL {
            timer.mark(stage);
            // A hair of real work so consecutive clock reads don't collapse to the same tick.
            std::hint::black_box(&timer);
        }
        assert!(timer.is_enabled());
        let timeline = timer.timeline().expect("all four stages marked");
        for pair in timeline.windows(2) {
            assert!(pair[1] >= pair[0], "timestamps must be non-decreasing across stages");
        }
        assert!(timer.is_monotonic());
        assert!(timer.total().is_some());
    }

    #[test]
    fn first_mark_wins() {
        let mut timer = StageTimer::enabled();
        timer.mark(Stage::WsReceive);
        let first = timer.get(Stage::WsReceive).unwrap();
        timer.mark(Stage::WsReceive); // should be ignored
        assert_eq!(timer.get(Stage::WsReceive).unwrap(), first);
    }

    #[test]
    fn enabled_from_presets_ws_receive() {
        let now = Instant::now();
        let timer = StageTimer::enabled_from(now);
        assert_eq!(timer.get(Stage::WsReceive), Some(now));
        assert_eq!(timer.get(Stage::StateUpdate), None);
        assert_eq!(timer.timeline(), None); // not all stages marked yet
    }

    #[test]
    fn timeline_requires_every_stage() {
        let mut timer = StageTimer::enabled();
        timer.mark(Stage::WsReceive);
        timer.mark(Stage::StateUpdate);
        timer.mark(Stage::FeatureCalc);
        assert_eq!(timer.timeline(), None, "missing StorageWrite -> no timeline");
        timer.mark(Stage::StorageWrite);
        assert!(timer.timeline().is_some());
    }

    #[test]
    fn is_monotonic_detects_out_of_order_timestamps() {
        // Hand-build timestamps out of causal order using explicit instants.
        let base = Instant::now();
        let later = Instant::now(); // >= base
        let mut timer = StageTimer::enabled();
        timer.mark_at(Stage::WsReceive, later);
        timer.mark_at(Stage::StateUpdate, base); // earlier than WsReceive -> violates order
        // Only assert the violation if the two reads actually differ; otherwise the ordering is
        // ambiguous and the check is vacuous. On any real clock `later >= base`.
        if later > base {
            assert!(!timer.is_monotonic());
            assert_eq!(timer.duration_between(Stage::WsReceive, Stage::StateUpdate), None);
        }
    }

    #[test]
    fn duration_between_measures_forward_segments() {
        let mut timer = StageTimer::enabled();
        timer.mark(Stage::WsReceive);
        std::thread::sleep(Duration::from_micros(50));
        timer.mark(Stage::StorageWrite);
        let d = timer
            .duration_between(Stage::WsReceive, Stage::StorageWrite)
            .expect("both stages marked in order");
        assert!(d >= Duration::from_micros(1));
    }
}
