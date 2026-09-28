import Link from "next/link";
import { EdgeBar } from "@/components/edge-bar";
import { LiveDot } from "@/components/live-dot";
import { Sparkline } from "@/components/sparkline";
import { fmtEdge, fmtEv, fmtProb } from "@/lib/format";
import type { Market } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface TerminalRow {
  market: Market;
  points: number[];
}

// The product-as-hero: a dense, live "terminal" of tracked markets. Monospace data, edge bars,
// sparklines. Every row links to its market.
export function MarketTerminal({ rows }: { rows: TerminalRow[] }) {
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/80 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex gap-1.5" aria-hidden>
            <span className="size-2.5 rounded-full bg-crit/70" />
            <span className="size-2.5 rounded-full bg-med/70" />
            <span className="size-2.5 rounded-full bg-ok/70" />
          </span>
          <span className="frame-label ml-1">parallax // live markets</span>
        </div>
        <LiveDot label={`${rows.length} tracked`} />
      </div>

      {/* column header */}
      <div className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-2 text-[11px] text-muted-foreground md:grid-cols-[minmax(0,1fr)_5rem_6rem_5rem_5rem_6rem]">
        <span>Market</span>
        <span className="text-right">Prob</span>
        <span className="hidden md:block">Model vs mkt</span>
        <span className="hidden text-right md:block">Edge</span>
        <span className="hidden text-right md:block">EV</span>
        <span className="hidden text-right md:block">30-pt</span>
      </div>

      <div className="divide-y divide-border/60">
        {rows.map(({ market: m, points }) => {
          const edge = m.prediction?.edge ?? null;
          const dot =
            edge == null ? "bg-muted-foreground/40" : edge >= 0 ? "bg-ok" : "bg-high";
          return (
            <Link
              key={m.market_id}
              href={`/markets/${m.market_id}`}
              className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-2.5 transition-colors hover:bg-violet/[0.04] md:grid-cols-[minmax(0,1fr)_5rem_6rem_5rem_5rem_6rem]"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <span className={cn("size-1.5 shrink-0 rounded-full", dot)} aria-hidden />
                <span className="truncate text-sm text-foreground">{m.question_text}</span>
              </span>
              <span className="text-right font-mono text-sm font-medium tabnum text-iris">
                {fmtProb(m.probability)}
              </span>
              <span className="hidden md:block">
                <EdgeBar pMarket={m.probability} pModel={m.prediction?.p_model ?? null} />
              </span>
              <span
                className={cn(
                  "hidden text-right font-mono text-xs tabnum md:block",
                  edge == null ? "text-muted-foreground" : edge >= 0 ? "text-ok" : "text-high",
                )}
              >
                {fmtEdge(edge)}
              </span>
              <span className="hidden text-right font-mono text-xs tabnum text-muted-foreground md:block">
                {fmtEv(m.prediction?.ev ?? null)}
              </span>
              <span className="hidden justify-self-end md:block">
                <Sparkline points={points} width={72} height={22} />
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
