import { DocPage } from "@/components/doc-page";

export const metadata = { title: "API reference" };

const toc = [
  { id: "base", label: "Base & conventions" },
  { id: "endpoints", label: "Endpoints" },
  { id: "markets", label: "Markets" },
  { id: "groups", label: "Groups" },
  { id: "arbitrage", label: "Arbitrage" },
  { id: "reports", label: "Reports" },
  { id: "models", label: "Response models" },
];

const MARKET_JSON = `{
  "market_id": "26QhQQ6hsQ",
  "platform": "manifold",
  "question_text": "Will Bitcoin be higher than $66,666 at the end of 2026?",
  "close_time": "2026-12-31T23:59:00+00:00",
  "category": "Crypto",
  "resolved_outcome": null,
  "probability": 0.884,
  "last_updated_ns": 1790000000000000000,
  "prediction": { "p_model": 0.945, "p_market": 0.884, "edge": 0.061, "ev": 0.061, "ts_ns": 1790000000000000000 },
  "recent": [0.61, 0.66, 0.72, 0.88]
}`;

const ARB_JSON = `{
  "items": [
    {
      "id": 3,
      "type": "cross_source_divergence",
      "market_refs": ["ulm6rrplx5", "0x18b1c1…"],
      "edge": -0.031,
      "detected_at": "2026-09-30T14:00:00+00:00",
      "details": { "p_manifold": 0.475, "p_polymarket": 0.506, "divergence": 0.031,
                   "direction": "polymarket_higher", "note": "divergence signal, not tradeable arbitrage" },
      "labels": { "ulm6rrplx5": "Will JD Vance be nominated for President…" }
    }
  ],
  "total": 3, "limit": 50, "offset": 0
}`;

export default function ApiDoc() {
  return (
    <DocPage
      eyebrow="Reference"
      title="API reference"
      intro="The backend is a read-only FastAPI service. Every endpoint is a GET; there are no write, auth, or execution endpoints by design. Interactive OpenAPI docs are served at /docs on the API itself."
      toc={toc}
    >
      <h2 id="base">Base &amp; conventions</h2>
      <ul>
        <li>Base URL (local): <code>http://127.0.0.1:8000</code>. The dashboard reads it from <code>NEXT_PUBLIC_API_URL</code>.</li>
        <li>All responses are JSON. All endpoints are <code>GET</code> and read-only.</li>
        <li>Timestamps are either ISO-8601 strings (<code>close_time</code>, <code>detected_at</code>) or integer nanoseconds (<code>ts_ns</code>, <code>last_updated_ns</code>).</li>
        <li>Probabilities are floats in <code>[0, 1]</code>.</li>
      </ul>

      <h2 id="endpoints">Endpoints</h2>
      <table>
        <thead>
          <tr><th>Method &amp; path</th><th>Returns</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>GET /health</code></td><td>HealthResponse</td><td>Liveness check.</td></tr>
          <tr><td><code>GET /markets</code></td><td>MarketOut[]</td><td>Every tracked market with its latest price, prediction, and recent series.</td></tr>
          <tr><td><code>GET /markets/{"{id}"}</code></td><td>MarketOut</td><td>A single market by id.</td></tr>
          <tr><td><code>GET /markets/{"{id}"}/replay</code></td><td>ReplayOut</td><td>Full probability time series for a market.</td></tr>
          <tr><td><code>GET /groups</code></td><td>GroupOut[]</td><td>Correlated-market ladders with live constraint checks.</td></tr>
          <tr><td><code>GET /arbitrage</code></td><td>PaginatedSignals</td><td>Detected signals (both detectors), paginated.</td></tr>
          <tr><td><code>GET /benchmarks</code></td><td>ReportOut[]</td><td>Committed latency/throughput reports.</td></tr>
          <tr><td><code>GET /backtests</code></td><td>ReportOut[]</td><td>Backtest reports.</td></tr>
          <tr><td><code>GET /calibration</code></td><td>ReportOut[]</td><td>Honest model-vs-market calibration reports.</td></tr>
        </tbody>
      </table>

      <h2 id="markets">Markets</h2>
      <p><code>GET /markets</code> returns an array of <code>MarketOut</code>. Example element:</p>
      <pre><code>{MARKET_JSON}</code></pre>
      <p>
        <code>prediction</code> is <code>null</code> for markets with no stored model prediction;{" "}
        <code>recent</code> is the trailing probability series used for the sparkline.
      </p>

      <h2 id="groups">Groups</h2>
      <p>
        <code>GET /groups</code> returns each correlated ladder as a <code>GroupOut</code> with its{" "}
        markets, constraints, and a <code>consistent</code> flag. Each constraint reports{" "}
        <code>holds</code> plus <code>gross_violation</code> / <code>net_violation</code> (net of a
        per-leg cost), so you can see not just whether it holds but by how much.
      </p>

      <h2 id="arbitrage">Arbitrage</h2>
      <p><code>GET /arbitrage</code> — query parameters:</p>
      <table>
        <thead><tr><th>Param</th><th>Type</th><th>Default</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td><code>limit</code></td><td>int</td><td>50</td><td>1–200</td></tr>
          <tr><td><code>offset</code></td><td>int</td><td>0</td><td>≥ 0</td></tr>
          <tr><td><code>type</code></td><td>string</td><td>—</td><td><code>logical_constraint</code> or <code>cross_source_divergence</code></td></tr>
        </tbody>
      </table>
      <pre><code>{ARB_JSON}</code></pre>
      <p>
        <code>labels</code> maps each resolvable market ref to its question text (so a client can show
        readable titles instead of raw ids); a Polymarket conditionId has no market row and is simply
        omitted.
      </p>

      <h2 id="reports">Reports</h2>
      <p>
        <code>/benchmarks</code>, <code>/backtests</code>, and <code>/calibration</code> each return an
        array of <code>ReportOut</code> — committed Markdown reports (<code>name</code> +{" "}
        <code>content</code>) rendered on the Performance page. These are how the dashboard shows real
        measured numbers rather than hard-coded figures.
      </p>

      <h2 id="models">Response models</h2>
      <p><strong>MarketOut</strong></p>
      <table>
        <thead><tr><th>Field</th><th>Type</th></tr></thead>
        <tbody>
          <tr><td>market_id, platform, question_text, close_time</td><td>string</td></tr>
          <tr><td>category</td><td>string | null</td></tr>
          <tr><td>resolved_outcome</td><td>int | null (1 = YES, 0 = NO)</td></tr>
          <tr><td>probability</td><td>float | null</td></tr>
          <tr><td>last_updated_ns</td><td>int | null</td></tr>
          <tr><td>prediction</td><td>ModelPrediction | null</td></tr>
          <tr><td>recent</td><td>float[]</td></tr>
        </tbody>
      </table>
      <p><strong>ArbitrageSignal</strong>: id, type, market_refs[], edge, detected_at, details{"{}"}, labels{"{}"}.</p>
      <p><strong>GroupOut</strong>: id, description, category, consistent, markets[], constraints[].</p>
    </DocPage>
  );
}
