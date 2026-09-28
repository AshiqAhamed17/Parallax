import { cn } from "@/lib/utils";

// Two offset bars = the same event priced twice (the parallax idea). Cyan + sky, horizontally shifted.
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="relative flex h-4 w-4 items-end gap-[3px]" aria-hidden>
        <span className="h-3 w-[3px] rounded-full bg-violet" />
        <span className="h-4 w-[3px] translate-y-[-2px] rounded-full bg-iris" />
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-foreground">Parallax</span>
    </span>
  );
}
