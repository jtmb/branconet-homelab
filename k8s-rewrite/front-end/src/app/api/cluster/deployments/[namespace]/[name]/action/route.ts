import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";

const ACTIONS: Record<string, string> = {
  restart: "rollout restart",
  rollback: "rollout undo",
  pause: "rollout pause",
  resume: "rollout resume",
};

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const { namespace, name } = await params;
  try {
    const { action } = await request.json();
    const kubectlAction = ACTIONS[action];
    if (!kubectlAction) {
      return NextResponse.json(
        { error: `Unknown action: ${action}` },
        { status: 400 }
      );
    }
    const result = await kubectlExec(
      `${kubectlAction} deployment/${name} -n ${namespace}`,
      15000
    );
    if (result === null) {
      return NextResponse.json({ error: "Action failed" }, { status: 500 });
    }
    invalidateCache();
    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}
