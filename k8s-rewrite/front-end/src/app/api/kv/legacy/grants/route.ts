import { kvAdminMetadataBody, kvHuman, metadataCursor } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyGrant } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman((registry, actor, request) => new KvLegacyAccess(registry).grants(actor, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => {
  const { legacyImpact, ...change } = await kvAdminMetadataBody(registry, actor, request, legacyGrant);
  return new KvLegacyAccess(registry).commit(actor, { kind: "grant", ...change }, legacyImpact);
}, 201);
