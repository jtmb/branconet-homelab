import prisma from "@/lib/db";
import { createSecretTransport, secretNamespaces } from "@/lib/secret-client";
import { secretResponse } from "@/lib/secret-http";
import { listAliases } from "@/lib/secret-references";
import { kvConfig } from "@/lib/kv-contract";
import { createReadinessCache, probeSecretScopes } from "@/lib/readiness";
import type { MetadataCache } from "@/lib/metadata-cache";
const scope = globalThis as typeof globalThis & { __bortusReadiness?: MetadataCache<void> };
const cache = scope.__bortusReadiness ??= createReadinessCache(async key => {
  const deadline = Date.now() + 8000;
  const { namespaces } = JSON.parse(key) as { namespaces: string[] };
  const [lock, principal] = await Promise.all([
    prisma.accountLock.findUnique({ where: { id: 1 }, select: { id: true } }),
    prisma.kvServicePrincipal.findUnique({ where: { id: "legacy-lookup" }, select: { id: true } }),
    prisma.user.findFirst({ select: { sessionVersion: true, engineAdmin: true } }), listAliases(),
  ]);
  if (!lock || !principal) throw new Error("Migration metadata unavailable");
  const transport = createSecretTransport();
  await probeSecretScopes(namespaces, (namespace, nativeDeadline) => transport.probe(namespace, nativeDeadline), deadline);
});
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export async function GET() {
  try {
    if (!process.env.BOTRUS_JWT_SECRET || !process.env.BOTRUS_SECRETS_KEY)
      return secretResponse(
        { status: "unready", dependency: "configuration" },
        503,
      );
    const config = kvConfig(), namespaces = secretNamespaces().filter(ns => ns !== config.historyNamespace);
    if (!namespaces.length) throw new Error("No current Secret namespace");
    if (config.guardedAdoption) namespaces.push(config.historyNamespace);
    await cache.get(JSON.stringify({ namespaces, aliases: process.env.BORTUS_SECRET_ALIASES_FILE || "", connection: process.env.KUBECONFIG || process.env.KUBERNETES_SERVICE_HOST || "default", port: process.env.KUBERNETES_SERVICE_PORT || "" }));
    return secretResponse({ status: "ready" });
  } catch {
    return secretResponse(
      { status: "unready", dependency: "database or Kubernetes Secrets" },
      503,
    );
  }
}
