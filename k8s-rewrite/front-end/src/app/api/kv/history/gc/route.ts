import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { historyGc } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request) => {
  const input = await kvBody(request, historyGc);
  return kvEngine(registry).gc(actor, input.pathId, input, request.signal);
});
