// Formatting helpers for market data. Every one returns an em dash for null/NaN so the UI never
// shows "NaN" or "undefined" when a market lacks a probability or prediction.

const DASH = "—";

function bad(n: number | null | undefined): boolean {
  return n == null || Number.isNaN(n);
}

/** Probability 0–1 → "64.2%". */
export function fmtProb(p: number | null | undefined): string {
  return bad(p) ? DASH : `${(p! * 100).toFixed(1)}%`;
}

/** Signed edge (model − market, a fraction) → "+4.3 pp" / "-1.2 pp" (percentage points). */
export function fmtEdge(e: number | null | undefined): string {
  if (bad(e)) return DASH;
  const pp = e! * 100;
  return `${pp >= 0 ? "+" : ""}${pp.toFixed(1)} pp`;
}

/** Signed expected value per unit stake → "+0.081" / "-0.030". */
export function fmtEv(e: number | null | undefined): string {
  if (bad(e)) return DASH;
  return `${e! >= 0 ? "+" : ""}${e!.toFixed(3)}`;
}

/** Epoch-nanoseconds → "2026-09-20 14:00 UTC". */
export function fmtTs(ns: number | null | undefined): string {
  if (bad(ns)) return DASH;
  const ms = ns! / 1_000_000;
  const iso = new Date(ms).toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

/** ISO date string → "Sep 20, 2026" (or the raw string if unparseable). */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
