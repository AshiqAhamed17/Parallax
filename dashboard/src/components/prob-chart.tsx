// Probability-over-time area chart (absolute 0–100% scale so the level is meaningful).
// Pure SVG with CSS draw-in; reference lines at 25/50/75%.
export function ProbChart({
  points,
  height = 240,
  color = "var(--amber)",
}: {
  points: number[];
  height?: number;
  color?: string;
}) {
  const W = 1000; // viewBox width; SVG scales to container
  const padY = 12;
  const usable = height - padY * 2;
  const y = (p: number) => padY + (1 - Math.min(1, Math.max(0, p))) * usable;

  if (!points || points.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-white/8 text-sm text-muted-foreground"
        style={{ height }}
      >
        Not enough history to chart yet.
      </div>
    );
  }

  const stepX = W / (points.length - 1);
  const coords = points.map((p, i) => [i * stepX, y(p)] as const);
  const line = coords.map(([x, yy], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${yy.toFixed(1)}`).join(" ");
  const area = `${line} L${W},${height} L0,${height} Z`;
  const [lx, ly] = coords[coords.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" height={height} preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id="pc-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.26" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((g) => (
        <line
          key={g}
          x1={0}
          x2={W}
          y1={y(g)}
          y2={y(g)}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={1}
          strokeDasharray="2 5"
        />
      ))}
      <path d={area} fill="url(#pc-grad)" />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="spark-draw"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={lx} cy={ly} r={3.5} fill={color} />
    </svg>
  );
}
