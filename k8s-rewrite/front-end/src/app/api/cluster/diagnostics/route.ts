import { NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { clusterDiagnostics } from "@/lib/cluster-cache";
import { kubectlDiagnostics } from "@/lib/k8s";

export async function GET() {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  return NextResponse.json({ resources: clusterDiagnostics(), commands: kubectlDiagnostics() }, { headers: { "Cache-Control": "no-store" } });
}
