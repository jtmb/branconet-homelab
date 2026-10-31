import { validateResourceName, KubernetesCommandError, kubectlExec } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { requireOperator } from "@/lib/permissions";

export async function GET() {
  return clusterRoute(async () => {
    const output = await kubectlExec([
      "get", "pv", "-o", "custom-columns=NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase,STORAGECLASS:.spec.storageClassName,CAPACITY:.spec.capacity.storage,CLAIM:.spec.claimRef.name,AGE:.metadata.creationTimestamp", "--no-headers",
    ], 8000);
    const volumes = output.trim() ? output.trim().split("\n").map(line => {
      const parts = line.trim().split(/\s+/);
      return { name: parts[0], reclaimPolicy: parts[1], status: parts[2], storageClass: parts[3], capacity: parts[4], claimRef: parts[5], age: parts[6] };
    }) : [];
    return NextResponse.json({ volumes });
  });
}

export async function PATCH(request: NextRequest) {
  return clusterRoute(async () => {
    const auth = await requireOperator();
    if (auth instanceof NextResponse) return auth;
    const body = await request.json();
    if (!Array.isArray(body?.volumes) || !body.volumes.length || body.volumes.length > 100)
      return NextResponse.json({ error: "Specify between 1 and 100 volumes" }, { status: 400 });
    const volumes: { name: string; policy: string }[] = body.volumes;
    for (const volume of volumes) {
      validateResourceName(volume?.name);
      if (!["Retain", "Delete", "Recycle"].includes(volume?.policy))
        return NextResponse.json({ error: "Invalid reclaim policy" }, { status: 400 });
    }
    const results = [];
    for (const volume of volumes) {
      try {
        await kubectlExec(["patch", "pv", volume.name, "-p", JSON.stringify({ spec: { persistentVolumeReclaimPolicy: volume.policy } })], 8000);
        results.push({ name: volume.name, success: true });
      } catch (error) {
        results.push({ name: volume.name, success: false, error: error instanceof KubernetesCommandError ? error.message : "Volume update unavailable" });
      }
    }
    const success = results.every(result => result.success);
    return NextResponse.json({ results, success }, { status: success ? 200 : 207 });
  });
}
