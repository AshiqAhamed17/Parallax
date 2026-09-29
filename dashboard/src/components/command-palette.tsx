"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMarkets } from "@/lib/api";
import { fmtProb } from "@/lib/format";
import type { Market } from "@/lib/types";
import { cn } from "@/lib/utils";

// Global fuzzy search (⌘K / Ctrl-K) across markets. Fetches the market list lazily on first open.
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [markets, setMarkets] = useState<Market[]>([]);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    if (markets.length > 0) return;
    try {
      setMarkets(await getMarkets());
    } catch {
      // API unreachable — palette shows an empty state.
    }
  }, [markets.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("parallax:open-command", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("parallax:open-command", onOpen);
    };
  }, []);

  useEffect(() => {
    if (open) {
      load();
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    } else {
      setQuery("");
    }
  }, [open, load]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q ? markets.filter((m) => m.question_text.toLowerCase().includes(q)) : markets;
    return base.slice(0, 8);
  }, [query, markets]);

  const go = useCallback(
    (m: Market) => {
      setOpen(false);
      router.push(`/markets/${m.market_id}`);
    },
    [router],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 px-4 pt-[14vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="bezel w-full max-w-xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(results.length - 1, i + 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(0, i - 1));
          } else if (e.key === "Enter" && results[active]) {
            go(results[active]);
          }
        }}
      >
        <div className="bezel-core overflow-hidden">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            placeholder="Search markets…"
            className="w-full border-b border-white/[0.06] bg-transparent px-5 py-4 text-base text-foreground outline-none placeholder:text-muted-foreground"
          />
          <div className="max-h-80 overflow-y-auto p-2">
            {results.length === 0 ? (
              <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                {markets.length === 0 ? "Loading markets…" : "No markets match."}
              </div>
            ) : (
              results.map((m, i) => (
                <button
                  key={m.market_id}
                  type="button"
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(m)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
                    i === active ? "bg-white/[0.06]" : "hover:bg-white/[0.03]",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                    {m.question_text}
                  </span>
                  {m.category ? (
                    <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground">
                      {m.category}
                    </span>
                  ) : null}
                  <span className="w-14 shrink-0 text-right font-mono text-sm tabnum text-amber">
                    {fmtProb(m.probability)}
                  </span>
                </button>
              ))
            )}
          </div>
          <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2 font-mono text-[10px] text-muted-foreground">
            <span>↑↓ navigate · ↵ open</span>
            <span>esc to close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
