import { validateNamespace, validateResourceName } from "@/lib/k8s";
import { deploymentPods } from "@/lib/deployment-state";
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
        const data = await getCachedClusterData(["deployments", "pods", "replicasets"]);
        const unavailable = clusterUnavailable(data, "deployments");
        if (unavailable)
            return unavailable;
        const rawDeploy = (data.rawDeployments || []).find((d: any) => d.metadata?.namespace === namespace && d.metadata?.name === name);
        if (!rawDeploy) {
            return clusterMissing(data, "deployments", "Deployment not found");
        }
        const ownershipAvailable = ["pods", "replicasets"].every(resource => data.availability[resource as "pods" | "replicasets"] && !["unavailable", "unsupported"].includes(data.availability[resource as "pods" | "replicasets"]!.state));
        const pods = ownershipAvailable ? deploymentPods(rawDeploy, data.pods, data.rawReplicaSets) : null;
        return clusterResponse(data, { deployment: rawDeploy, pods, ownershipAvailable }, ["deployments"]);
    });
}
