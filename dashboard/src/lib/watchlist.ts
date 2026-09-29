"use client";

import { useEffect, useState } from "react";

// Browser-local watchlist. localStorage only — no backend, no network, no account.

const KEY = "parallax:watchlist";
const listeners = new Set<() => void>();

function read(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  window.localStorage.setItem(KEY, JSON.stringify(ids));
  listeners.forEach((l) => l());
}

export function toggle(id: string): void {
  const set = new Set(read());
  if (set.has(id)) set.delete(id);
  else set.add(id);
  write([...set]);
}

export function isSaved(id: string): boolean {
  return read().includes(id);
}

// Subscribes to watchlist changes (this tab + other tabs). Starts empty for SSR-safe hydration.
export function useWatchlist(): string[] {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const update = () => setIds(read());
    update();
    listeners.add(update);
    window.addEventListener("storage", update);
    return () => {
      listeners.delete(update);
      window.removeEventListener("storage", update);
    };
  }, []);
  return ids;
}
