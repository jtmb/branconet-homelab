import { validateNamespace, validateResourceName } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable, clusterMissing } from "@/lib/cluster-response";
import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET(_request: NextRequest, { params }: {
    params: Promise<{
        name: string;
    }>;
}) {
    return clusterRoute(async () => {
        const { name: rawName } = await params;
        const name = validateNamespace(rawName);
        const data = await getCachedClusterData(["namespaces", "pods", "deployments", "replicasets", "services"]);
        const unavailable = clusterUnavailable(data, "namespaces");
        if (unavailable)
            return unavailable;
        const rawNs = (data.rawNamespaces || []).find((ns: any) => ns.metadata?.name === name);
        if (!rawNs) {
            return clusterMissing(data, "namespaces", "Namespace not found");
        }
        const now = Date.now();
        const created = rawNs.metadata?.creationTimestamp;
        const age = created ? formatAge(now - new Date(created).getTime()) : "-";
        // Filter all resources in this namespace
        const nsPods = (data.pods || []).filter((p: any) => p.metadata?.namespace === name);
        const nsDeployments = data.deployments.filter((d: any) => d.namespace === name);
        const nsServices = data.services.filter((s: any) => s.namespace === name);
        return clusterResponse(data, {
            namespace: {
                name: rawNs.metadata?.name || "unknown",
                status: rawNs.status?.phase || "Active",
                age,
            },
            pods: nsPods,
            deployments: nsDeployments,
            services: nsServices,
        }, ["namespaces"]);
    });
}
function formatAge(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60)
        return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60)
        return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24)
        return `${hours}h`;
    const days = Math.floor(hours / 24);
    if (days < 365)
        return `${days}d`;
    const years = Math.floor(days / 365);
    return `${years}y`;
}
