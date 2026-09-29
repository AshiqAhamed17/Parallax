import { MarketsExplorer } from "@/components/markets-explorer";
import { Reveal } from "@/components/reveal";
import { getMarkets } from "@/lib/api";
import type { Market } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function MarketsPage() {
  let markets: Market[] = [];
  try {
    markets = await getMarkets();
  } catch {
    // API unreachable — render the header with an empty explorer.
  }

  return (
    <div className="flex flex-col gap-10 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-3">
          <span className="eyebrow">markets</span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Every tracked market</h1>
          <p className="max-w-[62ch] text-muted-foreground">
            Live market-implied probability against the calibrated model, with edge and expected
            value. Search, sort, and filter the full set.
          </p>
        </header>
      </Reveal>
      <Reveal delay={0.08}>
        <MarketsExplorer markets={markets} />
      </Reveal>
    </div>
  );
}
