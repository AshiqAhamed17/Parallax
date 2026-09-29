import { Reveal } from "@/components/reveal";

const STAGES = [
  {
    n: "01",
    title: "Ingest",
    body: "A Rust collector holds Manifold's live WebSocket bet stream, reconnecting automatically, and turns each bet into a typed event.",
  },
  {
    n: "02",
    title: "Model",
    body: "Per-market probability state updates in place; velocity, arrival-rate and volatility features feed a calibrated, Brier-scored model.",
  },
  {
    n: "03",
    title: "Detect",
    body: "Two detectors run: provable logical-constraint violations across correlated markets, and cross-source divergence vs. an independent forecast.",
  },
  {
    n: "04",
    title: "Serve",
    body: "Signals, markets and measured benchmarks land in SQLite and are served read-only to this dashboard. It never places an order.",
  },
];

const FACTS = [
  { value: "194k", unit: "events / s", label: "sustained ingest throughput, measured" },
  { value: "<40", unit: "µs", label: "signal-path latency, p50" },
  { value: "2", unit: "detectors", label: "logical-constraint + cross-source" },
];

// Recruiter-facing explainer of the pipeline. Numbered because it genuinely is a sequence.
export function HowItWorks() {
  return (
    <section className="flex flex-col gap-8">
      <Reveal>
        <div className="flex flex-col gap-2.5">
          <span className="eyebrow">how it works</span>
          <h2 className="text-3xl font-semibold tracking-tight text-foreground">
            From bet stream to signal, in microseconds
          </h2>
          <p className="max-w-[64ch] text-muted-foreground">
            A low-latency Rust pipeline does the fast part; a Python research layer does the
            statistics. They meet through shared storage — the simplest correct boundary.
          </p>
        </div>
      </Reveal>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STAGES.map((s, i) => (
          <Reveal key={s.n} delay={0.06 * i}>
            <div className="panel h-full p-5">
              <div className="font-mono text-sm text-amber">{s.n}</div>
              <div className="mt-3 text-lg font-semibold text-foreground">{s.title}</div>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.1}>
        <div className="grid gap-4 sm:grid-cols-3">
          {FACTS.map((f) => (
            <div key={f.label} className="flex items-baseline gap-2 rounded-2xl border border-white/8 px-5 py-4">
              <span className="font-mono text-3xl font-semibold tabnum text-foreground">{f.value}</span>
              <span className="font-mono text-sm text-amber">{f.unit}</span>
              <span className="ml-auto max-w-[16ch] text-right text-xs text-muted-foreground">{f.label}</span>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
