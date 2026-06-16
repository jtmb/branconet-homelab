import { NextResponse } from "next/server";
import { invalidateCache, getCachedClusterData } from "@/lib/cluster-cache";
import { requireWrite } from "@/lib/permissions";

export async function POST() {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
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
