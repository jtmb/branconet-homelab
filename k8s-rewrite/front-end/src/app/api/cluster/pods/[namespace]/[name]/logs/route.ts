import { NextRequest, NextResponse } from "next/server";
import { clusterRoute } from "@/lib/cluster-http";
import { kubectlExec, validateNamespace, validateResourceName, KubernetesCommandError } from "@/lib/k8s";

function number(value: string | null, fallback: number, maximum: number) {
  if (value === null) return fallback;
  if (!/^\d+$/.test(value) || Number(value) < 1 || Number(value) > maximum) throw new KubernetesCommandError(400, "Invalid log limit");
  return Number(value);
}
export async function GET(request: NextRequest, { params }: { params: Promise<{ namespace: string; name: string }> }) {
  return clusterRoute(async () => {
    const target = await params, query = new URL(request.url).searchParams;
    const namespace = validateNamespace(target.namespace), name = validateResourceName(target.name);
    const tail = number(query.get("tail"), 100, 1000), since = number(query.get("sinceSeconds"), 0, 86400);
    const container = query.get("container"), previous = query.get("previous");
    if (previous !== null && previous !== "true" && previous !== "false") throw new KubernetesCommandError(400, "Invalid previous-log flag");
    const logs = await kubectlExec(["logs", name, "-n", namespace, `--tail=${tail}`, "--limit-bytes=262144", "--timestamps", ...(container !== null ? ["-c", validateNamespace(container)] : []), ...(since ? [`--since=${since}s`] : []), ...(previous === "true" ? ["--previous"] : [])]);
    if (Buffer.byteLength(logs) > 262144) throw new KubernetesCommandError(502, "Pod log response exceeds the size limit");
    return NextResponse.json({ logs, bounded: true, maxBytes: 262144 }, { headers: { "Cache-Control": "no-store" } });
  });
}
