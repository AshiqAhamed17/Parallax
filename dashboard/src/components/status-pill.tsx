import { cn } from "@/lib/utils";

export type Status = "crit" | "high" | "med" | "low" | "ok" | "neutral";

// Dot + text. Status is never conveyed by color alone — the label is always present.
const STYLES: Record<Status, { dot: string; text: string; ring: string }> = {
  crit: { dot: "bg-crit", text: "text-crit", ring: "ring-crit/30" },
  high: { dot: "bg-high", text: "text-high", ring: "ring-high/30" },
  med: { dot: "bg-med", text: "text-med", ring: "ring-med/30" },
  low: { dot: "bg-low", text: "text-low", ring: "ring-low/30" },
  ok: { dot: "bg-ok", text: "text-ok", ring: "ring-ok/30" },
  neutral: { dot: "bg-muted-foreground", text: "text-muted-foreground", ring: "ring-border" },
};

export function StatusPill({
  status,
  label,
  className,
}: {
  status: Status;
  label: string;
  className?: string;
}) {
  const s = STYLES[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        s.text,
        s.ring,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", s.dot)} aria-hidden />
      {label}
    </span>
  );
}
