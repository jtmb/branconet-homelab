import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { requireWrite } from "@/lib/permissions";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { namespace, name } = await params;
  try {
    const { command } = await request.json();
    if (!command || typeof command !== "string") {
      return NextResponse.json({ error: "No command" }, { status: 400 });
    }
    const output = await kubectlExec(
      `exec ${name} -n ${namespace} -- ${command}`,
      15000
    );
    return NextResponse.json({ output: output ?? "" });
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}
