import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { nativeDestroy } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request, { id }) => kvEngine(registry).destroy(actor, id, await kvBody(request, nativeDestroy), request.signal));
