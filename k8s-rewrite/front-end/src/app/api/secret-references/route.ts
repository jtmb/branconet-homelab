import { requireOperator } from "@/lib/permissions";
import { getSessionAccount } from "@/lib/auth";
import { NextResponse } from "next/server";
import { SecretError } from "@/lib/cluster-secrets";
import { invalidateAliases, listAliases, pageAliases } from "@/lib/secret-references";
import { mergeAliases, validateAlias } from "@/lib/secret-aliases";
import { isSensitiveVariable } from "@/lib/variable-policy";
import { secretNamespaces } from "@/lib/secret-client";
import { secretResponse, secretErrorResponse } from "@/lib/secret-http";
import { KvError, kvConfig } from "@/lib/kv-contract";
import { kvBody, kvRegistry } from "@/lib/kv-http";
import { MAX_ALIASES } from "@/lib/alias-catalog";
import { z } from "zod/v3";
const aliasBody = z.object({ alias: z.string().max(253), namespace: z.string().max(63), name: z.string().max(253), key: z.string().max(253) }).strict();
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  try {
    const account = await getSessionAccount();
    if (!account || !["readonly", "write"].includes(account.role))
      throw new SecretError(401, "Authentication required");
    const params = new URL(request.url).searchParams, cursor = params.get("cursor"), namespace = params.get("namespace");
    if ([...params.keys()].some(key => !["cursor", "namespace"].includes(key) || params.getAll(key).length !== 1) ||
      cursor !== null && !/^[a-zA-Z0-9_.:/-]{1,253}$/.test(cursor)) throw new SecretError(400, "Invalid alias metadata filters");
    const namespaces = secretNamespaces().filter(ns => ns !== kvConfig().historyNamespace);
    if (namespace !== null && !namespaces.includes(namespace)) throw new SecretError(403, "Namespace is outside the configured Secret scope");
    return secretResponse(await pageAliases(new Set(namespaces), namespace, cursor));
  } catch (error) {
    return secretErrorResponse(error);
  }
}
export async function POST(request: Request) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  try {
    const ref = validateAlias(await kvBody(request, aliasBody, 4096));
    if (ref.namespace === kvConfig().historyNamespace) throw new SecretError(403, "Engine history cannot be registered as a flat alias");
    if (!secretNamespaces().includes(ref.namespace))
      throw new SecretError(
        403,
        "Namespace is outside the configured Secret scope",
      );
    const snapshot = await listAliases(), registry = kvRegistry();
    await registry.serialized(async tx => {
      await registry.admin(auth, tx);
      const current = await tx.secretReference.findMany({ take: MAX_ALIASES + 1, select: { alias: true, namespace: true, name: true, key: true } });
      let merged;
      try { merged = mergeAliases([snapshot, current, [ref]]); }
      catch (error) { if (error instanceof SecretError) throw new KvError(error.status, error.message); throw error; }
      if (current.length > MAX_ALIASES || merged.length > MAX_ALIASES) throw new KvError(413, "Alias metadata exceeds the limit");
      const variable = await tx.variable.findUnique({ where: { key: ref.alias }, select: { key: true, category: true, encrypted: true } });
      if (variable && !isSensitiveVariable(variable)) throw new KvError(409, "Alias collides with nonsecret configuration");
      if (!current.some(existing => existing.alias === ref.alias)) await tx.secretReference.create({ data: ref });
    });
    invalidateAliases();
    return secretResponse({ success: true, reference: ref }, 201);
  } catch (error) {
    return secretErrorResponse(error);
  }
}
export async function DELETE(request: Request) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  try {
    const alias = new URL(request.url).searchParams.get("alias");
    if (!alias) throw new SecretError(400, "alias is required");
    const registry = kvRegistry();
    await registry.serialized(async tx => { await registry.admin(auth, tx); await tx.secretReference.deleteMany({ where: { alias } }); });
    invalidateAliases();
    return secretResponse({
      success: true,
      message:
        "Database reference removed; ConfigMap references and native values are unchanged",
    });
  } catch (error) {
    return secretErrorResponse(error);
  }
}
