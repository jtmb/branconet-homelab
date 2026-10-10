import { NextRequest, NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { clusterRoute } from "@/lib/cluster-http";
import { kubectlExec, validateNamespace, validateResourceName } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ namespace: string; name: string }> }) {
  return clusterRoute(async () => {
    const auth = await requireWrite();
    if (auth instanceof NextResponse) return auth;
    const target = await params;
    await kubectlExec(["delete", "ingress", validateResourceName(target.name), "-n", validateNamespace(target.namespace), "--wait=false"], 15000);
    invalidateCache();
    return NextResponse.json({ success: true });
  });
}
