import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// CSS-based entrance so content is ALWAYS visible at rest (animation-fill-mode: both), even if JS
// hasn't hydrated. Under prefers-reduced-motion the global rule zeroes the duration → instant.
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <div className={cn("reveal", className)} style={{ animationDelay: `${delay}s` }}>
      {children}
    </div>
  );
}
