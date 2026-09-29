import { Reveal } from "@/components/reveal";
import { ReportView } from "@/components/report-view";
import { getBacktests, getBenchmarks } from "@/lib/api";
import type { Report } from "@/lib/types";

export const dynamic = "force-dynamic";

function parseThroughput(reports: Report[]): number[] | null {
  for (const r of reports) {
    const m = r.content.match(
      /throughput\s*\|\s*([\d,]+)\s*ev\/s\s*\|\s*([\d,]+)\s*ev\/s\s*\|\s*([\d,]+)\s*ev\/s/i,
    );
    if (m) return [m[1], m[2], m[3]].map((s) => Number(s.replace(/,/g, "")));
  }
  return null;
}

export default async function PerformancePage() {
  let benchmarks: Report[] = [];
  let backtests: Report[] = [];
  try {
    [benchmarks, backtests] = await Promise.all([getBenchmarks(), getBacktests()]);
  } catch {
    // API unreachable
  }
  const throughput = parseThroughput(benchmarks);

  return (
    <div className="flex flex-col gap-12 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-3">
          <span className="eyebrow">performance</span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Measured, not estimated</h1>
          <p className="max-w-[64ch] text-muted-foreground">
            Every figure below comes from an instrumented run of the real pipeline — latency
            percentiles from the Rust collector, and P&amp;L from the backtester against real resolved
            markets. Reproducible with the commands shown in each report.
          </p>
        </header>
      </Reveal>

      {throughput ? (
        <Reveal delay={0.06}>
          <div className="bezel">
            <div className="bezel-core p-7">
              <div className="flex items-baseline justify-between">
                <span className="eyebrow">sustained throughput · events / second</span>
                <span className="font-mono text-xs text-muted-foreground">v1 → v2 → v3</span>
              </div>
              <ThroughputBars values={throughput} />
            </div>
          </div>
        </Reveal>
      ) : null}

      <Reveal delay={0.1}>
        <ReportSection eyebrow="latency benchmarks" title="Ingestion pipeline" reports={benchmarks} />
      </Reveal>
      <Reveal delay={0.14}>
        <ReportSection eyebrow="backtests" title="Strategy validation" reports={backtests} />
      </Reveal>
    </div>
  );
}

function ThroughputBars({ values }: { values: number[] }) {
  const labels = ["v1", "v2", "v3"];
  const max = Math.max(...values);
  return (
    <div className="mt-6 grid grid-cols-3 gap-6">
      {values.map((v, i) => (
        <div key={i} className="flex flex-col justify-end">
          <div className="mb-2 font-mono text-2xl font-semibold tabnum text-amber">
            {v.toLocaleString()}
          </div>
          <div className="h-40 overflow-hidden rounded-lg bg-white/[0.03]">
            <div
              className="h-full w-full origin-bottom bg-gradient-to-t from-amber/70 to-amber-bright/90"
              style={{ transform: `scaleY(${v / max})`, transformOrigin: "bottom" }}
            />
          </div>
          <div className="mt-2 font-mono text-xs text-muted-foreground">
            {labels[i]}
            {i === values.length - 1 ? ` · +${Math.round((v / values[0] - 1) * 100)}% vs v1` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReportSection({
  eyebrow,
  title,
  reports,
}: {
  eyebrow: string;
  title: string;
  reports: Report[];
}) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <span className="eyebrow">{eyebrow}</span>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
      </div>
      {reports.length === 0 ? (
        <div className="panel px-6 py-10 text-sm text-muted-foreground">No reports available.</div>
      ) : (
        reports.map((r, i) => (
          <details key={r.name} className="panel group px-6 py-4" open={i === 0}>
            <summary className="flex cursor-pointer items-center justify-between text-sm text-foreground marker:content-none">
              <span className="font-mono">{r.name}</span>
              <span className="text-muted-foreground transition-transform group-open:rotate-90">›</span>
            </summary>
            <div className="mt-4 border-t border-white/[0.06] pt-4">
              <ReportView content={r.content} />
            </div>
          </details>
        ))
      )}
    </section>
  );
}
