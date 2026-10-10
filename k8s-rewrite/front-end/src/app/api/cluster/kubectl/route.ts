import { NextRequest, NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { shellExec } from "@/lib/k8s";
import { runtimeCapabilities } from "@/lib/runtime-capabilities";

/**
 * POST /api/cluster/kubectl
 * Execute an arbitrary shell command via bash -c and return stdout+stderr.
 * KUBECONFIG is set so kubectl commands work naturally.
 * Write-gated — only users with write role can run commands.
 */
export async function POST(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  if (!runtimeCapabilities().operatorShell) return NextResponse.json({ error: "Operator shell is unavailable in this runtime" }, { status: 501 });

  try {
    const { command } = await request.json();
    if (!command || typeof command !== "string" || command.length > 16384 || command.includes("\0")) {
      return NextResponse.json(
        { error: "Missing or invalid 'command' field" },
        { status: 400 }
      );
    }

    const output = await shellExec(command.trim(), 30000);
    return NextResponse.json({ output: output ?? "" });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Operator command failed" },
      { status: 500 }
    );
  }
}
