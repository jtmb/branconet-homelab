import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const { namespace, name } = await params;
  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ error: "Cluster data not available" }, { status: 503 });
  }

  const rawPvc = (data.rawPvcs || []).find(
    (pvc: any) =>
      pvc.metadata?.namespace === namespace && pvc.metadata?.name === name
  );

  if (!rawPvc) {
    return NextResponse.json({ error: "PVC not found" }, { status: 404 });
  }

  return NextResponse.json({ pvc: rawPvc });
}
