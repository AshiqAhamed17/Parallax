"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LiveDot } from "@/components/live-dot";
import { Wordmark } from "@/components/wordmark";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/markets", label: "Markets" },
  { href: "/signals", label: "Signals" },
  { href: "/performance", label: "Performance" },
  { href: "/watchlist", label: "Watchlist" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function TopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false); // close menu on route change
  }, [pathname]);

  return (
    <header className="sticky top-4 z-40 px-4">
      <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3 rounded-full border border-white/10 bg-black/40 py-2 pl-4 pr-2 backdrop-blur-2xl">
        <Link href="/" className="shrink-0 pl-1">
          <Wordmark />
        </Link>

        <nav className="hidden items-center gap-0.5 md:flex">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-full px-3.5 py-1.5 text-sm transition-colors duration-300",
                  active ? "bg-white/10 text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 rounded-full bg-white/[0.04] px-3 py-1.5 sm:flex">
            <LiveDot label="live" />
          </div>
          {/* mobile menu button */}
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="grid size-9 place-items-center rounded-full bg-white/[0.05] text-foreground md:hidden"
          >
            <span className="relative block h-3 w-4">
              <span className={cn("absolute left-0 top-0 h-0.5 w-4 bg-current transition-transform duration-300", open && "top-1.5 rotate-45")} />
              <span className={cn("absolute left-0 top-1.5 h-0.5 w-4 bg-current transition-opacity duration-200", open && "opacity-0")} />
              <span className={cn("absolute left-0 top-3 h-0.5 w-4 bg-current transition-transform duration-300", open && "top-1.5 -rotate-45")} />
            </span>
          </button>
        </div>
      </div>

      {/* mobile dropdown */}
      {open ? (
        <div className="mx-auto mt-2 flex w-full max-w-4xl flex-col gap-1 rounded-3xl border border-white/10 bg-black/70 p-3 backdrop-blur-2xl md:hidden">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-2xl px-4 py-2.5 text-sm transition-colors",
                  active ? "bg-white/10 text-foreground" : "text-muted-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </div>
      ) : null}
    </header>
  );
}
