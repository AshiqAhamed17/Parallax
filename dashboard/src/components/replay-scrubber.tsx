"use client";

import { useEffect, useRef, useState } from "react";
import { ProbChart } from "@/components/prob-chart";
import { fmtProb } from "@/lib/format";

// Scrubs a market's stored probability history: drag the slider or press play to replay the curve
// forming over time. Autoplay is disabled under prefers-reduced-motion (manual scrub still works).
export function ReplayScrubber({ points }: { points: number[] }) {
  const n = points.length;
  const [i, setI] = useState(Math.max(0, n - 1));
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setPlaying(false);
      return;
    }
    let last = performance.now();
    const stepEvery = Math.max(24, 2400 / Math.max(1, n)); // ~2.4s full sweep
    const tick = (now: number) => {
      if (now - last >= stepEvery) {
        last = now;
        setI((prev) => {
          if (prev >= n - 1) {
            setPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [playing, n]);

  if (n < 2) {
    return <ProbChart points={points} />;
  }

  const play = () => {
    if (i >= n - 1) setI(0);
    setPlaying(true);
  };

  return (
    <div>
      <ProbChart points={points.slice(0, i + 1)} />
      <div className="mt-5 flex items-center gap-4">
        <button
          type="button"
          onClick={() => (playing ? setPlaying(false) : play())}
          aria-label={playing ? "Pause replay" : "Play replay"}
          className="grid size-9 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition-transform active:scale-95"
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden>
              <rect x="3" y="2.5" width="3" height="9" rx="1" />
              <rect x="8" y="2.5" width="3" height="9" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden>
              <path d="M4 2.5l7 4.5-7 4.5z" />
            </svg>
          )}
        </button>
        <input
          type="range"
          min={0}
          max={n - 1}
          value={i}
          onChange={(e) => {
            setPlaying(false);
            setI(Number(e.target.value));
          }}
          aria-label="Scrub probability history"
          className="scrubber h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10"
        />
        <div className="shrink-0 text-right">
          <div className="font-mono text-sm font-medium tabnum text-amber">{fmtProb(points[i])}</div>
          <div className="font-mono text-[10px] text-muted-foreground">
            {i + 1}/{n}
          </div>
        </div>
      </div>
    </div>
  );
}
