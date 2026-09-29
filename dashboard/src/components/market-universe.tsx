"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export type UniverseSlice = { label: string; count: number };

// Animated breakdown of tracked markets by category. Bars grow from zero and counts tick up when
// the panel scrolls into view — makes the breadth of coverage (crypto, sports, macro, politics…)
// legible at a glance. Static under reduced motion.
export function MarketUniverse({ slices, total }: { slices: UniverseSlice[]; total: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  const max = Math.max(1, ...slices.map((s) => s.count));

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={ref} className="bezel">
      <div className="bezel-core p-7 sm:p-9">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="eyebrow">market universe</span>
            <h3 className="text-2xl font-semibold tracking-tight text-foreground">
              {slices.length} categories, one pipeline
            </h3>
          </div>
          <Link
            href="/markets"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Browse all {total} →
          </Link>
        </div>

        <div className="mt-8 grid gap-x-10 gap-y-4 sm:grid-cols-2">
          {slices.map((s, i) => {
            const pct = (s.count / max) * 100;
            return (
              <div key={s.label} className="flex items-center gap-4">
                <span className="w-20 shrink-0 truncate text-sm text-foreground">{s.label}</span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                  <div
                    className={cn(
                      "absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-amber to-amber-bright transition-[width] duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
                    )}
                    style={{
                      width: shown ? `${pct}%` : "0%",
                      transitionDelay: `${i * 55}ms`,
                    }}
                  />
                </div>
                <span className="w-6 shrink-0 text-right font-mono text-sm tabnum text-muted-foreground">
                  {s.count}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
