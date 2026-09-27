"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

// A compact probability-over-time sparkline. Hand-rolled SVG so we control the path-draw animation
// and can guard degenerate inputs precisely.
export function Sparkline({
  points,
  width = 96,
  height = 28,
  className,
  color = "var(--accent-cyan)",
}: {
  points: number[];
  width?: number;
  height?: number;
  className?: string;
  color?: string;
}) {
  const reduce = useReducedMotion();
  const pad = 2;

  // Guard: fewer than two points (or a flat series) can't form a slope — draw a muted baseline,
  // never a NaN path.
  if (!points || points.length < 2) {
    return (
      <svg width={width} height={height} className={className} aria-hidden>
        <line
          x1={pad}
          y1={height / 2}
          x2={width - pad}
          y2={height / 2}
          stroke="var(--muted-foreground)"
          strokeOpacity={0.4}
          strokeWidth={1}
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1; // avoid divide-by-zero on a flat series
  const stepX = (width - pad * 2) / (points.length - 1);
  const d = points
    .map((p, i) => {
      const x = pad + i * stepX;
      const y = height - pad - ((p - min) / span) * (height - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      className={cn("overflow-visible", className)}
      aria-hidden
    >
      <motion.path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={reduce ? false : { pathLength: 0, opacity: 0.4 }}
        animate={reduce ? undefined : { pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.9, ease: "easeOut" }}
      />
    </svg>
  );
}
