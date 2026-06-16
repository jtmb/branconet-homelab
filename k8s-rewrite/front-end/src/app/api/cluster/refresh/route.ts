import { NextResponse } from "next/server";
import { invalidateCache, getCachedClusterData } from "@/lib/cluster-cache";

export async function POST() {
  // Invalidate the in-memory cluster cache so the next
  // polling interval refetches everything via SSH+kubectl.
  invalidateCache();

  // Prefetch to make the next page load instant
  try {
    await getCachedClusterData();
  } catch {
    // Best effort — the 10s poll will retry
  }

  return NextResponse.json({ ok: true });
}
