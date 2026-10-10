import { NextRequest, NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { clusterRoute } from "@/lib/cluster-http";
import { kubectlExec, validateResourceName } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";

export async function POST(request: NextRequest, { params }: { params: Promise<{ hostname: string }> }) {
  return clusterRoute(async () => {
    const auth = await requireWrite();
    if (auth instanceof NextResponse) return auth;
    const name = validateResourceName((await params).hostname), body = await request.json();
    if (!["cordon", "uncordon", "drain"].includes(body?.action)) return NextResponse.json({ error: "Invalid node action" }, { status: 400 });
    if (body.action === "drain" && body.confirmName !== name) return NextResponse.json({ error: "Confirm the exact node name to drain" }, { status: 400 });
    try {
      await kubectlExec([body.action, name, ...(body.action === "drain" ? ["--ignore-daemonsets", "--timeout=20s"] : [])], 25000);
      return NextResponse.json({ success: true });
    } finally {
      // Drain may have cordoned/evicted some pods before a timeout or PDB refusal.
      invalidateCache();
    }
  });
}
