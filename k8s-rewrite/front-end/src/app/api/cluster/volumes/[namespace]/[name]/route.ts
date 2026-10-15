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
        const data = await getCachedClusterData(["pvc"]);
        const unavailable = clusterUnavailable(data, "pvc");
        if (unavailable)
            return unavailable;
        const rawPvc = (data.rawPvcs || []).find((pvc: any) => pvc.metadata?.namespace === namespace && pvc.metadata?.name === name);
        if (!rawPvc) {
            return clusterMissing(data, "pvc", "PVC not found");
        }
        return clusterResponse(data, { pvc: rawPvc }, ["pvc"]);
    });
}
