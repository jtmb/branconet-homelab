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
        const data = await getCachedClusterData(["services"]);
        const unavailable = clusterUnavailable(data, "services");
        if (unavailable)
            return unavailable;
        const rawService = (data.rawServices || []).find((svc: any) => svc.metadata?.namespace === namespace && svc.metadata?.name === name);
        if (!rawService) {
            return clusterMissing(data, "services", "Service not found");
        }
        return clusterResponse(data, { service: rawService }, ["services"]);
    });
}
