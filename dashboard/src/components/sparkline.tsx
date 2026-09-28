import { cn } from "@/lib/utils";

// Probability-over-time sparkline. Pure SVG + CSS draw so it's always visible at rest (no JS/
// hydration dependency); the draw-in is a CSS enhancement. Optional gradient area fill for hero use.
export function Sparkline({
  points,
  width = 96,
  height = 28,
  className,
  color = "var(--iris)",
  fill = false,
}: {
  points: number[];
  width?: number;
  height?: number;
  className?: string;
  color?: string;
  fill?: boolean;
}) {
  const pad = 2;
  const gid = `sg-${Math.round(width)}x${Math.round(height)}-${points.length}`;

  if (!points || points.length < 2) {
    return (
      <svg width={width} height={height} className={className} aria-hidden>
        <line
          x1={pad}
          y1={height / 2}
          x2={width - pad}
          y2={height / 2}
          stroke="var(--muted-foreground)"
          strokeOpacity={0.35}
          strokeWidth={1}
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const stepX = (width - pad * 2) / (points.length - 1);
  const coords = points.map((p, i) => {
    const x = pad + i * stepX;
    const y = height - pad - ((p - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const line = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const area = `${line} L${coords[coords.length - 1][0].toFixed(2)},${height} L${coords[0][0].toFixed(2)},${height} Z`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <svg width={width} height={height} className={cn("overflow-visible", className)} aria-hidden>
      {fill ? (
        <>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill={`url(#${gid})`} stroke="none" />
        </>
      ) : null}
      <path
        d={line}
        pathLength={1}
        fill="none"
        stroke={color}
        strokeWidth={fill ? 2 : 1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="spark-draw"
      />
      <circle cx={lastX} cy={lastY} r={fill ? 2.4 : 1.6} fill={color} />
    </svg>
  );
}
