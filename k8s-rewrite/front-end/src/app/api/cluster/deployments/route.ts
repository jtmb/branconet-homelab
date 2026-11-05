import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable } from "@/lib/cluster-response";
import { NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET() {
    return clusterRoute(async () => {
        const data = await getCachedClusterData(["deployments", "pods", "replicasets"]);
        const unavailable = clusterUnavailable(data, "deployments");
        if (unavailable)
            return unavailable;
        return clusterResponse(data, { deployments: data.deployments }, ["deployments"]);
    });
}
