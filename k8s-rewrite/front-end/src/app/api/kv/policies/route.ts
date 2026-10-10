import { kvHuman, kvBody, metadataCursor } from "@/lib/kv-http";
import { policyCreateRequest } from "@/lib/kv-schemas";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = kvHuman((registry, actor, request) => registry.listPolicies(actor, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => {
  const { legacyImpact, ...input } = await kvBody(request, policyCreateRequest);
  return registry.savePolicy(actor, input, undefined, undefined, legacyImpact);
}, 201);
