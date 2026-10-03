import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Tech stack" };

const toc = [
  { id: "rust", label: "Rust (hot path)" },
  { id: "python", label: "Python (research)" },
  { id: "frontend", label: "Frontend" },
  { id: "sources", label: "Data sources" },
  { id: "why", label: "Why these choices" },
];

export default function TechStackDoc() {
  return (
    <DocPage
      eyebrow="Reference"
      title="Tech stack"
      intro="Each layer uses the tool that fits its job: Rust for predictable latency, Python for statistics, Next.js for the dashboard, and public market APIs for data."
      toc={toc}
    >
      <h2 id="rust">Rust (hot path)</h2>
      <table>
        <thead><tr><th>Tool</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td><strong>Rust</strong> (Cargo workspace)</td><td>The low-latency ingestion pipeline; C-like speed, memory safety, no GC.</td></tr>
          <tr><td><strong>Tokio</strong></td><td>Async runtime — the ingest/writer tasks and bounded <code>mpsc</code> channel.</td></tr>
          <tr><td><strong>rusqlite</strong></td><td>SQLite writer with cached prepared statements.</td></tr>
          <tr><td><strong>quanta</strong></td><td>TSC-backed clock for cheap per-stage timestamps.</td></tr>
          <tr><td><strong>hdrhistogram</strong></td><td>High-dynamic-range histograms for honest tail-latency percentiles.</td></tr>
        </tbody>
      </table>

      <h2 id="python">Python (research)</h2>
      <table>
        <thead><tr><th>Tool</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td><strong>Python 3.12 + uv</strong></td><td>The research package and API; uv for fast, reproducible installs.</td></tr>
          <tr><td><strong>httpx</strong></td><td>REST clients for Manifold and Polymarket.</td></tr>
          <tr><td><strong>pandas</strong></td><td>Training-set assembly and feature joins.</td></tr>
          <tr><td><strong>scikit-learn</strong></td><td>The logistic-regression calibration model.</td></tr>
          <tr><td><strong>FastAPI</strong></td><td>The read-only API, with automatic OpenAPI docs.</td></tr>
          <tr><td><strong>pytest</strong></td><td>185+ tests across the research layer.</td></tr>
        </tbody>
      </table>

      <h2 id="frontend">Frontend</h2>
      <table>
        <thead><tr><th>Tool</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td><strong>Next.js 16</strong> (App Router)</td><td>The dashboard and this docs site; server components with live data.</td></tr>
          <tr><td><strong>React 19</strong></td><td>UI.</td></tr>
          <tr><td><strong>Tailwind v4</strong></td><td>Styling via CSS <code>@theme</code> tokens (the obsidian + amber system).</td></tr>
          <tr><td><strong>motion</strong></td><td>Interaction animations (tilt, spotlight, magnetic buttons); scroll reveals use native IntersectionObserver.</td></tr>
        </tbody>
      </table>

      <h2 id="sources">Data sources</h2>
      <ul>
        <li><strong>Manifold Markets</strong> — live bet WebSocket (<code>wss://api.manifold.markets/ws</code>) and REST (<code>api.manifold.markets/v0</code>). Public, no auth.</li>
        <li><strong>Polymarket</strong> — the Gamma REST API (<code>gamma-api.polymarket.com</code>) for the second source in cross-source divergence. Public, polled gently.</li>
      </ul>

      <h2 id="why">Why these choices</h2>
      <ul>
        <li><strong>Rust on the hot path</strong> buys predictable microsecond latency with no GC pauses — the whole point of the engineering story.</li>
        <li><strong>Python for research</strong> because the stats/ML ecosystem makes it cheap, and that layer isn&rsquo;t latency-sensitive.</li>
        <li><strong>SQLite as the boundary</strong> is the simplest correct integration between the two halves — no queue, no RPC.</li>
        <li><strong>Next.js + Tailwind</strong> for a fast, server-rendered dashboard that reads live data and still looks distinctive.</li>
      </ul>
    </DocPage>
  );
}
