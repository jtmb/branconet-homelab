import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable } from "@/lib/cluster-response";
import { NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET() {
    return clusterRoute(async () => {
        const data = await getCachedClusterData(["services"]);
        const unavailable = clusterUnavailable(data, "services");
        if (unavailable)
            return unavailable;
        return clusterResponse(data, { services: data.services }, ["services"]);
    });
}
