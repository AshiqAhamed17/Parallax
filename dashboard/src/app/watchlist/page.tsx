import { Reveal } from "@/components/reveal";
import { WatchlistView } from "@/components/watchlist-view";
import { getMarkets } from "@/lib/api";
import type { Market } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function WatchlistPage() {
  let markets: Market[] = [];
  try {
    markets = await getMarkets();
  } catch {
    // API unreachable
  }

  return (
    <div className="flex flex-col gap-8 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-3">
          <span className="eyebrow">watchlist</span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">My watchlist</h1>
          <p className="max-w-[62ch] text-muted-foreground">
            Markets you&rsquo;ve starred, saved in this browser only. No account, no sync — clear
            your site data and it resets.
          </p>
        </header>
      </Reveal>
      <Reveal delay={0.08}>
        <WatchlistView markets={markets} />
      </Reveal>
    </div>
  );
}
