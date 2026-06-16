import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { writeFile, unlink } from "fs/promises";
import { randomUUID } from "crypto";
import { tmpdir } from "os";
import { join } from "path";
import { requireWrite } from "@/lib/permissions";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const { namespace, name } = await params;
  const yaml = await kubectlExec(`get pod ${name} -n ${namespace} -o yaml`, 10000);
  if (!yaml) {
    return NextResponse.json({ error: "Failed to get YAML" }, { status: 500 });
  }
  return NextResponse.json({ yaml });
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ namespace: string; name: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { namespace, name } = await params;
  try {
    const { yaml } = await request.json();
    if (!yaml || typeof yaml !== "string") {
      return NextResponse.json({ error: "No YAML body" }, { status: 400 });
    }
    const tmpPath = join(tmpdir(), `k8s-edit-${randomUUID()}.yaml`);
    await writeFile(tmpPath, yaml);
    try {
      const result = await kubectlExec(`apply -f ${tmpPath}`, 15000);
      if (result === null) {
        return NextResponse.json({ error: "Apply failed" }, { status: 500 });
      }
      return NextResponse.json({ success: true });
    } finally {
      await unlink(tmpPath).catch(() => {});
    }
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}
