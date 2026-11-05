import { kvBody, kvHuman } from "@/lib/kv-http";
import { policyPreview } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request) => {
  const input = await kvBody(request, policyPreview);
  if (input.action === "delete") return registry.previewPolicy(actor, null, input.id, input.revision, input.cursor);
  if (input.action === "create") {
    const { action: _action, cursor, ...fields } = input;
    return registry.previewPolicy(actor, fields, undefined, undefined, cursor);
  }
  const { action: _action, id, revision, cursor, ...fields } = input;
  return registry.previewPolicy(actor, fields, id, revision, cursor);
});
