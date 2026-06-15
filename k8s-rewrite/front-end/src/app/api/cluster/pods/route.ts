import { NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET() {
  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ pods: [] });
  }

  const pods = data.pods.map((p: any) => ({
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
  }));

  return NextResponse.json({ pods });
}