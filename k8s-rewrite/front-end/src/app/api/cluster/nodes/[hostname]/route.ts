import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ hostname: string }> }
) {
  const { hostname } = await params;
  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ error: "Cluster data not available" }, { status: 503 });
  }

  const rawNode = (data.nodes || []).find(
    (n: any) => n.metadata?.name === hostname
  );

  if (!rawNode) {
    return NextResponse.json({ error: "Node not found" }, { status: 404 });
  }

  // Find pods running on this node
  const nodePods = (data.pods || []).filter(
    (p: any) => p.spec?.nodeName === hostname
  );

  return NextResponse.json({ node: rawNode, pods: nodePods });
}
