import { validateNamespace, validateResourceName, KubernetesCommandError } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";
export async function POST(request: NextRequest, { params }: {
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
        try {
            const { replicas } = await request.json();
            if (!Number.isInteger(replicas) || replicas < 0 || replicas > 10000) {
                return NextResponse.json({ error: "Invalid replicas" }, { status: 400 });
            }
            const result = await kubectlExec(["scale", "deployment/" + (validateResourceName(name)), "-n", (validateNamespace(namespace)), "--replicas=" + (replicas)], 10000);
            if (result === null) {
                return NextResponse.json({ error: "Scale failed" }, { status: 500 });
            }
            invalidateCache();
            return NextResponse.json({ success: true });
        }
        catch (error) {
            if (error instanceof KubernetesCommandError)
                throw error;
            return NextResponse.json({ error: "Invalid request" }, { status: 400 });
        }
    });
}
