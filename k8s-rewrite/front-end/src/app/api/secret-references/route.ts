import prisma from "@/lib/db";
import { getCurrentRole, requireWrite } from "@/lib/permissions";
import { NextResponse } from "next/server";
import { SecretError } from "@/lib/cluster-secrets";
import { listAliases } from "@/lib/secret-references";
import { mergeAliases, validateAlias } from "@/lib/secret-aliases";
import { isSensitiveVariable } from "@/lib/variable-policy";
import { secretNamespaces } from "@/lib/secret-client";
import { secretResponse, secretErrorResponse } from "@/lib/secret-http";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    if (!(await getCurrentRole()))
      throw new SecretError(401, "Authentication required");
    return secretResponse({ references: await listAliases() });
  } catch (error) {
    return secretErrorResponse(error);
  }
}
export async function POST(request: Request) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  try {
    let body;
    try {
      body = await request.json();
    } catch {
      throw new SecretError(400, "Invalid JSON request");
    }
    const ref = validateAlias(body);
    if (!secretNamespaces().includes(ref.namespace))
      throw new SecretError(
        403,
        "Namespace is outside the configured Secret scope",
      );
    mergeAliases([await listAliases(), [ref]]);
    const variable = await prisma.variable.findUnique({
      where: { key: ref.alias },
      select: { key: true, category: true, encrypted: true },
    });
    if (variable && !isSensitiveVariable(variable))
      throw new SecretError(409, "Alias collides with nonsecret configuration");
    // Alias targets are immutable. Delete the reference deliberately before remapping.
    const existing = await prisma.secretReference.findUnique({
      where: { alias: ref.alias },
    });
    if (existing) mergeAliases([[existing], [ref]]);
    if (!existing) {
      try {
        await prisma.secretReference.create({ data: ref });
      } catch {
        throw new SecretError(
          409,
          "Alias registration conflict; refresh before retrying",
        );
      }
    }
    return secretResponse({ success: true, reference: ref }, 201);
  } catch (error) {
    return secretErrorResponse(error);
  }
}
export async function DELETE(request: Request) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  try {
    const alias = new URL(request.url).searchParams.get("alias");
    if (!alias) throw new SecretError(400, "alias is required");
    await prisma.secretReference.deleteMany({ where: { alias } });
    return secretResponse({
      success: true,
      message:
        "Database reference removed; ConfigMap references and native values are unchanged",
    });
  } catch (error) {
    return secretErrorResponse(error);
  }
}
