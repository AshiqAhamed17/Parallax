import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Architecture" };

const toc = [
  { id: "overview", label: "Overview" },
  { id: "two-languages", label: "Why two languages" },
  { id: "crates", label: "The Rust crates" },
  { id: "hot-path", label: "The hot path" },
  { id: "storage", label: "Storage is the contract" },
];

const DIAGRAM = `                   ┌──────────────── RUST (hot path) ────────────────┐
 Manifold WS ────▶ collector ─▶ probability-engine ─▶ feature-engine ─▶ SQLite
 (live bets)       (ingest)     (current prob)        (velocity, vol)   (storage)
                   └──────────────────────────────────────────────────┘
                                                                          │  shared file
 Polymarket REST ─────────────────────────────────────▶ PYTHON research ◀┘
 (periodic poll)                                         (backfill, model, detectors)
                                                                  │
                                                                  ▼
                                                   FastAPI  ──▶  Next.js dashboard`;

export default function Architecture() {
  return (
    <DocPage
      eyebrow="How it works"
      title="Architecture"
      intro="Two halves, one storage boundary. Rust owns the latency-critical hot path; Python owns the research and statistics. They never call each other — they meet only at a shared SQLite database."
      toc={toc}
    >
      <h2 id="overview">Overview</h2>
      <pre>
        <code>{DIAGRAM}</code>
      </pre>
      <p>
        Everything left of storage is <strong>Rust</strong>, optimized for speed. Everything right is{" "}
        <strong>Python</strong> (research/stats) and a <strong>TypeScript</strong> dashboard. Data
        flows one way: bets in, signals out.
      </p>

      <h2 id="two-languages">Why two languages</h2>
      <ul>
        <li>
          <strong>Rust</strong> handles the part that must be fast and correct under load — receiving
          the live stream and updating state per bet. It gives C-like speed with memory safety and no
          garbage collector, so there are no GC pauses to blow out tail latency.
        </li>
        <li>
          <strong>Python</strong> handles the math/stats that isn&rsquo;t latency-sensitive — market
          matching, divergence detection, fitting a calibrated model, backtesting. Its data/ML
          ecosystem (pandas, scikit-learn) makes this cheap to build.
        </li>
      </ul>
      <p>
        They communicate through <strong>shared storage, not RPC</strong>. Rust writes rows to SQLite;
        Python reads the same file. For a project at this scale that&rsquo;s the simplest correct
        boundary — no message queue, no gRPC — trading tight coupling for operational simplicity.
      </p>

      <h2 id="crates">The Rust crates</h2>
      <p>
        The Rust side is a Cargo <strong>workspace</strong> under <code>crates/</code>. Dependencies
        only point inward toward <code>common</code>, so the math engine literally cannot depend on
        the network client — which keeps it trivially testable.
      </p>
      <table>
        <thead>
          <tr>
            <th>Crate</th>
            <th>Responsibility</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>common</code></td>
            <td>Shared domain types — <code>BetEvent</code>, <code>BetSample</code>, <code>StageTimer</code>. No dependencies.</td>
          </tr>
          <tr>
            <td><code>manifold-client</code></td>
            <td>Manifold REST + WebSocket client; parses the wire format.</td>
          </tr>
          <tr>
            <td><code>probability-engine</code></td>
            <td>Per-market probability + a fixed-capacity ring buffer of recent bets.</td>
          </tr>
          <tr>
            <td><code>feature-engine</code></td>
            <td>Derives probability velocity, bet-arrival rate, and realized volatility.</td>
          </tr>
          <tr>
            <td><code>collector</code></td>
            <td>The always-on binary that wires it together and writes storage.</td>
          </tr>
          <tr>
            <td><code>bench-harness</code></td>
            <td>Load generator + HDR-histogram latency report (not shipped to prod).</td>
          </tr>
        </tbody>
      </table>

      <h2 id="hot-path">The hot path</h2>
      <p>Inside the collector, one bet flows through four timed stages:</p>
      <pre>
        <code>{`WS-receive ──▶ state-update ──▶ feature-calc ──▶ storage-write
            └──── ingest task ────┘   │ bounded mpsc │  └ writer task ┘`}</code>
      </pre>
      <ul>
        <li>
          <strong>A bounded channel splits the work into two async tasks.</strong> The ingest task
          does the fast in-memory work; it hands finished records to the writer task over a bounded{" "}
          <code>tokio::sync::mpsc</code> channel (capacity 1024). The hot path never blocks on the
          disk — if the writer falls behind, the channel applies <em>backpressure</em> instead of
          growing memory without bound.
        </li>
        <li>
          <strong>Per-stage latency is stamped by <code>StageTimer</code>.</strong> In production the
          timer is a zero-cost <code>Disabled</code> variant (reads no clock); the benchmark harness
          turns it on and records nanosecond timestamps into HDR histograms, reporting
          p50/p95/p99/p99.9/max.
        </li>
      </ul>
      <p>
        Profiling and optimizing this path produced a <strong>~175% throughput improvement</strong>{" "}
        (70,586 → 194,444 events/s) — mostly by removing per-event heap allocation and caching SQL
        statements. The full numbers live in <code>benchmarks/latency-report.md</code>.
      </p>

      <h2 id="storage">Storage is the contract</h2>
      <p>
        The SQLite schema is the interface between everything. The Rust collector owns the migration;
        the Python layer mirrors it. Key tables:
      </p>
      <table>
        <thead>
          <tr>
            <th>Table</th>
            <th>Written by</th>
            <th>Holds</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><code>markets</code></td><td>collector / backfill</td><td>id, question, close time, category, outcome</td></tr>
          <tr><td><code>probability_snapshots</code></td><td>collector / backfill</td><td>probability over time (the sparklines)</td></tr>
          <tr><td><code>feature_snapshots</code></td><td>collector / backfill</td><td>velocity, arrival rate, realized volatility</td></tr>
          <tr><td><code>model_predictions</code></td><td>Python model</td><td>p_model, p_market, edge, EV</td></tr>
          <tr><td><code>arbitrage_signals</code></td><td>Python detectors</td><td>both signal types</td></tr>
          <tr><td><code>market_matches</code></td><td>Python matching</td><td>Manifold↔Polymarket links</td></tr>
        </tbody>
      </table>
    </DocPage>
  );
}
