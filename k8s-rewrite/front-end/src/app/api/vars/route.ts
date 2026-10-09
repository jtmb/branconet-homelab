import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite, getCurrentRole } from "@/lib/permissions";
import { isSensitiveVariable } from "@/lib/variable-policy";
import { resolveAlias } from "@/lib/secret-references";
import { nativeSecrets } from "@/lib/secret-client";
import { SecretError } from "@/lib/cluster-secrets";
import { secretResponse, secretErrorResponse } from "@/lib/secret-http";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    if (!(await getCurrentRole()))
      throw new SecretError(401, "Authentication required");
    const vars = await prisma.variable.findMany({
      orderBy: { category: "asc" },
    });
    return secretResponse(
      vars.filter((variable) => !isSensitiveVariable(variable)),
    );
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
    if (!body || typeof body !== "object")
      throw new SecretError(400, "Invalid variable request");
    const existing = body.id
      ? await prisma.variable.findUnique({ where: { id: body.id } })
      : typeof body.key === "string"
        ? await prisma.variable.findUnique({ where: { key: body.key } })
        : null;
    if (body.id && !existing) throw new SecretError(404, "Variable not found");
    const key = body.key ?? existing?.key;
    const category = body.category ?? existing?.category ?? "general";
    const encrypted = body.encrypted ?? existing?.encrypted ?? false;
    if (
      typeof key !== "string" ||
      !/^[a-zA-Z0-9_.:/-]{1,253}$/.test(key) ||
      typeof category !== "string" ||
      typeof encrypted !== "boolean" ||
      typeof body.value !== "string"
    )
      throw new SecretError(
        400,
        "Valid key, category and text value are required",
      );
    const target = await resolveAlias(key);
    if (
      target ||
      isSensitiveVariable({ key, category, encrypted }) ||
      (existing && isSensitiveVariable(existing))
    ) {
      if (!target)
        throw new SecretError(
          400,
          "Sensitive values require an explicit Secret mapping; use /api/secrets and /api/secret-references",
        );
      return secretResponse({
        success: true,
        secret: await nativeSecrets().write(
          target,
          body.value,
          body.mode || "update",
          body.resourceVersion,
        ),
      });
    }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key))
      throw new SecretError(400, "Nonsecret keys must be valid Ansible identifiers");
    const variable = await prisma.variable.upsert({
      where: { key },
      create: { key, value: body.value, category, encrypted: false },
      update: { value: body.value, category, encrypted: false },
    });
    return secretResponse({ success: true, variable }, existing ? 200 : 201);
  } catch (error) {
    return secretErrorResponse(error);
  }
}
