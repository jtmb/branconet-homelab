import { validateNamespace, validateResourceName } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";
export async function DELETE(_request: NextRequest, { params }: {
    params: Promise<{
        namespace: string;
        name: string;
    }>;
}) {
    return clusterRoute(async () => {
        const auth = await requireOperator();
        if (auth instanceof NextResponse)
            return auth;
        const { namespace: rawNamespace, name: rawName } = await params;
        const namespace = validateNamespace(rawNamespace), name = validateResourceName(rawName);
        const result = await kubectlExec(["delete", "deployment", (validateResourceName(name)), "-n", (validateNamespace(namespace)), "--wait=false"], 15000);
        invalidateCache();
        return NextResponse.json({ success: true });
    });
}
