import { historyVersion, kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { nativeDelete } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const DELETE = kvHuman(async (registry, actor, request, { id, version }) => kvEngine(registry).destroy(actor, id,
  { ...await kvBody(request, nativeDelete), versions: [historyVersion(version)] }, request.signal));
