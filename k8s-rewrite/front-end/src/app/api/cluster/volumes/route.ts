import { clusterRoute } from "@/lib/cluster-http";
import { clusterResponse, clusterUnavailable } from "@/lib/cluster-response";
import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";
export async function GET(request: NextRequest) {
    return clusterRoute(async () => {
        const { searchParams } = new URL(request.url);
        const typeFilter = searchParams.get("type");
        const kind = searchParams.get("kind") || "pv";
        if (!["pv", "pvc"].includes(kind) || typeFilter && !["all", "local", "nfs", "samba", "longhorn"].includes(typeFilter))
            return NextResponse.json({ error: "Invalid storage filter" }, { status: 400 });
        if (kind === "pvc") {
            const data = await getCachedClusterData(["pvc", "sc"]);
            const volumes = data.rawPvcs.map((pvc: any) => ({
                id: pvc.metadata?.uid, name: pvc.metadata?.name, namespace: pvc.metadata?.namespace,
                status: pvc.status?.phase || "Unknown",
                capacity: pvc.status?.capacity?.storage ?? pvc.spec?.resources?.requests?.storage ?? null,
                storageClass: pvc.spec?.storageClassName || "none", node: null,
            })).filter(volume => !typeFilter || typeFilter === "all" || matchesType(volume.storageClass, typeFilter));
            return clusterResponse(data, { volumes, storageClasses: data.storageClasses }, ["pvc"]);
        }
        const data = await getCachedClusterData(["pv", "longhorn", "sc"]);
        const unavailable = clusterUnavailable(data, "pv");
        if (unavailable)
            return unavailable;
        let volumes = data.volumes;
        // Filter by storage type
        if (typeFilter && typeFilter !== "all") {
            volumes = volumes.filter((v) => matchesType(v.storageClass, typeFilter));
        }
        return clusterResponse(data, { volumes, storageClasses: data.storageClasses }, ["pv"]);
    });
}
/**
 * Match a storageClassName against a filter type keyword.
 * Uses loose matching so "local-path" matches "local", "nfs-client" matches "nfs", etc.
 */
function matchesType(storageClass: string, type: string): boolean {
    const sc = storageClass.toLowerCase();
    switch (type) {
        case "local":
            return sc.includes("local-path") || sc === "none" || sc === "local";
        case "nfs":
            return sc.includes("nfs");
        case "samba":
            return sc.includes("smb") || sc.includes("samba") || sc.includes("cifs");
        case "longhorn":
            return sc.includes("longhorn");
        default:
            return true;
    }
}
