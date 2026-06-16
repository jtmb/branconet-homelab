import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { parseSecretKey, syncSecretToCluster } from "@/lib/cluster-secrets";
import { requireWrite } from "@/lib/permissions";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { id } = await params;

  const variable = await prisma.variable.findUnique({ where: { id } });
  if (!variable) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  // Parse secret info BEFORE deleting the DB record
  let secretNs: string | null = null;
  let secretName: string | null = null;

  const parsed = parseSecretKey(variable.key);
  if (parsed && variable.category === "secret") {
    secretNs = parsed.namespace;
    secretName = parsed.name;
  }

  // Delete from DB
  await prisma.variable.delete({ where: { id } });

  // Re-sync: cluster-secrets will rebuild or delete the K8s Secret
  if (secretNs && secretName) {
    syncSecretToCluster(secretNs, secretName).catch((err) =>
      console.error("[vars] DELETE K8s sync error:", err)
    );
  }

  return NextResponse.json({ success: true });
}
