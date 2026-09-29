import Link from "next/link";
import { notFound } from "next/navigation";
import { EdgeBar } from "@/components/edge-bar";
import { LiveDot } from "@/components/live-dot";
import { ProbChart } from "@/components/prob-chart";
import { Reveal } from "@/components/reveal";
import { SpotlightCard } from "@/components/spotlight-card";
import { StatusPill } from "@/components/status-pill";
import { WatchlistToggle } from "@/components/watchlist-toggle";
import { getMarket, getReplay, getSignals } from "@/lib/api";
import { fmtDate, fmtEdge, fmtEv, fmtProb } from "@/lib/format";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function MarketDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const market = await getMarket(id);
  if (!market) notFound();

  const [replay, signals] = await Promise.all([
    getReplay(id).catch(() => null),
    getSignals({ limit: 200 }).catch(() => null),
  ]);
  const points = replay?.points.map((p) => p.probability) ?? market.recent;
  const mine = signals?.items.filter((s) => s.market_refs.includes(id)) ?? [];
  const p = market.prediction;
  const resolved = market.resolved_outcome != null;

  return (
    <div className="flex flex-col gap-10 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-4">
          <Link href="/markets" className="eyebrow transition-colors hover:text-foreground">
            ← markets
          </Link>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <WatchlistToggle marketId={market.market_id} className="mt-1 shrink-0" />
              <h1 className="max-w-[24ch] text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
                {market.question_text}
              </h1>
            </div>
            {resolved ? (
              <StatusPill status="neutral" label={`resolved ${market.resolved_outcome === 1 ? "YES" : "NO"}`} />
            ) : (
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5">
                <LiveDot />
                <span className="text-xs text-muted-foreground">open</span>
              </span>
            )}
          </div>
        </header>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="bezel">
          <div className="bezel-core p-7">
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <span className="eyebrow">market probability</span>
                <div className="mt-2 font-mono text-6xl font-semibold tabnum text-amber">
                  {fmtProb(market.probability)}
                </div>
              </div>
              <div className="flex gap-8">
                <Metric label="Model" value={fmtProb(p?.p_model ?? null)} />
                <Metric label="Edge" value={fmtEdge(p?.edge ?? null)} accent />
                <Metric label="EV" value={fmtEv(p?.ev ?? null)} />
              </div>
            </div>
            <div className="mt-7">
              <ProbChart points={points} />
            </div>
            <div className="mt-6 space-y-2.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>model vs. market</span>
                <span className="font-mono tabnum">{points.length} points</span>
              </div>
              <EdgeBar pMarket={market.probability} pModel={p?.p_model ?? null} />
            </div>
          </div>
        </div>
      </Reveal>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Reveal delay={0.1}>
          <SpotlightCard className="panel h-full" lift={false}>
            <div className="flex items-center justify-between border-b border-white/8 px-5 py-3">
              <span className="frame-label">signals for this market</span>
              {mine.length > 0 ? <LiveDot label="live" /> : null}
            </div>
            {mine.length === 0 ? (
              <div className="px-5 py-8 text-sm text-muted-foreground">
                No active signals for this market.
              </div>
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {mine.map((s) => (
                  <div key={s.id} className="flex items-center gap-3 px-5 py-3">
                    <span
                      className={cn(
                        "size-1.5 rounded-full",
                        s.type === "logical_constraint" ? "bg-amber" : "bg-white/60",
                      )}
                    />
                    <span className="w-24 text-xs text-muted-foreground">
                      {s.type === "logical_constraint" ? "logical" : "divergence"}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground/90">
                      {s.market_refs.join("  ·  ")}
                    </span>
                    <span className="font-mono text-xs tabnum text-amber">
                      {s.edge >= 0 ? "+" : ""}
                      {s.edge.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </SpotlightCard>
        </Reveal>

        <Reveal delay={0.14}>
          <SpotlightCard className="panel flex h-full flex-col gap-4 p-6">
            <span className="frame-label">details</span>
            <Detail label="Platform" value={market.platform} />
            <Detail label="Closes" value={fmtDate(market.close_time)} />
            <Detail
              label="24h volume"
              value={market.volume_24h != null ? Math.round(market.volume_24h).toLocaleString() : "—"}
            />
            <Detail
              label="Resolution"
              value={resolved ? (market.resolved_outcome === 1 ? "YES" : "NO") : "unresolved"}
            />
            <Detail label="Market id" value={market.market_id} mono />
          </SpotlightCard>
        </Reveal>
      </div>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-1 font-mono text-2xl font-semibold tabnum", accent ? "text-amber" : "text-foreground")}>
        {value}
      </div>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/[0.05] pb-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={cn("truncate text-sm text-foreground", mono && "font-mono text-xs")}>{value}</span>
    </div>
  );
}
