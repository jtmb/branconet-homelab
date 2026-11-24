import { kvAdminMetadataBody, kvHuman } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyRevoke } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const DELETE = kvHuman(async (registry, actor, request, { id }) => {
  const { revision, legacyImpact } = await kvAdminMetadataBody(registry, actor, request, legacyRevoke);
  return new KvLegacyAccess(registry).commit(actor, { kind: "revoke", grantId: id, revision }, legacyImpact);
});
