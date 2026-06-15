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
  ]);

  let pods = data.pods.map((p: any) => {
    const labels = p.metadata?.labels || {};
    const namespace = p.metadata?.namespace || "default";

    // Label takes priority; fallback to namespace-based detection
    let appType = labels["branconet.io/type"] || null;
    if (!appType) {
      appType = SYSTEM_NAMESPACES.has(namespace) ? "system" : "app";
    }

    return {
      id: p.metadata?.uid || `${namespace}-${p.metadata?.name}`,
      name: p.metadata?.name || "unknown",
      namespace,
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