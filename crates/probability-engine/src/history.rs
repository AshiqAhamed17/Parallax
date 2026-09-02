use common::BetEvent;

/// A fixed-capacity ring buffer of the most recent `BetEvent`s for a single market.
///
/// Backing storage is pre-allocated to `capacity` and never grows: once full, each push
/// overwrites the oldest entry in place (O(1), no allocation). This bounds memory per market
/// regardless of how long the collector runs — a market that sees millions of bets still holds
/// only `capacity` of them. The feature engine (Phase 3) reads the current window via `iter`,
/// which always yields oldest → newest.
#[derive(Debug, Clone)]
pub struct BetHistory {
    /// Grows to `capacity` as the buffer fills, then stays at `capacity` for the rest of its life.
    buf: Vec<BetEvent>,
    capacity: usize,
    /// Once full, the index of the oldest element (and the next slot to overwrite). While still
    /// filling this stays 0, since pushes append rather than overwrite.
    next: usize,
}

impl BetHistory {
    /// Creates an empty buffer that will retain at most `capacity` events.
    ///
    /// # Panics
    /// Panics if `capacity == 0` — a zero-capacity history is a programmer error (it could never
    /// hold a bet), so fail fast at construction rather than silently discarding every push.
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "BetHistory capacity must be greater than zero");
        Self {
            buf: Vec::with_capacity(capacity),
            capacity,
            next: 0,
        }
    }

    /// Appends `event`, evicting the oldest entry if the buffer is already at capacity. O(1).
    pub fn push(&mut self, event: BetEvent) {
        if self.buf.len() < self.capacity {
            self.buf.push(event);
        } else {
            self.buf[self.next] = event;
            self.next = (self.next + 1) % self.capacity;
        }
    }

    /// Number of events currently held (0..=capacity).
    pub fn len(&self) -> usize {
        self.buf.len()
    }

    pub fn is_empty(&self) -> bool {
        self.buf.is_empty()
    }

    /// The maximum number of events this buffer will retain.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Iterates the current window from oldest to newest.
    pub fn iter(&self) -> impl Iterator<Item = &BetEvent> + '_ {
        let cap = self.capacity;
        let next = self.next;
        let len = self.buf.len();
        (0..len).map(move |i| &self.buf[(next + i) % cap])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bet(ts_ns: u64) -> BetEvent {
        BetEvent {
            market_id: "m".to_string(),
            ts_ns,
            prob_before: 0.5,
            prob_after: 0.5,
            amount: 1.0,
            shares: 1.0,
            is_limit_order: false,
        }
    }

    /// Convenience: the timestamps currently in the buffer, oldest → newest.
    fn tss(h: &BetHistory) -> Vec<u64> {
        h.iter().map(|e| e.ts_ns).collect()
    }

    #[test]
    #[should_panic(expected = "capacity must be greater than zero")]
    fn zero_capacity_panics() {
        BetHistory::new(0);
    }

    #[test]
    fn empty_buffer_reports_zero_len() {
        let h = BetHistory::new(4);
        assert_eq!(h.len(), 0);
        assert!(h.is_empty());
        assert_eq!(h.capacity(), 4);
        assert_eq!(tss(&h), Vec::<u64>::new());
    }

    #[test]
    fn fills_up_to_capacity_preserving_order() {
        let mut h = BetHistory::new(3);
        h.push(bet(1));
        h.push(bet(2));
        assert_eq!(tss(&h), vec![1, 2]);
        assert_eq!(h.len(), 2);
        assert!(!h.is_empty());

        h.push(bet(3));
        assert_eq!(tss(&h), vec![1, 2, 3]);
        assert_eq!(h.len(), 3);
    }

    #[test]
    fn evicts_oldest_when_over_capacity() {
        let mut h = BetHistory::new(3);
        for ts in 1..=4 {
            h.push(bet(ts));
        }
        // Capacity is 3; the 4th push evicts ts=1.
        assert_eq!(h.len(), 3);
        assert_eq!(tss(&h), vec![2, 3, 4]);
    }

    #[test]
    fn iteration_order_correct_after_multiple_wraparounds() {
        let mut h = BetHistory::new(3);
        // Push far more than capacity so the write head wraps around several times.
        for ts in 1..=10 {
            h.push(bet(ts));
        }
        // Only the last 3 survive, still oldest → newest.
        assert_eq!(h.len(), 3);
        assert_eq!(tss(&h), vec![8, 9, 10]);
    }

    #[test]
    fn capacity_one_always_holds_only_the_latest() {
        let mut h = BetHistory::new(1);
        h.push(bet(1));
        assert_eq!(tss(&h), vec![1]);
        h.push(bet(2));
        assert_eq!(tss(&h), vec![2]);
        h.push(bet(3));
        assert_eq!(tss(&h), vec![3]);
        assert_eq!(h.len(), 1);
    }
}
