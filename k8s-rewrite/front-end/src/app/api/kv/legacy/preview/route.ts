import { kvBody, kvHuman } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyPreview } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request) => {
  const body = await kvBody(request, legacyPreview);
  const { cursor } = body;
  const change = {} as typeof body;
  const from = Object(body);
  // Copy own enumerable fields without rereading the excluded getter.
  for (const key of Reflect.ownKeys(from)) {
    if (key === "cursor") continue;
    const descriptor = Object.getOwnPropertyDescriptor(from, key);
    if (descriptor?.enumerable) Object.defineProperty(change, key, {
      value: Reflect.get(from, key), enumerable: true, writable: true, configurable: true,
    });
  }
  return new KvLegacyAccess(registry).preview(actor, change, cursor);
});
