import Link from "next/link";

export default function MarketNotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
      <span className="eyebrow">404</span>
      <h1 className="text-3xl font-semibold tracking-tight">Market not found</h1>
      <p className="max-w-[42ch] text-muted-foreground">
        That market isn&rsquo;t tracked, or its id is wrong.
      </p>
      <Link
        href="/markets"
        className="mt-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
      >
        Back to markets
      </Link>
    </div>
  );
}
