import type { Metadata } from "next";
import type { ReactNode } from "react";
import { DocsSidebar } from "@/components/docs-sidebar";

export const metadata: Metadata = {
  title: "Docs",
  description:
    "Technical documentation for Parallax — architecture, the data pipeline, the calibration model, signal detectors, and the read-only API.",
};

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="lg:grid lg:grid-cols-[15rem_1fr] lg:gap-10">
      {/* Desktop sidebar */}
      <aside className="hidden lg:block">
        <div className="sticky top-28 max-h-[calc(100vh-8rem)] overflow-y-auto pr-2">
          <DocsSidebar />
        </div>
      </aside>

      {/* Mobile sidebar — pure-HTML disclosure, no JS */}
      <details className="mb-8 rounded-xl border border-border bg-surface/60 p-4 lg:hidden">
        <summary className="cursor-pointer text-sm font-medium text-foreground">
          Documentation menu
        </summary>
        <div className="mt-4">
          <DocsSidebar />
        </div>
      </details>

      <main className="min-w-0">{children}</main>
    </div>
  );
}
