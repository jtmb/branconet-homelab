import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name } = await params;
  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ error: "Cluster data not available" }, { status: 503 });
  }

  const rawNs = (data.rawNamespaces || []).find(
    (ns: any) => ns.metadata?.name === name
  );

  if (!rawNs) {
    return NextResponse.json({ error: "Namespace not found" }, { status: 404 });
  }

  const now = Date.now();
  const created = rawNs.metadata?.creationTimestamp;
  const age = created ? formatAge(now - new Date(created).getTime()) : "-";

  // Filter all resources in this namespace
  const nsPods = (data.pods || []).filter(
    (p: any) => p.metadata?.namespace === name
  );
  const nsDeployments = data.deployments.filter(
    (d: any) => d.namespace === name
  );
  const nsServices = data.services.filter(
    (s: any) => s.namespace === name
  );

  return NextResponse.json({
    namespace: {
      name: rawNs.metadata?.name || "unknown",
      status: rawNs.status?.phase || "Active",
      age,
    },
    pods: nsPods,
    deployments: nsDeployments,
    services: nsServices,
  });
}

function formatAge(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 365) return `${days}d`;
  const years = Math.floor(days / 365);
  return `${years}y`;
}
