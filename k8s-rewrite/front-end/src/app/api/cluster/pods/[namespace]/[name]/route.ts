import { validateNamespace, validateResourceName } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable, clusterMissing } from "@/lib/cluster-response";
import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET(_request: NextRequest, { params }: {
    params: Promise<{
        namespace: string;
        name: string;
    }>;
}) {
    return clusterRoute(async () => {
        const { namespace: rawNamespace, name: rawName } = await params;
        const namespace = validateNamespace(rawNamespace), name = validateResourceName(rawName);
        const data = await getCachedClusterData(["pods"]);
        const unavailable = clusterUnavailable(data, "pods");
        if (unavailable)
            return unavailable;
        const rawPod = (data.pods || []).find((p: any) => p.metadata?.namespace === namespace && p.metadata?.name === name);
        if (!rawPod) {
            return clusterMissing(data, "pods", "Pod not found");
        }
        return clusterResponse(data, { pod: rawPod }, ["pods"]);
    });
}
