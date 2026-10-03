"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DocsToc, type TocItem } from "@/components/docs-toc";
import { adjacentDocs } from "@/lib/docs-nav";

// Wraps a single docs page: content column (title + prose) + an "on this page" rail, with a
// prev/next footer derived from the shared nav order.
export function DocPage({
  title,
  eyebrow,
  intro,
  toc = [],
  children,
}: {
  title: string;
  eyebrow?: string;
  intro?: string;
  toc?: TocItem[];
  children: ReactNode;
}) {
  const pathname = usePathname();
  const { prev, next } = adjacentDocs(pathname);

  return (
    <div className="flex w-full gap-10">
      <article className="doc-prose min-w-0 flex-1 pb-20">
        {eyebrow ? <div className="doc-eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {intro ? <p className="doc-lead">{intro}</p> : null}
        {children}

        <div className="mt-16 flex items-stretch justify-between gap-4 border-t border-border pt-6">
          {prev ? (
            <Link href={prev.href} className="doc-pager group">
              <span className="doc-pager-label">← Previous</span>
              <span className="doc-pager-title">{prev.title}</span>
            </Link>
          ) : (
            <span />
          )}
          {next ? (
            <Link href={next.href} className="doc-pager doc-pager-next group">
              <span className="doc-pager-label">Next →</span>
              <span className="doc-pager-title">{next.title}</span>
            </Link>
          ) : (
            <span />
          )}
        </div>
      </article>

      <aside className="hidden w-56 shrink-0 xl:block">
        <DocsToc items={toc} />
      </aside>
    </div>
  );
}
