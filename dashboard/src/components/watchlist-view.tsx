"use client";

import Link from "next/link";
import { EdgeBar } from "@/components/edge-bar";
import { Sparkline } from "@/components/sparkline";
import { WatchlistToggle } from "@/components/watchlist-toggle";
import { fmtEdge, fmtEv, fmtProb } from "@/lib/format";
import type { Market } from "@/lib/types";
import { useWatchlist } from "@/lib/watchlist";
import { cn } from "@/lib/utils";

// Filters the full market set to the browser-local watchlist. All client-side; no network on save.
export function WatchlistView({ markets }: { markets: Market[] }) {
  const ids = useWatchlist();
  const saved = markets.filter((m) => ids.includes(m.market_id));

  if (ids.length === 0) {
    return (
      <div className="panel px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Your watchlist is empty. Tap the star on any market to save it here — it stays in this
          browser, no account needed.
        </p>
        <Link
          href="/markets"
          className="mt-5 inline-flex rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
        >
          Browse markets
        </Link>
      </div>
    );
  }

  return (
    <div className="bezel">
      <div className="bezel-core divide-y divide-white/[0.05] overflow-hidden">
        {saved.map((m) => {
          const edge = m.prediction?.edge ?? null;
          return (
            <Link
              key={m.market_id}
              href={`/markets/${m.market_id}`}
              className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-3 transition-colors hover:bg-white/[0.03] md:grid-cols-[minmax(0,1fr)_5rem_7rem_5rem_6rem]"
            >
              <span className="flex min-w-0 items-center gap-1.5">
                <WatchlistToggle marketId={m.market_id} className="-ml-1 shrink-0" />
                <span className="truncate text-sm text-foreground">{m.question_text}</span>
              </span>
              <span className="text-right font-mono text-sm font-medium tabnum text-amber">
                {fmtProb(m.probability)}
              </span>
              <span className="hidden md:block">
                <EdgeBar pMarket={m.probability} pModel={m.prediction?.p_model ?? null} />
              </span>
              <span
                className={cn(
                  "hidden text-right font-mono text-xs tabnum md:block",
                  edge == null ? "text-muted-foreground" : edge >= 0 ? "text-amber" : "text-crit",
                )}
              >
                {fmtEdge(edge)}
              </span>
              <span className="hidden justify-self-end md:block">
                <Sparkline points={m.recent} width={80} height={24} />
              </span>
            </Link>
          );
        })}
        {saved.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-muted-foreground">
            None of your saved markets are currently tracked.
          </div>
        ) : null}
      </div>
    </div>
  );
}
