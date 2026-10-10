"use client";
import { QuerySnapshot } from "@/lib/query-store";

export function QueryStatus({ query }: { query: QuerySnapshot<{ availability?: { state?: string } }> & { refetch: () => void } }) {
  const availability = query.data?.availability;
  const warning = query.error || (availability?.state && !["healthy", "empty"].includes(availability.state));
  if (!warning) return null;
  return <div role="status" className="mb-4 rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-sm text-amber-200">
    <p>{query.error ?? `Cluster data is ${availability?.state}. Some fields may be unavailable.`}
      {query.data && query.error ? " Showing the previous successful snapshot." : ""}</p>
    {query.updatedAt > 0 && <p className="text-xs mt-1">Last successful response: {new Date(query.updatedAt).toLocaleTimeString()}</p>}
    <button className="mt-2 underline" onClick={query.refetch} disabled={query.refreshing}>Retry</button>
  </div>;
}
