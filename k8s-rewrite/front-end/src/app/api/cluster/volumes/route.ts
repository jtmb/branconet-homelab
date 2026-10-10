import { NextRequest, NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const typeFilter = searchParams.get("type");

  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ volumes: [] });
  }

  let volumes = data.volumes;

  // Filter by storage type
  if (typeFilter && typeFilter !== "all") {
    volumes = volumes.filter((v) => matchesType(v.storageClass, typeFilter));
  }

  return NextResponse.json({ volumes, storageClasses: data.storageClasses });
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