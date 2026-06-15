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

  // If no live data, fall back to DB-only (shows provisioned nodes without status)
  if (!clusterData || !clusterData.nodes.length) {
    const fallback = dbNodes.length
      ? dbNodes.map((n) => ({
          id: n.id,
          hostname: n.hostname,
          ipAddress: n.ipAddress,
          role: n.role,
          status: n.status,
          cpu: n.cpu,
          memory: n.memory,
          k8sVersion: null,
          osImage: null,
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

    return {
      id: kn.metadata?.name || dbNode?.id || `node-${Math.random()}`,
      name: kn.metadata?.name || "unknown",
      hostname: kn.metadata?.name || "unknown",
      ipAddress:
        dbNode?.ipAddress ||
        kn.status?.addresses?.find((a: any) => a.type === "InternalIP")
          ?.address ||
        "unknown",
      role:
        dbNode?.role ||
        ("node-role.kubernetes.io/control-plane" in (kn.metadata?.labels || {})
          ? "master"
          : "worker"),
      status: ready ? "ready" : "not-ready",
      cpu: dbNode?.cpu || parseInt(kn.status?.capacity?.cpu) || null,
      memory:
        dbNode?.memory ||
        (kn.status?.capacity?.memory
          ? Math.round(
              parseInt(kn.status.capacity.memory) / (1024 * 1024)
            )
          : null),
      k8sVersion: kn.status?.nodeInfo?.kubeletVersion || null,
      osImage: kn.status?.nodeInfo?.osImage || null,
    };
  });

  return NextResponse.json({ nodes: liveNodes });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { hostname, ipAddress, role, status, cpu, memory } = body;

    if (!hostname || !ipAddress) {
      return NextResponse.json({ error: "hostname and ipAddress required" }, { status: 400 });
    }

    // Upsert: update if exists, create if not
    const node = await prisma.node.upsert({
      where: { hostname },
      update: { ipAddress, role: role || "master", status: status || "pending", cpu, memory },
      create: {
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