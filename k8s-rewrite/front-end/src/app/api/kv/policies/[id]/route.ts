import { kvHuman, kvBody } from "@/lib/kv-http";
import { policyUpdate, removeMetadata } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const PATCH = kvHuman(async (registry, actor, request, { id }) => {
  const { revision, ...input } = await kvBody(request, policyUpdate);
  return registry.savePolicy(actor, input, id, revision);
});
export const DELETE = kvHuman(async (registry, actor, request, { id }) => registry.deletePolicy(actor, id, (await kvBody(request, removeMetadata)).revision));
