import { validateNamespace, validateResourceName, KubernetesCommandError } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";
const ACTIONS: Record<string, string[]> = {
    restart: ["rollout", "restart"],
    rollback: ["rollout", "undo"],
    pause: ["rollout", "pause"],
    resume: ["rollout", "resume"],
};
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
            const body = await request.json();
            const action = body?.action;
            if (typeof action !== "string" || !Object.hasOwn(ACTIONS, action)) {
                return NextResponse.json({ error: "Invalid deployment action" }, { status: 400 });
            }
            const kubectlAction = ACTIONS[action];
            const result = await kubectlExec([...kubectlAction, "deployment", name, "-n", namespace], 15000);
            if (result === null) {
                return NextResponse.json({ error: "Action failed" }, { status: 500 });
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
