"use client";

import { toggle, useWatchlist } from "@/lib/watchlist";
import { cn } from "@/lib/utils";

// Star toggle, persisted to localStorage only (no network request, ever).
export function WatchlistToggle({ marketId, className }: { marketId: string; className?: string }) {
  const ids = useWatchlist();
  const saved = ids.includes(marketId);

  return (
    <button
      type="button"
      aria-label={saved ? "Remove from watchlist" : "Save to watchlist"}
      aria-pressed={saved}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle(marketId);
      }}
      className={cn(
        "grid size-7 place-items-center rounded-full transition-colors hover:bg-white/[0.06]",
        saved ? "text-amber" : "text-muted-foreground/50 hover:text-foreground",
        className,
      )}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill={saved ? "currentColor" : "none"} aria-hidden>
        <path
          d="M12 3.5l2.6 5.27 5.82.85-4.21 4.1.99 5.79L12 16.77l-5.2 2.73.99-5.79-4.21-4.1 5.82-.85z"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
