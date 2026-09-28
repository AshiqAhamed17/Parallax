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
    <header className="sticky top-0 z-40">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <Link href="/" className="shrink-0">
          <Wordmark />
        </Link>

        {/* floating pill nav */}
        <nav className="hidden items-center gap-1 rounded-full border border-border bg-surface/70 p-1 backdrop-blur-xl md:flex">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-full px-4 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-violet/15 text-foreground ring-1 ring-inset ring-violet/30"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 backdrop-blur-xl sm:flex">
          <LiveDot label="live" />
        </div>
      </div>
    </header>
  );
}
