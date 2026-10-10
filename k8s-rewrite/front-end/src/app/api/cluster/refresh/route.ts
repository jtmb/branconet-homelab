import { NextResponse } from "next/server";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireWrite } from "@/lib/permissions";

export async function POST() {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  invalidateCache();
  return NextResponse.json({ ok: true, cacheInvalidated: true }, { headers: { "Cache-Control": "no-store" } });
}
