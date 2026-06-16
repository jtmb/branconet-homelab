import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireWrite } from "@/lib/permissions";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { namespace, name } = await params;
  try {
    const { replicas } = await request.json();
    if (typeof replicas !== "number" || replicas < 0) {
      return NextResponse.json({ error: "Invalid replicas" }, { status: 400 });
    }
    const result = await kubectlExec(
      `scale deployment/${name} -n ${namespace} --replicas=${replicas}`,
      10000
    );
    if (result === null) {
      return NextResponse.json({ error: "Scale failed" }, { status: 500 });
    }
    invalidateCache();
    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}
