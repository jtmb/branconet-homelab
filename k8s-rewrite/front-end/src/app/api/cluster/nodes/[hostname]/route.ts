import { validateNamespace, validateResourceName } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable, clusterMissing } from "@/lib/cluster-response";
import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET(_request: NextRequest, { params }: {
    params: Promise<{
        hostname: string;
    }>;
}) {
    return clusterRoute(async () => {
        const { hostname: rawHostname } = await params;
        const hostname = validateResourceName(rawHostname);
        const data = await getCachedClusterData(["nodes", "pods"]);
        const unavailable = clusterUnavailable(data, "nodes");
        if (unavailable)
            return unavailable;
        const rawNode = (data.nodes || []).find((n: any) => n.metadata?.name === hostname);
        if (!rawNode) {
            return clusterMissing(data, "nodes", "Node not found");
        }
        // Find pods running on this node
        const nodePods = (data.pods || []).filter((p: any) => p.spec?.nodeName === hostname);
        return clusterResponse(data, { node: rawNode, pods: nodePods }, ["nodes"]);
    });
}
