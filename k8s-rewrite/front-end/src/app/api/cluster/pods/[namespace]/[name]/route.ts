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

  const rawPod = (data.pods || []).find(
    (p: any) =>
      p.metadata?.namespace === namespace && p.metadata?.name === name
  );

  if (!rawPod) {
    return NextResponse.json({ error: "Pod not found" }, { status: 404 });
  }

  return NextResponse.json({ pod: rawPod });
}
