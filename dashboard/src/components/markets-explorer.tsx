"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { EdgeBar } from "@/components/edge-bar";
import { Sparkline } from "@/components/sparkline";
import { WatchlistToggle } from "@/components/watchlist-toggle";
import { fmtEdge, fmtEv, fmtProb } from "@/lib/format";
import type { Market } from "@/lib/types";
import { cn } from "@/lib/utils";

type Sort = "edge" | "prob" | "ev";
type Filter = "all" | "open" | "signals";

const SORTS: { key: Sort; label: string }[] = [
  { key: "edge", label: "Edge" },
  { key: "prob", label: "Probability" },
  { key: "ev", label: "EV" },
];
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "signals", label: "With edge" },
];

export function MarketsExplorer({ markets }: { markets: Market[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("edge");
  const [filter, setFilter] = useState<Filter>("all");

  const rows = useMemo(() => {
    let r = markets;
    if (query.trim()) {
      const q = query.toLowerCase();
      r = r.filter((m) => m.question_text.toLowerCase().includes(q));
    }
    if (filter === "open") r = r.filter((m) => m.resolved_outcome == null);
    if (filter === "signals") r = r.filter((m) => m.prediction != null && m.prediction.edge !== 0);
    const val = (m: Market) =>
      sort === "prob"
        ? (m.probability ?? -1)
        : sort === "ev"
          ? (m.prediction?.ev ?? -Infinity)
          : Math.abs(m.prediction?.edge ?? -1);
    return [...r].sort((a, b) => val(b) - val(a));
  }, [markets, query, sort, filter]);

  return (
    <div className="flex flex-col gap-4">
      {/* toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search markets…"
            className="w-full rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-white/25"
          />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <PillGroup label="Sort">
            {SORTS.map((s) => (
              <Pill key={s.key} active={sort === s.key} onClick={() => setSort(s.key)}>
                {s.label}
              </Pill>
            ))}
          </PillGroup>
          <PillGroup label="Show">
            {FILTERS.map((f) => (
              <Pill key={f.key} active={filter === f.key} onClick={() => setFilter(f.key)}>
                {f.label}
              </Pill>
            ))}
          </PillGroup>
        </div>
      </div>

      <div className="bezel">
        <div className="bezel-core overflow-hidden">
          <div className="hidden grid-cols-[minmax(0,1fr)_5rem_7rem_5rem_5rem_6rem] items-center gap-4 px-5 py-3 text-[11px] text-muted-foreground md:grid">
            <span>Market</span>
            <span className="text-right">Prob</span>
            <span>Model vs mkt</span>
            <span className="text-right">Edge</span>
            <span className="text-right">EV</span>
            <span className="text-right">Recent</span>
          </div>
          <div className="divide-y divide-white/[0.05]">
            {rows.map((m) => {
              const edge = m.prediction?.edge ?? null;
              const dot = edge == null ? "bg-muted-foreground/40" : edge >= 0 ? "bg-amber" : "bg-crit";
              return (
                <Link
                  key={m.market_id}
                  href={`/markets/${m.market_id}`}
                  className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-3 transition-colors hover:bg-white/[0.03] md:grid-cols-[minmax(0,1fr)_5rem_7rem_5rem_5rem_6rem]"
                >
                  <span className="flex min-w-0 items-center gap-1.5">
                    <WatchlistToggle marketId={m.market_id} className="-ml-1 shrink-0" />
                    <span className={cn("size-1.5 shrink-0 rounded-full", dot)} aria-hidden />
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
                  <span className="hidden text-right font-mono text-xs tabnum text-muted-foreground md:block">
                    {fmtEv(m.prediction?.ev ?? null)}
                  </span>
                  <span className="hidden justify-self-end md:block">
                    <Sparkline points={m.recent} width={80} height={24} />
                  </span>
                </Link>
              );
            })}
            {rows.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                No markets match “{query}”.
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {rows.length} of {markets.length} markets
      </p>
    </div>
  );
}

function PillGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="eyebrow">{label}</span>
      <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1">
        {children}
      </div>
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1 text-xs transition-colors",
        active ? "bg-primary/15 text-amber ring-1 ring-inset ring-primary/30" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
