import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Introduction" };

const toc = [
  { id: "what", label: "What Parallax is" },
  { id: "signals", label: "The two signals" },
  { id: "honest", label: "Honest by design" },
  { id: "read", label: "How to read these docs" },
];

export default function DocsIntro() {
  return (
    <DocPage
      eyebrow="Documentation"
      title="Introduction"
      intro="Parallax is a low-latency pipeline that watches a live prediction-market bet stream, keeps a calibrated probability for every market in real time, and flags mispricings. It observes and reports — it never trades."
      toc={toc}
    >
      <h2 id="what">What Parallax is</h2>
      <p>
        A prediction market turns a question (&ldquo;Will X happen?&rdquo;) into a price between 0 and
        1 that behaves like the crowd&rsquo;s probability. Parallax treats each market as a
        probability that moves over time, and does two things with that stream:
      </p>
      <ul>
        <li>
          <strong>Ingests it fast.</strong> A Rust pipeline consumes Manifold Markets&rsquo; live
          WebSocket bet stream and updates each market&rsquo;s probability, recent history, and
          derived features on every bet — instrumented and benchmarked end to end.
        </li>
        <li>
          <strong>Analyses it honestly.</strong> A Python research layer reconstructs real prices for
          a curated set of liquid markets, trains a calibrated model, and runs two mispricing
          detectors. A read-only API and a Next.js dashboard surface the results.
        </li>
      </ul>
      <p>
        It is a research-and-engineering portfolio project, not a trading product. There is no
        order-execution code anywhere in the repository.
      </p>

      <h2 id="signals">The two signals</h2>
      <p>Parallax looks for two kinds of mispricing that don&rsquo;t require a forecast to be &ldquo;right&rdquo;:</p>
      <ul>
        <li>
          <strong>Logical-constraint violations.</strong> Some markets are logically linked — if
          Bitcoin ends the year above $88k it is necessarily above $66k, so P(&gt;88k) ≤ P(&gt;66k).
          When live prices break that ordering, it is a <em>provable</em> mispricing, not an opinion.
        </li>
        <li>
          <strong>Cross-source divergence.</strong> When the <em>same</em> event trades on both
          Manifold and Polymarket at different prices, that gap is a real divergence between two
          venues.
        </li>
      </ul>
      <p>
        See <a href="/docs/signals">Signals</a> for how each detector works — and why genuine signals
        are rarer than you might expect.
      </p>

      <h2 id="honest">Honest by design</h2>
      <div className="doc-note">
        <p>
          Every figure on the dashboard is real — real market prices, a model trained on real
          outcomes, and benchmarks from instrumented runs. Where the model loses to the market, the
          dashboard says so. There are no fabricated numbers and no invented edge.
        </p>
      </div>
      <p>
        This matters because the easy version of a project like this fakes a busy signal feed and a
        market-beating model. Parallax does the opposite: it reports a calibration score where the
        market currently wins, and it shows only hand-verified signals. See{" "}
        <a href="/docs/model">The model</a>.
      </p>

      <h2 id="read">How to read these docs</h2>
      <p>The sidebar is ordered as a path:</p>
      <ul>
        <li>
          <a href="/docs/architecture">Architecture</a> — the map of the system and the low-latency
          hot path.
        </li>
        <li>
          <a href="/docs/data-pipeline">Data pipeline</a> — how real markets, prices, and features are
          built.
        </li>
        <li>
          <a href="/docs/model">The model</a> and <a href="/docs/signals">Signals</a> — the analysis
          layer.
        </li>
        <li>
          <a href="/docs/api">API reference</a> and <a href="/docs/running">Running it</a> — use it
          yourself.
        </li>
      </ul>
    </DocPage>
  );
}
