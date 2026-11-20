"use client";
import { QuerySnapshot } from "@/lib/query-store";

export function QueryStatus<T>({ query }: { query: QuerySnapshot<T> & { refetch: () => void } }) {
  const candidate = query.data && typeof query.data === "object" && "availability" in query.data ? query.data.availability : undefined;
  const availability = candidate && typeof candidate === "object" && "state" in candidate && typeof candidate.state === "string" ? { state: candidate.state } : undefined;
  const warning = query.error || (availability?.state && !["healthy", "empty"].includes(availability.state));
  if (!warning) return null;
  return <div role="status" className="mb-4 rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-sm text-amber-200">
    <p>{query.error ?? `Cluster data is ${availability?.state}. Some fields may be unavailable.`}
      {query.data && query.error ? " Showing the previous successful snapshot." : ""}</p>
    {query.updatedAt > 0 && <p className="text-xs mt-1">Last successful response: {new Date(query.updatedAt).toLocaleTimeString()}</p>}
    <button className="mt-2 underline" onClick={query.refetch} disabled={query.refreshing}>Retry</button>
  </div>;
}
