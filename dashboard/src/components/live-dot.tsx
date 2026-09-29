import { cn } from "@/lib/utils";

// A pulsing cyan dot marking live/fresh data. The ping ring stops under prefers-reduced-motion
// (global CSS zeroes animation durations).
export function LiveDot({ label, className }: { label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald opacity-60" />
        <span className="relative inline-flex size-2 rounded-full bg-emerald" />
      </span>
      {label ? <span className="text-xs text-muted-foreground">{label}</span> : null}
    </span>
  );
}
