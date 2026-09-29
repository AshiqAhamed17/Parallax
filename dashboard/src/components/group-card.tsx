import { fmtProb } from "@/lib/format";
import type { Group } from "@/lib/types";
import { cn } from "@/lib/utils";

// Visualizes a correlated-market group: the ladder of live probabilities and whether the provable
// ordering constraints currently hold.
export function GroupCard({ group }: { group: Group }) {
  const labelOf = (key: string) =>
    group.markets.find((m) => m.key === key)?.label ?? key;

  return (
    <div className="flex h-full flex-col gap-5 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          {group.category ? (
            <span className="rounded-md bg-white/[0.05] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {group.category}
            </span>
          ) : null}
          <span className="font-mono text-xs text-muted-foreground">{group.id}</span>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ring-1 ring-inset",
            group.consistent
              ? "bg-white/[0.04] text-muted-foreground ring-white/10"
              : "bg-crit/12 text-crit ring-crit/30",
          )}
        >
          <span className={cn("size-1.5 rounded-full", group.consistent ? "bg-amber" : "bg-crit")} />
          {group.consistent ? "consistent" : "violation"}
        </span>
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">{group.description}</p>

      {/* probability ladder */}
      <div className="flex flex-col gap-2.5">
        {group.markets.map((m) => {
          const pct = m.probability == null ? 0 : Math.round(m.probability * 100);
          return (
            <div key={m.key} className="flex items-center gap-3">
              <span className="w-40 shrink-0 truncate text-sm text-foreground">{m.label ?? m.key}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-amber/80" style={{ width: `${pct}%` }} />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-sm tabnum text-amber">
                {fmtProb(m.probability)}
              </span>
            </div>
          );
        })}
      </div>

      {/* constraints */}
      <div className="flex flex-col gap-2 border-t border-white/[0.06] pt-4">
        {group.constraints.map((c, i) => (
          <div key={i} className="flex items-center justify-between gap-3 text-sm">
            <span className="font-mono text-xs text-foreground/90">
              P({labelOf(c.lhs)}) {c.op} P({labelOf(c.rhs)})
            </span>
            {c.holds ? (
              <span className="font-mono text-xs text-muted-foreground">holds ✓</span>
            ) : (
              <span className="font-mono text-xs text-crit">
                violated by {c.gross_violation.toFixed(3)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
