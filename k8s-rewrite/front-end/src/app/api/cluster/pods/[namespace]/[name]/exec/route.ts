import { NextRequest, NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { clusterRoute } from "@/lib/cluster-http";
import { kubectlExec, validateNamespace, validateResourceName } from "@/lib/k8s";
import { runtimeCapabilities } from "@/lib/runtime-capabilities";

export async function POST(request: NextRequest, { params }: { params: Promise<{ namespace: string; name: string }> }) {
  return clusterRoute(async () => {
    const auth = await requireWrite();
    if (auth instanceof NextResponse) return auth;
    if (!runtimeCapabilities().podExec) return NextResponse.json({ error: "Pod execution is disabled in this runtime" }, { status: 501 });
    const target = await params, namespace = validateNamespace(target.namespace), name = validateResourceName(target.name);
    const body = await request.json();
    if (typeof body?.command !== "string" || !body.command.trim() || Buffer.byteLength(body.command) > 16384 || body.command.includes("\0"))
      return NextResponse.json({ error: "Supply a command within the 16-KiB limit" }, { status: 400 });
    const output = await kubectlExec(["exec", name, "-n", namespace, ...(body.container !== undefined ? ["-c", validateNamespace(body.container)] : []), "--", "sh", "-lc", body.command], 15000);
    return NextResponse.json({ output }, { headers: { "Cache-Control": "no-store" } });
  });
}
