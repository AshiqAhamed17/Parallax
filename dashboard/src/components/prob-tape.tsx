"use client";

import { useReducedMotion } from "motion/react";
import { fmtProb } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface TapeItem {
  question: string;
  probability: number | null;
}

// A scrolling monospace ticker of live market probabilities. Pauses on hover; static under
// reduced motion.
export function ProbTape({ items }: { items: TapeItem[] }) {
  const reduce = useReducedMotion();
  if (items.length === 0) return null;

  const row = (keyPrefix: string) =>
    items.map((it, i) => (
      <span key={`${keyPrefix}-${i}`} className="mx-5 inline-flex items-center gap-2">
        <span className="max-w-[22ch] truncate text-muted-foreground">{it.question}</span>
        <span className="font-mono tabnum text-iris">{fmtProb(it.probability)}</span>
      </span>
    ));

  return (
    <div className="group relative overflow-hidden border-y border-border bg-surface/60 py-2 text-sm">
      <div
        className={cn(
          "flex w-max whitespace-nowrap",
          reduce ? "" : "animate-[tape_40s_linear_infinite] group-hover:[animation-play-state:paused]",
        )}
      >
        {row("a")}
        {reduce ? null : row("b")}
      </div>
      <style>{`@keyframes tape { from { transform: translateX(0); } to { transform: translateX(-50%); } }`}</style>
    </div>
  );
}
