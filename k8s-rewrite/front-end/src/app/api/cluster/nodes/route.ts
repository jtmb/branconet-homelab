import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET() {
  // Get live k8s node data via cache
  const clusterData = await getCachedClusterData();

  // Get DB node records for metadata (hostname, role, ipAddress)
  const dbNodes = await prisma.node.findMany({
    orderBy: { createdAt: "asc" },
  });

  // Helper: compute human-readable age from ISO timestamp
  function nodeAge(createdAt: string): string {
    const created = new Date(createdAt).getTime();
    const diff = Date.now() - created;
    const seconds = Math.floor(diff / 1000);
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

  // Index pods by node name for per-node pod counts
  const podsByNode = new Map<string, number>();
  if (clusterData?.pods) {
    for (const p of clusterData.pods) {
      const node = p.spec?.nodeName;
      if (node) podsByNode.set(node, (podsByNode.get(node) || 0) + 1);
    }
  }

  // If no live data, fall back to DB-only (shows provisioned nodes without status)
  if (!clusterData || !clusterData.nodes.length) {
    const fallback = dbNodes.length
      ? dbNodes.map((n) => ({
          id: n.id,
          name: n.name || n.hostname,
          hostname: n.hostname,
          ipAddress: n.ipAddress,
          role: n.role,
          status: n.status,
          cpu: n.cpu,
          memory: n.memory,
          k8sVersion: null,
          osImage: null,
          externalIp: null,
          pods: null,
          age: null,
        }))
      : [];
    return NextResponse.json({ nodes: fallback });
  }

  // Merge live k8s data with DB metadata
  const liveNodes = clusterData.nodes.map((kn: any) => {
    const dbNode = dbNodes.find(
      (n) => n.hostname === kn.metadata?.name
    );

    const conditions = kn.status?.conditions || [];
    const ready = conditions.find(
      (c: any) => c.type === "Ready" && c.status === "True"
    );

    const addresses = kn.status?.addresses || [];
    const internalIp = addresses.find((a: any) => a.type === "InternalIP")?.address || dbNode?.ipAddress || "unknown";
    const externalIp = addresses.find((a: any) => a.type === "ExternalIP")?.address || null;

    return {
      id: kn.metadata?.name || dbNode?.id || `node-${Math.random()}`,
      name: dbNode?.name || kn.metadata?.name || "unknown",
      hostname: kn.metadata?.name || "unknown",
      ipAddress: internalIp,
      externalIp,
      role: (() => {
        const roles: string[] = [];
        const labels = kn.metadata?.labels || {};
        if ("node-role.kubernetes.io/control-plane" in labels) roles.push("control-plane");
        if ("node-role.kubernetes.io/master" in labels) roles.push("master");
        if (!roles.length && dbNode?.role) roles.push(dbNode.role);
        if (!roles.length) roles.push("worker");
        return roles.join(",");
      })(),
      status: ready ? "ready" : "not-ready",
      cpu: parseInt(kn.status?.capacity?.cpu) || dbNode?.cpu || null,
      memory:
        (kn.status?.capacity?.memory
          ? Math.round(parseInt(kn.status.capacity.memory) / 1024 / 1024)
          : null) || dbNode?.memory || null,
      k8sVersion: kn.status?.nodeInfo?.kubeletVersion || null,
      osImage: kn.status?.nodeInfo?.osImage || null,
      pods: podsByNode.get(kn.metadata?.name) ?? 0,
      age: kn.metadata?.creationTimestamp ? nodeAge(kn.metadata.creationTimestamp) : null,
    };
  });

  return NextResponse.json({ nodes: liveNodes });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, hostname, ipAddress, role, status, cpu, memory } = body;

    if (!hostname || !ipAddress) {
      return NextResponse.json({ error: "hostname and ipAddress required" }, { status: 400 });
    }

    // Upsert: update if exists, create if not
    const node = await prisma.node.upsert({
      where: { hostname },
      update: { name: name || hostname, ipAddress, role: role || "master", status: status || "pending", cpu, memory },
      create: {
        name: name || hostname,
        hostname,
        ipAddress,
        role: role || "master",
        status: status || "pending",
        cpu: cpu || null,
        memory: memory || null,
      },
    });

    return NextResponse.json({ success: true, node }, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}