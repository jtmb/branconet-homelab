import { kvHuman, kvBody, metadataCursor } from "@/lib/kv-http";
import { identityCreate } from "@/lib/kv-schemas";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = kvHuman((registry, actor, request) => registry.listIdentities(actor, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => {
  const input = await kvBody(request, identityCreate);
  return registry.issueIdentity(actor, { ...input, expiresAt: new Date(input.expiresAt) });
}, 201);
