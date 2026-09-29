import Link from "next/link";
import { Reveal } from "@/components/reveal";
import { SignalCard } from "@/components/signal-card";
import { getSignals } from "@/lib/api";
import type { PaginatedSignals, SignalType } from "@/lib/types";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const LIMIT = 10;
const TABS: { key: "all" | SignalType; label: string }[] = [
  { key: "all", label: "All" },
  { key: "logical_constraint", label: "Logical-constraint" },
  { key: "cross_source_divergence", label: "Cross-source divergence" },
];

export default async function SignalsPage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string; offset?: string }>;
}) {
  const sp = await searchParams;
  const tab = TABS.find((t) => t.key === sp.type)?.key ?? "all";
  const offset = Math.max(0, Number(sp.offset ?? 0) || 0);
  const type = tab === "all" ? undefined : tab;

  let page: PaginatedSignals = { items: [], total: 0, limit: LIMIT, offset };
  try {
    page = await getSignals({ type, limit: LIMIT, offset });
  } catch {
    // API unreachable
  }

  const start = page.total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + LIMIT, page.total);
  const hasPrev = offset > 0;
  const hasNext = offset + LIMIT < page.total;
  const qs = (o: number) => `/signals?${type ? `type=${type}&` : ""}offset=${o}`;

  return (
    <div className="flex flex-col gap-8 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-3">
          <span className="eyebrow">signals</span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Where the market is wrong</h1>
          <p className="max-w-[64ch] text-muted-foreground">
            Provable logical-constraint violations and cross-source disagreements. These are
            informational signals about price consistency — market vs. independent forecast, not
            tradeable arbitrage. Parallax never trades.
          </p>
        </header>
      </Reveal>

      <Reveal delay={0.06}>
        <div className="flex flex-wrap items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1">
          {TABS.map((t) => (
            <Link
              key={t.key}
              href={t.key === "all" ? "/signals" : `/signals?type=${t.key}`}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm transition-colors",
                tab === t.key
                  ? "bg-primary/15 text-amber ring-1 ring-inset ring-primary/30"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </Link>
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <div className="flex flex-col gap-4">
          {page.items.length === 0 ? (
            <div className="panel px-6 py-16 text-center text-sm text-muted-foreground">
              No signals in this view.
            </div>
          ) : (
            page.items.map((s) => <SignalCard key={s.id} signal={s} />)
          )}
        </div>
      </Reveal>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="font-mono">
          {start}–{end} of {page.total}
        </span>
        <div className="flex gap-2">
          <PagerLink href={qs(offset - LIMIT)} disabled={!hasPrev}>
            Previous
          </PagerLink>
          <PagerLink href={qs(offset + LIMIT)} disabled={!hasNext}>
            Next
          </PagerLink>
        </div>
      </div>
    </div>
  );
}

function PagerLink({
  href,
  disabled,
  children,
}: {
  href: string;
  disabled: boolean;
  children: React.ReactNode;
}) {
  if (disabled) {
    return (
      <span className="cursor-not-allowed rounded-full border border-white/8 px-4 py-1.5 text-muted-foreground/40">
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className="rounded-full border border-white/12 px-4 py-1.5 text-foreground transition-colors hover:border-white/25 hover:bg-white/[0.03]"
    >
      {children}
    </Link>
  );
}
