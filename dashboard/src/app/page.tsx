import Link from "next/link";
import { EdgeBar } from "@/components/edge-bar";
import { LiveDot } from "@/components/live-dot";
import { MarketTerminal, type TerminalRow } from "@/components/market-terminal";
import { ProbTape } from "@/components/prob-tape";
import { Reveal } from "@/components/reveal";
import { SignalStrip } from "@/components/signal-strip";
import { Sparkline } from "@/components/sparkline";
import { getMarkets, getSignals } from "@/lib/api";
import { fmtEdge, fmtEv, fmtProb } from "@/lib/format";
import type { ArbitrageSignal, Market, PaginatedSignals } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Home() {
  let markets: Market[] = [];
  let signals: PaginatedSignals = { items: [], total: 0, limit: 0, offset: 0 };
  try {
    [markets, signals] = await Promise.all([getMarkets(), getSignals({ limit: 100 })]);
  } catch {
    // API unreachable — sections degrade to quiet empty states rather than crashing.
  }

  const open = markets.filter((m) => m.resolved_outcome == null);
  const withPred = markets.filter((m) => m.prediction != null);
  const featured = [...withPred].sort(
    (a, b) => Math.abs(b.prediction!.edge) - Math.abs(a.prediction!.edge),
  )[0];
  const rows: TerminalRow[] = markets.slice(0, 8).map((m) => ({ market: m, points: m.recent }));
  const nLogical = signals.items.filter(
    (s: ArbitrageSignal) => s.type === "logical_constraint",
  ).length;

  return (
    <div className="flex flex-col gap-16">
      {/* Hero */}
      <section className="relative isolate grid items-center gap-12 pt-6 lg:grid-cols-[1.02fr_0.98fr] lg:pt-10">
        <div className="pointer-events-none absolute inset-x-0 -top-24 -z-10 h-[560px] grid-texture" aria-hidden />
        <div className="pointer-events-none absolute -top-40 right-[-6%] -z-10 h-[620px] w-[680px] glow-violet" aria-hidden />

        <div>
          <Reveal>
            <div className="inline-flex items-center gap-2.5 rounded-full border border-border bg-surface/60 px-3.5 py-1.5 font-mono text-xs text-muted-foreground">
              <LiveDot />
              tracking {open.length} live markets · {signals.total} open signals
            </div>
          </Reveal>
          <Reveal delay={0.06}>
            <h1 className="mt-6 text-6xl font-extrabold leading-[0.95] tracking-tight sm:text-7xl">
              Markets move fast.
              <br />
              <span className="text-iris">Parallax</span> moves faster.
            </h1>
          </Reveal>
          <Reveal delay={0.12}>
            <p className="mt-7 max-w-[52ch] text-lg leading-relaxed text-muted-foreground">
              A low-latency pipeline that watches Manifold&rsquo;s live bet stream, calibrates a
              probability for every market, and flags logical and cross-source mispricings.
            </p>
          </Reveal>
          <Reveal delay={0.18}>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/markets"
                className="rounded-xl bg-primary px-5 py-3 text-base font-semibold text-primary-foreground shadow-[0_10px_40px_-10px_rgba(139,124,246,0.7)] transition-transform hover:-translate-y-0.5"
              >
                Explore markets
              </Link>
              <Link
                href="/performance"
                className="rounded-xl border border-border px-5 py-3 text-base font-medium text-foreground transition-colors hover:border-violet/50"
              >
                See measured latency
              </Link>
            </div>
          </Reveal>
          <Reveal delay={0.24}>
            <dl className="mt-10 flex gap-8">
              <HeroStat value={String(markets.length)} label="markets tracked" />
              <HeroStat value={fmtEdge(featured?.prediction?.edge ?? null)} label="top model edge" />
              <HeroStat value={String(signals.total)} label="live signals" />
            </dl>
          </Reveal>
        </div>

        {/* Featured-market spotlight — the product-as-art moment */}
        <Reveal delay={0.28}>
          {featured ? <FeaturedCard market={featured} /> : null}
        </Reveal>
      </section>

      <Reveal>
        <ProbTape items={open.map((m) => ({ question: m.question_text, probability: m.probability }))} />
      </Reveal>

      {/* Full live terminal */}
      <section className="flex flex-col gap-5">
        <SectionHead title="Live markets" note="Market vs. calibrated model, updated as bets land." />
        <Reveal>
          <MarketTerminal rows={rows} />
        </Reveal>
      </section>

      {/* Signals + snapshot */}
      <section className="flex flex-col gap-5">
        <SectionHead title="Signals & snapshot" note="Mispricings from both detectors, and the system at a glance." />
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <SignalStrip signals={signals.items.slice(0, 6)} />
          <div className="panel flex flex-col gap-6 p-6">
            <span className="frame-label">snapshot</span>
            <div className="grid grid-cols-2 gap-6">
              <Stat label="Markets" value={String(markets.length)} sub={`${open.length} open`} />
              <Stat label="Top edge" value={fmtEdge(featured?.prediction?.edge ?? null)} sub="vs market" />
              <Stat label="Logical" value={String(nLogical)} sub="constraint breaks" />
              <Stat label="Divergence" value={String(signals.total - nLogical)} sub="cross-source" />
            </div>
            <Link
              href="/performance"
              className="mt-auto rounded-xl border border-border px-4 py-3.5 text-sm text-muted-foreground transition-colors hover:border-violet/50 hover:text-foreground"
            >
              Measured latency and backtest P&amp;L, from real runs
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dd className="font-mono text-2xl font-semibold tabnum text-foreground">{value}</dd>
      <dt className="mt-1 text-xs text-muted-foreground">{label}</dt>
    </div>
  );
}

function FeaturedCard({ market }: { market: Market }) {
  const p = market.prediction;
  return (
    <div className="panel relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 glow-violet" aria-hidden />
      <div className="flex items-center justify-between">
        <span className="frame-label">top signal</span>
        <LiveDot label="live" />
      </div>
      <p className="mt-4 text-lg font-medium leading-snug text-foreground">{market.question_text}</p>
      <div className="mt-5 flex items-end gap-4">
        <span className="font-mono text-6xl font-semibold tabnum leading-none text-iris">
          {fmtProb(market.probability)}
        </span>
        <span className="mb-1 rounded-lg bg-violet/15 px-2.5 py-1 font-mono text-sm tabnum text-iris ring-1 ring-inset ring-violet/30">
          edge {fmtEdge(p?.edge ?? null)}
        </span>
      </div>
      <div className="mt-5">
        <Sparkline points={market.recent} width={520} height={120} fill className="w-full" />
      </div>
      <div className="mt-5 space-y-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>model vs. market</span>
          <span className="font-mono tabnum">EV {fmtEv(p?.ev ?? null)}</span>
        </div>
        <EdgeBar pMarket={market.probability} pModel={p?.p_model ?? null} />
      </div>
    </div>
  );
}

function SectionHead({ title, note }: { title: string; note: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-2xl font-bold tracking-tight text-foreground">{title}</h2>
      <p className="text-sm text-muted-foreground">{note}</p>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1.5 font-mono text-3xl font-semibold tabnum text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}
