import { kvAdminMetadataBody, kvHuman } from "@/lib/kv-http";
import { KvLegacyAccess } from "@/lib/kv-legacy-access";
import { legacyPrincipal } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman((registry, actor) => new KvLegacyAccess(registry).state(actor));
export const PATCH = kvHuman(async (registry, actor, request) => {
  const body = await kvAdminMetadataBody(registry, actor, request, legacyPrincipal);
  const { legacyImpact } = body;
  const input = {} as typeof body;
  const from = Object(body);
  // Copy own enumerable fields without rereading the excluded getter.
  for (const key of Reflect.ownKeys(from)) {
    if (key === "legacyImpact") continue;
    const descriptor = Object.getOwnPropertyDescriptor(from, key);
    if (descriptor?.enumerable) Object.defineProperty(input, key, {
      value: Reflect.get(from, key), enumerable: true, writable: true, configurable: true,
    });
  }
  return new KvLegacyAccess(registry).commit(actor, { kind: "principal", ...input }, legacyImpact);
});
