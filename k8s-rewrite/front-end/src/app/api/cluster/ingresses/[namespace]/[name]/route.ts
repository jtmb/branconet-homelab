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

  const rawIngress = (data.rawIngresses || []).find(
    (ing: any) =>
      ing.metadata?.namespace === namespace && ing.metadata?.name === name
  );

  if (!rawIngress) {
    return NextResponse.json({ error: "Ingress not found" }, { status: 404 });
  }

  return NextResponse.json({ ingress: rawIngress });
}
