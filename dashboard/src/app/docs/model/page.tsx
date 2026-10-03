import { DocPage } from "@/components/doc-page";

export const metadata = { title: "The model" };

const toc = [
  { id: "what", label: "What the model is" },
  { id: "training", label: "How it's trained" },
  { id: "calibration", label: "Calibration & honesty" },
  { id: "edge", label: "What 'edge' means" },
];

export default function ModelDoc() {
  return (
    <DocPage
      eyebrow="How it works"
      title="The model"
      intro="A calibrated probability baseline — deliberately simple, and measured honestly against the market's own price. The point is a trustworthy, well-measured number, not a market-beating edge."
      toc={toc}
    >
      <h2 id="what">What the model is</h2>
      <p>
        A <strong>logistic-regression calibration baseline</strong> (impute → standardize → logistic),
        trained on four features per market:
      </p>
      <ul>
        <li><strong>probability velocity</strong> — how fast the price is moving</li>
        <li><strong>bet-arrival rate</strong> — how much activity there is</li>
        <li><strong>realized volatility</strong> — how choppy the recent price has been</li>
        <li><strong>market price</strong> — the market&rsquo;s own implied probability</li>
      </ul>
      <p>
        It is intentionally simple. The goal (per the project&rsquo;s research notes) is to show whether
        even a simple model is <em>calibrated</em> — not to win an accuracy contest. A
        confident-but-miscalibrated model is worse than useless.
      </p>

      <h2 id="training">How it&rsquo;s trained</h2>
      <p>
        Training needs <strong>resolved</strong> markets, where the YES/NO outcome is known and can
        serve as a label. The pipeline fetches a corpus of resolved Manifold markets, reconstructs
        their features from bet history at points <em>before</em> each market closed (an anti-lookahead
        guard — training on post-close information would make measured skill meaningless), and fits the
        model. It is then scored on a held-out 20% split.
      </p>

      <h2 id="calibration">Calibration &amp; honesty</h2>
      <p>
        The model&rsquo;s predictions are compared to the market price on the holdout using{" "}
        <strong>Brier score</strong>, <strong>log loss</strong>, and <strong>expected calibration
        error</strong> (all lower-is-better). The result is written to a report and shown on the
        dashboard&rsquo;s Performance page.
      </p>
      <div className="doc-note">
        <p>
          <strong>The market is currently better calibrated than the model</strong> (lower Brier). We
          publish this rather than hide it. A simple model over four features does not reliably beat a
          liquid market&rsquo;s own price — and pretending otherwise would be the dishonest move. This
          honesty is the point of the Performance page.
        </p>
      </div>

      <h2 id="edge">What &ldquo;edge&rdquo; means</h2>
      <p>
        On the Markets page every market shows an <strong>edge</strong> and <strong>EV</strong>. Given
        the calibration result above, read these carefully:
      </p>
      <ul>
        <li>
          <strong>Edge</strong> is the model&rsquo;s <em>disagreement</em> with the market price
          (p_model − p_market) — useful for spotting where the model and market diverge.
        </li>
        <li>
          It is <strong>not</strong> a profit guarantee. Since the market out-calibrates the model,
          most of that &ldquo;edge&rdquo; is model error, not alpha.
        </li>
      </ul>
      <p>
        Every prediction is stored (not just positive-EV ones) so the dashboard shows the
        model&rsquo;s view on every market, framed as disagreement rather than opportunity.
      </p>
    </DocPage>
  );
}
