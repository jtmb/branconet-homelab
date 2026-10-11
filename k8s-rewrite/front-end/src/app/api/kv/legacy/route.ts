import { kvAdminMetadataBody, kvHuman } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyPrincipal } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman((registry, actor) => new KvLegacyAccess(registry).state(actor));
export const PATCH = kvHuman(async (registry, actor, request) => {
  const { legacyImpact, ...input } = await kvAdminMetadataBody(registry, actor, request, legacyPrincipal);
  return new KvLegacyAccess(registry).commit(actor, { kind: "principal", ...input }, legacyImpact);
});
