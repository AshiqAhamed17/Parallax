import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Data pipeline" };

const toc = [
  { id: "why-curated", label: "Why a curated set" },
  { id: "registry", label: "The registry" },
  { id: "backfill", label: "Prices & features" },
  { id: "refresh", label: "Refreshing" },
];

export default function DataPipeline() {
  return (
    <DocPage
      eyebrow="How it works"
      title="Data pipeline"
      intro="How the dashboard gets real data. A curated registry of liquid markets is backfilled from Manifold's REST API — real prices and a feature history reconstructed from each market's bet history."
      toc={toc}
    >
      <h2 id="why-curated">Why a curated set</h2>
      <p>
        Manifold&rsquo;s global bet firehose is mostly random, low-quality markets (joke markets,
        personal bets). Showing that raw would be live but unimpressive. Instead the dashboard tracks a{" "}
        <strong>curated set of ~50 liquid binary markets</strong> across politics, tech/AI, crypto,
        macro, and sports. Every price is still real — we only choose <em>which</em> real markets to
        watch.
      </p>
      <div className="doc-note">
        <p>
          Honest coverage note: Manifold has deep liquidity in politics, AI, and crypto, and thin
          liquidity in sports. The registry reflects that reality rather than faking rich sports
          coverage — a category simply yields fewer markets when the platform has fewer.
        </p>
      </div>

      <h2 id="registry">The registry</h2>
      <p>
        <code>research/src/parallax_research/ingest/registry.py</code> resolves the curated set against
        the live API in two ways:
      </p>
      <ul>
        <li>
          <strong>Topic buckets.</strong> For each topic slug (e.g. <code>us-politics</code>,{" "}
          <code>ai</code>, <code>bitcoin</code>), it fetches the most-liquid open binary markets and
          tags them with a display category.
        </li>
        <li>
          <strong>Pinned markets.</strong> Specific market ids the correlated-group ladders and
          cross-source pairs need, so those features always have data even if a market drops out of the
          liquidity ranking.
        </li>
      </ul>

      <h2 id="backfill">Prices &amp; features</h2>
      <p>
        For each curated market, <code>ingest/backfill.py</code> fetches its bet history from
        Manifold&rsquo;s REST API and writes four things:
      </p>
      <ul>
        <li><strong>A market row</strong> — real question, close time, category, resolution.</li>
        <li><strong>Bets</strong> — the raw bet history.</li>
        <li>
          <strong>Probability snapshots</strong> — a price series reconstructed from each bet&rsquo;s{" "}
          <code>probAfter</code>, which becomes the sparkline you see on the dashboard.
        </li>
        <li>
          <strong>Feature snapshots</strong> — probability velocity, bet-arrival rate, and realized
          volatility, computed over a trailing window with the same definitions the Rust feature-engine
          uses live.
        </li>
      </ul>
      <p>
        The feature snapshot&rsquo;s timestamp is aligned to the final price snapshot, so the model can
        join a market price to each feature row. The backfill is idempotent — re-running replaces a
        market&rsquo;s rows rather than duplicating them.
      </p>

      <h2 id="refresh">Refreshing</h2>
      <p>
        The whole pipeline is one orchestrator script, <code>scripts/build_live_db.py</code>, which
        backfills the curated markets, trains the model (see <a href="/docs/model">The model</a>), and
        runs the detectors (see <a href="/docs/signals">Signals</a>) into{" "}
        <code>data/parallax-live.db</code> — the database the API serves.
      </p>
      <pre>
        <code>{`# one command builds the whole live DB
uv run python scripts/build_live_db.py --db ../data/parallax-live.db

# or the cron-friendly wrapper
./deploy/refresh_live_db.sh`}</code>
      </pre>
      <p>
        Scheduling <code>refresh_live_db.sh</code> on a cron (e.g. every 6 hours) keeps prices current.
        It hits external APIs and takes a few minutes, so it runs out of band — never on a user
        request.
      </p>
    </DocPage>
  );
}
