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
        const data = await getCachedClusterData(["ingresses"]);
        const unavailable = clusterUnavailable(data, "ingresses");
        if (unavailable)
            return unavailable;
        const rawIngress = (data.rawIngresses || []).find((ing: any) => ing.metadata?.namespace === namespace && ing.metadata?.name === name);
        if (!rawIngress) {
            return clusterMissing(data, "ingresses", "Ingress not found");
        }
        return clusterResponse(data, { ingress: rawIngress }, ["ingresses"]);
    });
}
