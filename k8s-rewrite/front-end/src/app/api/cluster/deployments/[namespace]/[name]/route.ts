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

  const rawDeploy = (data.rawDeployments || []).find(
    (d: any) =>
      d.metadata?.namespace === namespace && d.metadata?.name === name
  );

  if (!rawDeploy) {
    return NextResponse.json({ error: "Deployment not found" }, { status: 404 });
  }

  // Find pods owned by this deployment via matchLabels
  const selector = rawDeploy.spec?.selector?.matchLabels || {};
  const selectorKeys = Object.keys(selector);
  const pods = (data.pods || []).filter((p: any) => {
    if (p.metadata?.namespace !== namespace) return false;
    const labels = p.metadata?.labels || {};
    return selectorKeys.every((k) => labels[k] === selector[k]);
  });

  return NextResponse.json({ deployment: rawDeploy, pods });
}
