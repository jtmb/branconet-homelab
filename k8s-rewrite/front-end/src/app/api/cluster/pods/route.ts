import { NextRequest } from "next/server";
import { getCachedClusterResource } from "@/lib/cluster-cache";
import { clusterRoute } from "@/lib/cluster-http";
import { podFilter } from "@/lib/pod-query";
import { podMetadataResponse } from "@/lib/pod-metadata-response";
export async function GET(request: NextRequest) {
    return clusterRoute(async () => {
        const query = new URL(request.url).searchParams;
        const predicate = podFilter(query);
        const snapshot = await getCachedClusterResource("pods");
        const data = { pods: snapshot.value?.items ?? [], availability: { pods: snapshot.availability } };
        const filtered = query.has("namespace") || !!query.get("labelSelector") || !!query.get("type") && query.get("type") !== "all";
        return podMetadataResponse(data, predicate, filtered);
    });
}
