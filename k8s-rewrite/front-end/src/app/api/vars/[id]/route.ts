import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";
import { isSensitiveVariable } from "@/lib/variable-policy";
import { SecretError } from "@/lib/cluster-secrets";
import { secretResponse, secretErrorResponse } from "@/lib/secret-http";
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  try {
    const { id } = await params;
    const variable = await prisma.variable.findUnique({ where: { id } });
    if (!variable) throw new SecretError(404, "Variable not found");
    if (isSensitiveVariable(variable))
      throw new SecretError(
        409,
        "Legacy sensitive rows are quarantined; delete native keys through /api/secrets",
      );
    await prisma.variable.delete({ where: { id } });
    return secretResponse({ success: true });
  } catch (error) {
    return secretErrorResponse(error);
  }
}
