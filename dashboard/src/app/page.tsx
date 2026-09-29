import Link from "next/link";
import { CountUp } from "@/components/count-up";
import { EdgeBar } from "@/components/edge-bar";
import { LiveDot } from "@/components/live-dot";
import { MagneticButton } from "@/components/magnetic-button";
import { MarketTerminal, type TerminalRow } from "@/components/market-terminal";
import { ProbTape } from "@/components/prob-tape";
import { Reveal } from "@/components/reveal";
import { SignalStrip } from "@/components/signal-strip";
import { Sparkline } from "@/components/sparkline";
import { SpotlightCard } from "@/components/spotlight-card";
import { TiltCard } from "@/components/tilt-card";
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
    <div className="flex flex-col gap-28 pb-16 sm:gap-36">
      {/* Hero */}
      <section className="relative isolate grid items-center gap-14 pt-10 lg:grid-cols-[1.05fr_0.95fr] lg:pt-20">
        <div className="pointer-events-none absolute -top-52 right-[-10%] -z-10 h-[720px] w-[720px] glow-emerald" aria-hidden />

        <div>
          <Reveal>
            <div className="inline-flex items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 backdrop-blur-sm">
              <LiveDot />
              <span className="eyebrow !normal-case !tracking-wide text-muted-foreground">
                tracking {open.length} live markets · {signals.total} open signals
              </span>
            </div>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-7 text-[clamp(3rem,7vw,5.75rem)] font-semibold leading-[0.95] tracking-tight">
              Markets move fast.
              <br />
              <span className="text-mint">Parallax</span> moves faster.
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-8 max-w-[50ch] text-lg leading-relaxed text-muted-foreground">
              A low-latency pipeline that watches Manifold&rsquo;s live bet stream, calibrates a
              probability for every market, and flags logical and cross-source mispricings.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <MagneticButton
                href="/markets"
                className="group items-center gap-3 rounded-full bg-primary py-2 pl-6 pr-2 text-base font-semibold text-primary-foreground shadow-[0_16px_50px_-12px_rgba(234,179,8,0.55)]"
              >
                Explore markets
                <span className="ml-3 flex size-8 items-center justify-center rounded-full bg-black/20 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
                  <Arrow />
                </span>
              </MagneticButton>
              <MagneticButton
                href="/performance"
                className="rounded-full border border-white/12 px-6 py-3 text-base font-medium text-foreground transition-colors duration-500 hover:border-white/25 hover:bg-white/[0.03]"
              >
                See measured latency
              </MagneticButton>
            </div>
          </Reveal>
          <Reveal delay={0.32}>
            <dl className="mt-14 flex gap-12">
              <HeroStat value={markets.length} label="markets tracked" />
              <HeroStat value={fmtEdge(featured?.prediction?.edge ?? null)} label="top model edge" />
              <HeroStat value={signals.total} label="live signals" />
            </dl>
          </Reveal>
        </div>

        {/* Featured-market spotlight — the product-as-art moment (tilt + spotlight) */}
        <Reveal delay={0.28}>{featured ? <FeaturedCard market={featured} /> : null}</Reveal>
      </section>

      <Reveal>
        <ProbTape items={open.map((m) => ({ question: m.question_text, probability: m.probability }))} />
      </Reveal>

      {/* Full live terminal */}
      <section className="flex flex-col gap-7">
        <SectionHead eyebrow="live markets" title="Market vs. calibrated model" note="Every tracked market, updated as bets land." />
        <Reveal>
          <SpotlightCard className="bezel" lift={false}>
            <MarketTerminal rows={rows} />
          </SpotlightCard>
        </Reveal>
      </section>

      {/* Signals + snapshot */}
      <section className="flex flex-col gap-7">
        <SectionHead eyebrow="signals" title="Where the market is wrong" note="Mispricings from both detectors, and the system at a glance." />
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <SpotlightCard className="panel" lift={false}>
            <SignalStrip signals={signals.items.slice(0, 6)} />
          </SpotlightCard>
          <SpotlightCard className="panel flex flex-col gap-7 p-7">
            <span className="frame-label">snapshot</span>
            <div className="grid grid-cols-2 gap-7">
              <Stat label="Markets" value={markets.length} sub={`${open.length} open`} />
              <Stat label="Top edge" value={fmtEdge(featured?.prediction?.edge ?? null)} sub="vs market" />
              <Stat label="Logical" value={nLogical} sub="constraint breaks" />
              <Stat label="Divergence" value={signals.total - nLogical} sub="cross-source" />
            </div>
            <Link
              href="/performance"
              className="mt-auto rounded-2xl border border-white/10 px-5 py-4 text-sm text-muted-foreground transition-colors duration-500 hover:border-white/20 hover:text-foreground"
            >
              Measured latency and backtest P&amp;L, from real runs
            </Link>
          </SpotlightCard>
        </div>
      </section>
    </div>
  );
}

function StatValue({ value }: { value: number | string }) {
  if (typeof value === "number") {
    return <CountUp to={value} />;
  }
  return <>{value}</>;
}

function Arrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path d="M3 11L11 3M11 3H5M11 3V9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HeroStat({ value, label }: { value: number | string; label: string }) {
  return (
    <div>
      <dd className="font-mono text-3xl font-semibold tabnum text-foreground">
        <StatValue value={value} />
      </dd>
      <dt className="mt-1.5 text-xs text-muted-foreground">{label}</dt>
    </div>
  );
}

function FeaturedCard({ market }: { market: Market }) {
  const p = market.prediction;
  return (
    <TiltCard className="bezel">
      <div className="bezel-core relative overflow-hidden p-7">
        <div className="pointer-events-none absolute -right-20 -top-20 h-52 w-52 glow-emerald" aria-hidden />
        <div className="flex items-center justify-between">
          <span className="eyebrow">top signal</span>
          <LiveDot label="live" />
        </div>
        <p className="mt-5 text-xl font-medium leading-snug text-foreground">{market.question_text}</p>
        <div className="mt-6 flex items-end gap-4">
          <span className="font-mono text-7xl font-semibold tabnum leading-none text-mint">
            {fmtProb(market.probability)}
          </span>
          <span className="mb-1.5 rounded-full bg-emerald/12 px-3 py-1 font-mono text-sm tabnum text-mint ring-1 ring-inset ring-emerald/25">
            edge {fmtEdge(p?.edge ?? null)}
          </span>
        </div>
        <div className="mt-6">
          <Sparkline points={market.recent} width={540} height={130} fill className="w-full" />
        </div>
        <div className="mt-6 space-y-2.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>model vs. market</span>
            <span className="font-mono tabnum">EV {fmtEv(p?.ev ?? null)}</span>
          </div>
          <EdgeBar pMarket={market.probability} pModel={p?.p_model ?? null} />
        </div>
      </div>
    </TiltCard>
  );
}

function SectionHead({ eyebrow, title, note }: { eyebrow: string; title: string; note: string }) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="eyebrow">{eyebrow}</span>
      <h2 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h2>
      <p className="max-w-[60ch] text-muted-foreground">{note}</p>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 font-mono text-3xl font-semibold tabnum text-foreground">
        <StatValue value={value} />
      </div>
      <div className="mt-1 text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}
