"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOCS_NAV } from "@/lib/docs-nav";
import { cn } from "@/lib/utils";

// Persistent left-hand docs navigation (GitBook-style), grouped, with active-link highlighting.
export function DocsSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-7">
      {DOCS_NAV.map((group) => (
        <div key={group.group} className="flex flex-col gap-1.5">
          <div className="px-3 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/70">
            {group.group}
          </div>
          {group.links.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm transition-colors duration-200",
                  active
                    ? "bg-amber/10 font-medium text-foreground ring-1 ring-inset ring-amber/20"
                    : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground",
                )}
              >
                {link.title}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
