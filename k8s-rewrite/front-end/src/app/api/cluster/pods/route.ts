import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const typeFilter = searchParams.get("type");

  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ pods: [] });
  }

  // Namespaces that indicate system/infrastructure pods.
  // These auto-classify as "system" unless overridden by branconet.io/type label.
  const SYSTEM_NAMESPACES = new Set([
    "kube-system",
    "kube-public",
    "kube-node-lease",
    "calico-system",
    "calico-apiserver",
    "tigera-operator",
    "longhorn-system",
    "cert-manager",
    "metallb-system",
    "ingress-nginx",
    "flux-system",
    "traefik",
    "local-path-storage",
  ]);

  let pods = data.pods.map((p: any) => {
    const namespace = p.metadata?.namespace || "default";
    const name = p.metadata?.name || "unknown";
    const containerStatuses = p.status?.containerStatuses || [];
    const readyCount = containerStatuses.filter((c: any) => c.ready).length;
    const totalContainers = containerStatuses.length || (p.spec?.containers?.length) || 1;
    const restartCount = containerStatuses.reduce((sum: number, c: any) => sum + (c.restartCount || 0), 0);
    const images = p.spec?.containers?.map((c: any) => c.image).join(", ") || "-";
    const podIP = p.status?.podIP || "-";

    return {
      id: p.metadata?.uid || `${namespace}-${name}`,
      name,
      namespace,
      status: p.status?.phase || "Unknown",
      ready: `${readyCount}/${totalContainers}`,
      restarts: restartCount,
      image: images,
      ip: podIP,
      node: p.spec?.nodeName || "-",
      created: p.metadata?.creationTimestamp || null,
    };
  });

  return NextResponse.json({ pods });
}