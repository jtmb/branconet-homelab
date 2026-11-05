import { NextRequest, NextResponse } from "next/server";
import { getSessionAccount } from "@/lib/auth";
import { requireOperator } from "@/lib/permissions";
import { systemReports } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };
function failure(error: unknown) {
  // Global singleton survives route bundle duplication; do not depend on constructor identity.
  const known = error as { status?: number; message?: string };
  const status = known?.status && [409, 422, 501, 503].includes(known.status) ? known.status : 503;
  return NextResponse.json({ error: status === 503 ? "System report unavailable. Refresh inventory and try again." : known.message }, { status, headers });
}
export async function GET() {
  if (!await getSessionAccount()) return NextResponse.json({ error: "Authentication required" }, { status: 401, headers });
  try { return NextResponse.json(await systemReports.report(), { headers }); }
  catch (error) { return failure(error); }
}
export async function POST() {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  try { return NextResponse.json({ job: await systemReports.start() }, { status: 202, headers }); }
  catch (error) { return failure(error); }
}
export async function DELETE(request: NextRequest) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  try {
    const id = request.nextUrl.searchParams.get("jobId");
    if (!id || id.length > 100) return NextResponse.json({ error: "A current scan job ID is required" }, { status: 400, headers });
    systemReports.cancel(id);
    return NextResponse.json({ cancelling: true }, { status: 202, headers });
  } catch (error) { return failure(error); }
}
