import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { historyGcPreview } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request) => {
  const input = await kvBody(request, historyGcPreview);
  return kvEngine(registry).gcPreview(actor, input.pathId);
});
