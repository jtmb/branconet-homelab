import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireWrite } from "@/lib/permissions";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { name } = await params;
  const result = await kubectlExec(`delete namespace ${name} --wait=false`, 15000);
  if (result === null) {
    return NextResponse.json({ error: "Delete failed" }, { status: 500 });
  }
  invalidateCache();
  return NextResponse.json({ success: true });
}
