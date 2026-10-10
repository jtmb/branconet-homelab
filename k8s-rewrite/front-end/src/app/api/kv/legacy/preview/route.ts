import { kvBody, kvHuman } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyPreview } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request) => {
  const { cursor, ...change } = await kvBody(request, legacyPreview);
  return new KvLegacyAccess(registry).preview(actor, change, cursor);
});
