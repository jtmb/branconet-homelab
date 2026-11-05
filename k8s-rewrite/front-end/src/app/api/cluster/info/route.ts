import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable } from "@/lib/cluster-response";
import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET() {
    return clusterRoute(async () => {
        // Check DB for stale cluster records (even if live cluster is dead)
        const [state, nodeCount, fluxRepos] = await Promise.all([
            prisma.clusterState.findFirst({ where: { deployed: true } }),
            prisma.node.count(),
            prisma.gitRepo.count(),
        ]);
        const hasDbCluster = !!state || nodeCount > 0;
        const data = await getCachedClusterData(["nodes", "pods", "longhorn"]);
        const unavailable = clusterUnavailable(data, "nodes");
        if (unavailable)
            return unavailable;
        return clusterResponse(data, { ...data.info, hasDbCluster, fluxRepos }, ["nodes"]);
    });
}
