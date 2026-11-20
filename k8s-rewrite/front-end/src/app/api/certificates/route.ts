import { NextResponse } from "next/server";
import { getSessionAccount } from "@/lib/auth";
import { kubectlJSON } from "@/lib/k8s";
import { certificateInventory } from "@/lib/certificate-inventory";
import { certificateControls } from "@/lib/certificate-control";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };

export async function GET() {
  if (!await getSessionAccount())
    return NextResponse.json({ error: "Authentication required" }, { status: 401, headers });
  try {
    const read = (args: readonly string[]) => kubectlJSON(args, 10000);
    const [report, controls] = await Promise.all([certificateInventory(read), certificateControls(read)]);
    return NextResponse.json({ ...report, controls }, { headers });
  } catch {
    return NextResponse.json({ error: "Certificate inventory unavailable" }, { status: 503, headers });
  }
}
