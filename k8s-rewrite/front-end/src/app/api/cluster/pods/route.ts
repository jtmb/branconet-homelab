import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const typeFilter = searchParams.get("type");

  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ pods: [] });
  }

  let pods = data.pods.map((p: any) => {
    const labels = p.metadata?.labels || {};
    const appType = labels["branconet.io/type"] || null;

    return {
      id: p.metadata?.uid || `${p.metadata?.namespace}-${p.metadata?.name}`,
      name: p.metadata?.name || "unknown",
      namespace: p.metadata?.namespace || "default",
      status: p.status?.phase || "Unknown",
      phase: p.status?.containerStatuses?.[0]?.state
        ? Object.keys(p.status.containerStatuses[0].state)[0]
        : undefined,
      reason: p.status?.reason,
      message: p.status?.message,
      node: p.spec?.nodeName || "-",
      appType,
    };
  });

  // Filter by type if requested
  if (typeFilter === "system") {
    pods = pods.filter((p) => p.appType === "system");
  } else if (typeFilter === "app") {
    pods = pods.filter((p) => p.appType === "app");
  }
  // "all" or no filter returns everything

  return NextResponse.json({ pods });
}