import { kvHuman, kvBody } from "@/lib/kv-http";
import { policyUpdate, policyRemove } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const PATCH = kvHuman(async (registry, actor, request, { id }) => {
  const { revision, legacyImpact, ...input } = await kvBody(request, policyUpdate);
  return registry.savePolicy(actor, input, id, revision, legacyImpact);
});
export const DELETE = kvHuman(async (registry, actor, request, { id }) => {
  const { revision, legacyImpact } = await kvBody(request, policyRemove);
  return registry.deletePolicy(actor, id, revision, legacyImpact);
});
