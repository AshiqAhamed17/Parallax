import { fmtDate } from "@/lib/format";
import type { ArbitrageSignal } from "@/lib/types";
import { cn } from "@/lib/utils";

const HIDE_KEYS = new Set(["note"]);

// A signal from either detector, with its detail payload rendered as key/value chips.
export function SignalCard({ signal }: { signal: ArbitrageSignal }) {
  const logical = signal.type === "logical_constraint";
  const note = typeof signal.details.note === "string" ? signal.details.note : null;
  const entries = Object.entries(signal.details).filter(([k]) => !HIDE_KEYS.has(k));

  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <span className={cn("size-2 rounded-full", logical ? "bg-amber" : "bg-white/70")} aria-hidden />
          <span className="text-sm font-medium text-foreground">
            {logical ? "Logical-constraint" : "Cross-source divergence"}
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {signal.market_refs.join("  ·  ")}
          </span>
        </div>
        <span className="shrink-0 font-mono text-lg font-semibold tabnum text-amber">
          {signal.edge >= 0 ? "+" : ""}
          {signal.edge.toFixed(3)}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-2">
            <span className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</span>
            <span className="font-mono text-xs tabnum text-foreground/90">
              {typeof v === "number" ? v.toFixed(3) : String(v)}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-white/[0.05] pt-3 text-xs text-muted-foreground">
        <span>{note ?? "informational signal"}</span>
        <span className="font-mono">{fmtDate(signal.detected_at)}</span>
      </div>
    </div>
  );
}
