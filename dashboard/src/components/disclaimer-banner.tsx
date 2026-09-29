// Persistent, honest disclaimer shown on every route (constraint 2.1: Parallax never trades).
export function DisclaimerBanner() {
  return (
    <div className="w-full border-b border-border bg-surface-2/60 px-4 py-1.5 text-center text-xs text-muted-foreground">
      <span className="mr-1.5 inline-block size-1.5 translate-y-[-1px] rounded-full bg-med align-middle" aria-hidden />
      Informational only. Parallax observes prediction markets and never places orders. Figures are real Manifold market data, refreshed periodically.
    </div>
  );
}
