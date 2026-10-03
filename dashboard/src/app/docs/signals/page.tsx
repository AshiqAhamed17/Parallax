import { DocPage } from "@/components/doc-page";

export const metadata = { title: "Signals" };

const toc = [
  { id: "logical", label: "Logical-constraint" },
  { id: "cross-source", label: "Cross-source divergence" },
  { id: "sparse", label: "Why signals are rare" },
];

export default function SignalsDoc() {
  return (
    <DocPage
      eyebrow="How it works"
      title="Signals"
      intro="Two detectors look for mispricings that don't depend on a forecast being right. Both are deliberately conservative — a signal is a provable or hand-verified inconsistency, never a model guess."
      toc={toc}
    >
      <h2 id="logical">Logical-constraint arbitrage</h2>
      <p>
        Some markets are <strong>logically linked</strong>, so their probabilities must obey an
        ordering. A &ldquo;correlated group&rdquo; is a set of markets plus the constraints between
        them. Three kinds appear in the curated config:
      </p>
      <ul>
        <li>
          <strong>Magnitude nesting.</strong> Bitcoin&rsquo;s end-of-2026 close at rising thresholds:
          being above a higher price implies being above every lower one, so P must fall as the
          threshold rises — P(&gt;88k) ≤ P(&gt;77k) ≤ P(&gt;66k).
        </li>
        <li>
          <strong>Temporal nesting.</strong> &ldquo;AGI before date X&rdquo; at rising deadlines:
          happening before an earlier date implies happening before a later one, so P must rise as the
          deadline moves later.
        </li>
        <li>
          <strong>Event subset.</strong> Winning the presidency requires first being nominated, so
          P(wins) ≤ P(nominated).
        </li>
      </ul>
      <p>
        The detector checks each constraint against live prices. A breach is a <em>provable</em>{" "}
        mispricing — net of a per-leg cost assumption — not a modelling opinion. The{" "}
        <strong>Groups</strong> page shows each ladder and whether every constraint currently holds.
      </p>

      <h2 id="cross-source">Cross-source divergence</h2>
      <p>
        When the <strong>same event</strong> trades on both Manifold and Polymarket, the two implied
        probabilities should roughly agree. The detector compares the latest price on each venue for a
        set of <strong>hand-verified same-event pairs</strong> and flags gaps above a small threshold.
      </p>
      <div className="doc-note">
        <p>
          A pair only counts if both markets resolve on the identical event with the same criteria and
          timeframe. &ldquo;BTC above $66k at close&rdquo; vs &ldquo;BTC dips to $45k&rdquo; are
          different events and are deliberately excluded — pairing them would manufacture a fake
          divergence. Each signal carries an explicit &ldquo;divergence signal, not tradeable
          arbitrage&rdquo; note.
        </p>
      </div>

      <h2 id="sparse">Why signals are rare</h2>
      <p>
        With real data, the <strong>Signals</strong> page is intentionally sparse — and that is the
        honest result:
      </p>
      <ul>
        <li>
          <strong>Logical constraints usually hold.</strong> Liquid ladders are already arbitraged, so
          violations are uncommon. A consistent ladder is itself informative — it shows the monitoring
          works.
        </li>
        <li>
          <strong>Genuine cross-source pairs are few.</strong> Manifold and Polymarket phrase and slice
          most questions differently, so there are only a handful of true same-event matches, and
          efficient venues tend to agree closely.
        </li>
      </ul>
      <p>
        Prediction markets are mostly efficient; real arbitrage is rare. Parallax surfaces it when it
        exists rather than inventing it when it doesn&rsquo;t.
      </p>
    </DocPage>
  );
}
