import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Running it" };

const toc = [
  { id: "prereq", label: "Prerequisites" },
  { id: "data", label: "1. Build the data" },
  { id: "api", label: "2. Serve the API" },
  { id: "dashboard", label: "3. Run the dashboard" },
  { id: "collector", label: "Optional: the collector" },
];

export default function RunningDoc() {
  return (
    <DocPage
      eyebrow="Reference"
      title="Running it"
      intro="Get Parallax running locally in three steps: build the real-data database, serve the read-only API against it, and run the dashboard. The live Rust collector is optional."
      toc={toc}
    >
      <h2 id="prereq">Prerequisites</h2>
      <ul>
        <li><strong>Rust</strong> (stable) — only needed for the optional collector/benchmarks.</li>
        <li><strong>uv</strong> — the Python package manager (for the research layer + API).</li>
        <li><strong>Node 20+</strong> — for the dashboard.</li>
        <li>Network access — the data build calls Manifold and Polymarket&rsquo;s public APIs (no keys needed).</li>
      </ul>

      <h2 id="data">1. Build the data</h2>
      <p>
        Build the curated real-data database. This backfills ~50 markets, trains the calibration model,
        and runs the detectors. It takes a few minutes (it fetches bet history over the network).
      </p>
      <pre><code>{`cd research
uv sync
uv run python scripts/build_live_db.py --db ../data/parallax-live.db`}</code></pre>
      <p>
        Useful flags: <code>--skip-model</code> (faster, no predictions), <code>--skip-signals</code>,{" "}
        <code>--train-markets N</code> (size of the resolved-market training corpus).
      </p>

      <h2 id="api">2. Serve the API</h2>
      <pre><code>{`./deploy/run_api.sh            # -> http://127.0.0.1:8000`}</code></pre>
      <p>
        The script defaults <code>PARALLAX_DB=data/parallax-live.db</code> and{" "}
        <code>PARALLAX_GROUPS_CONFIG=research/config/correlated_market_groups.yaml</code>. Set{" "}
        <code>PARALLAX_CORS_ORIGINS</code> to your dashboard origin if it isn&rsquo;t on localhost.
        Interactive OpenAPI docs are at <code>/docs</code> on the API.
      </p>

      <h2 id="dashboard">3. Run the dashboard</h2>
      <pre><code>{`cd dashboard
npm install
npm run build && npm start    # -> http://127.0.0.1:3000`}</code></pre>
      <p>
        The dashboard reads <code>NEXT_PUBLIC_API_URL</code> (defaults to{" "}
        <code>http://127.0.0.1:8000</code>). Use <code>npm run dev</code> for hot-reload during
        development.
      </p>
      <div className="doc-note">
        <p>
          To keep prices current, schedule <code>./deploy/refresh_live_db.sh</code> on a cron (e.g.
          every 6 hours). It rebuilds <code>parallax-live.db</code> in place; the API picks up the new
          data on its next request.
        </p>
      </div>

      <h2 id="collector">Optional: the live collector</h2>
      <p>
        The Rust collector is the true 24/7 low-latency path — it streams Manifold&rsquo;s WebSocket and
        is what the latency benchmarks measure. It isn&rsquo;t required for the dashboard (the REST
        backfill already provides real data), but it&rsquo;s the heart of the engineering story.
      </p>
      <pre><code>{`cargo build --release
./deploy/run_collector.sh                 # streams bets into data/parallax.db

# reproduce the latency / throughput report
cargo run -p bench-harness -- --rate 0    # unpaced: max throughput
cargo run -p bench-harness -- --rate 5000 # paced: latency under load`}</code></pre>
    </DocPage>
  );
}
