import { kvHuman, kvBody } from "@/lib/kv-http";
import { identityRevoke } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const DELETE = kvHuman(async (registry, actor, request, { id }) => {
  const input = await kvBody(request, identityRevoke);
  return registry.revokeIdentity(actor, id, input.revision);
});
