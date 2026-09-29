// Typed client for the Parallax read-only API. Server Components call these directly.
// Base URL from NEXT_PUBLIC_API_URL (default localhost:8000). Reads are never cached so the
// dashboard reflects the latest collector/demo data.

import type {
  Group,
  Market,
  PaginatedSignals,
  Replay,
  Report,
  SignalType,
} from "@/lib/types";

// 127.0.0.1 (not "localhost") so Node's server-side fetch doesn't resolve to IPv6 ::1 while the
// API listens on IPv4. In production NEXT_PUBLIC_API_URL points at the deployed API.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(res.status, path, `GET ${path} → ${res.status}`);
  }
  return (await res.json()) as T;
}

// Returns null on 404 instead of throwing — used for single-resource lookups.
async function requestOrNull<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new ApiError(res.status, path, `GET ${path} → ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getMarkets(): Promise<Market[]> {
  return request<Market[]>("/markets");
}

export function getMarket(id: string): Promise<Market | null> {
  return requestOrNull<Market>(`/markets/${encodeURIComponent(id)}`);
}

export function getReplay(id: string): Promise<Replay | null> {
  return requestOrNull<Replay>(`/markets/${encodeURIComponent(id)}/replay`);
}

export function getSignals(
  opts: { type?: SignalType; limit?: number; offset?: number } = {},
): Promise<PaginatedSignals> {
  const params = new URLSearchParams();
  if (opts.type) params.set("type", opts.type);
  if (opts.limit != null) params.set("limit", String(opts.limit));
  if (opts.offset != null) params.set("offset", String(opts.offset));
  const qs = params.toString();
  return request<PaginatedSignals>(`/arbitrage${qs ? `?${qs}` : ""}`);
}

export function getGroups(): Promise<Group[]> {
  return request<Group[]>("/groups");
}

export function getBenchmarks(): Promise<Report[]> {
  return request<Report[]>("/benchmarks");
}

export function getBacktests(): Promise<Report[]> {
  return request<Report[]>("/backtests");
}
