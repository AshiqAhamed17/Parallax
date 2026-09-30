import Link from "next/link";
import { LiveDot } from "@/components/live-dot";
import type { ArbitrageSignal } from "@/lib/types";
import { cn } from "@/lib/utils";

function label(t: ArbitrageSignal["type"]): string {
  return t === "logical_constraint" ? "logical" : "divergence";
}

// Compact live feed of the most recent signals from both detectors.
export function SignalStrip({ signals }: { signals: ArbitrageSignal[] }) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/80 px-4 py-2.5">
        <span className="frame-label">signal feed</span>
        <LiveDot label="live" />
      </div>
      <div className="flex-1 divide-y divide-border/60">
        {signals.length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">No signals in range.</div>
        ) : (
          signals.map((s) => {
            const logical = s.type === "logical_constraint";
            return (
              <div key={s.id} className="flex items-center gap-3 px-4 py-2.5">
                <span
                  className={cn("size-1.5 shrink-0 rounded-full", logical ? "bg-emerald" : "bg-mint")}
                  aria-hidden
                />
                <span className="w-20 shrink-0 text-xs text-muted-foreground">{label(s.type)}</span>
                <span className="min-w-0 flex-1 truncate text-xs text-foreground/90">
                  {s.market_refs.map((r) => s.labels?.[r] ?? (r.startsWith("0x") ? "Polymarket" : r)).join("  ·  ")}
                </span>
                <span className="shrink-0 font-mono text-xs tabnum text-mint">
                  {s.edge >= 0 ? "+" : ""}
                  {s.edge.toFixed(3)}
                </span>
              </div>
            );
          })
        )}
      </div>
      <Link
        href="/signals"
        className="border-t border-border/80 px-4 py-2.5 text-xs text-muted-foreground transition-colors hover:text-mint"
      >
        Open signal panel
      </Link>
    </div>
  );
}
