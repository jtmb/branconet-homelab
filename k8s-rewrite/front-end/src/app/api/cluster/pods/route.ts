import { NextRequest } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse } from "@/lib/cluster-response";
import { podFilter, podSummary } from "@/lib/pod-query";
export async function GET(request: NextRequest) {
    return clusterRoute(async () => {
        const predicate = podFilter(new URL(request.url).searchParams);
        const data = await getCachedClusterData(["pods"]);
        return clusterResponse(data, { pods: data.pods.filter(predicate).map(podSummary) }, ["pods"]);
    });
}
