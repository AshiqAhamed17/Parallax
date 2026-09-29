"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  return (
    <header className="sticky top-4 z-40 px-4">
      {/* Floating glass island, detached from the top */}
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
                  active
                    ? "bg-white/10 text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-2 rounded-full bg-white/[0.04] px-3 py-1.5">
          <LiveDot label="live" />
        </div>
      </div>
    </header>
  );
}
