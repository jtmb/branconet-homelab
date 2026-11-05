import { NextResponse } from "next/server";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";

export async function POST() {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  invalidateCache();
  return NextResponse.json({ ok: true, cacheInvalidated: true }, { headers: { "Cache-Control": "no-store" } });
}
