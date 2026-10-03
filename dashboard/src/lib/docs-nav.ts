// Single source of truth for the /docs navigation — used by the sidebar and the prev/next footer.

export type DocLink = { href: string; title: string };
export type DocGroup = { group: string; links: DocLink[] };

export const DOCS_NAV: DocGroup[] = [
  {
    group: "Getting started",
    links: [
      { href: "/docs", title: "Introduction" },
      { href: "/docs/architecture", title: "Architecture" },
    ],
  },
  {
    group: "How it works",
    links: [
      { href: "/docs/data-pipeline", title: "Data pipeline" },
      { href: "/docs/model", title: "The model" },
      { href: "/docs/signals", title: "Signals" },
    ],
  },
  {
    group: "Reference",
    links: [
      { href: "/docs/api", title: "API reference" },
      { href: "/docs/running", title: "Running it" },
      { href: "/docs/tech-stack", title: "Tech stack" },
    ],
  },
];

// Flattened, in reading order — for prev/next.
export const DOCS_ORDER: DocLink[] = DOCS_NAV.flatMap((g) => g.links);

export function adjacentDocs(pathname: string): { prev: DocLink | null; next: DocLink | null } {
  const i = DOCS_ORDER.findIndex((l) => l.href === pathname);
  if (i === -1) return { prev: null, next: null };
  return {
    prev: i > 0 ? DOCS_ORDER[i - 1] : null,
    next: i < DOCS_ORDER.length - 1 ? DOCS_ORDER[i + 1] : null,
  };
}
