import { historyVersion, kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { nativeDestroy } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const DELETE = kvHuman(async (registry, actor, request, { id, version }) => kvEngine(registry).destroy(actor, id,
  { ...await kvBody(request, nativeDestroy.omit({ versions: true })), versions: [historyVersion(version)] }, request.signal));
