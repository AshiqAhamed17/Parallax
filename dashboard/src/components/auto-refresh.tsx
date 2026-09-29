"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// Re-runs server components on an interval so the dashboard's data feels live, without a full
// reload. Pauses while the tab is hidden.
export function AutoRefresh({ intervalMs = 30000 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") router.refresh();
    };
    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [router, intervalMs]);
  return null;
}
