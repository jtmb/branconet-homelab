import { kvHuman, kvEngine, kvBody } from "@/lib/kv-http";
import { nativeReconcile } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const POST = kvHuman(async (registry, actor, request, { id }) => kvEngine(registry).change(actor, id, await kvBody(request, nativeReconcile), "reconcile"));
