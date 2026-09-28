import { cn } from "@/lib/utils";

// Diverging glyph: market probability vs. model probability on a 0–100% track, with the span
// between them (the edge) highlighted. Cyan when the model is higher (positive edge), amber when
// lower. Guards null inputs with a muted placeholder — edge is undefined without both.
export function EdgeBar({
  pMarket,
  pModel,
  className,
}: {
  pMarket: number | null;
  pModel: number | null;
  className?: string;
}) {
  if (pMarket == null || pModel == null || Number.isNaN(pMarket) || Number.isNaN(pModel)) {
    return (
      <div className={cn("h-2 w-full rounded-full bg-surface-2", className)} aria-hidden />
    );
  }

  const market = Math.min(1, Math.max(0, pMarket));
  const model = Math.min(1, Math.max(0, pModel));
  const lo = Math.min(market, model);
  const hi = Math.max(market, model);
  const positive = model >= market;

  return (
    <div
      className={cn("relative h-2 w-full rounded-full bg-surface-2", className)}
      role="img"
      aria-label={`market ${(market * 100).toFixed(0)}%, model ${(model * 100).toFixed(0)}%`}
    >
      {/* edge span */}
      <div
        className={cn(
          "absolute top-0 h-full rounded-full",
          positive ? "bg-violet/60" : "bg-high/60",
        )}
        style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }}
      />
      {/* market marker */}
      <div
        className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-background bg-muted-foreground"
        style={{ left: `${market * 100}%` }}
      />
      {/* model marker */}
      <div
        className={cn(
          "absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-background",
          positive ? "bg-violet" : "bg-high",
        )}
        style={{ left: `${model * 100}%` }}
      />
    </div>
  );
}
