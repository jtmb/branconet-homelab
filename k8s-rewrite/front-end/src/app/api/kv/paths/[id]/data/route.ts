import { kvHuman, kvEngine, kvBody } from "@/lib/kv-http";
import { dataChange, nativeDelete } from "@/lib/kv-schemas";
import { KvError } from "@/lib/kv-contract";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, _request, { id }) => kvEngine(registry).read(actor, id));
export const POST = kvHuman(async (registry, actor, request, { id }) => kvEngine(registry).create(actor, id, await kvBody(request, dataChange)), 201);
export const PUT = kvHuman(async (registry, actor, request, { id }) => kvEngine(registry).change(actor, id, await kvBody(request, dataChange)));
export const DELETE = kvHuman(async (registry, actor, request, { id }) => {
  const input = await kvBody(request, nativeDelete), path = await registry.path(id);
  if (input.confirmPath !== path.path) throw new KvError(400, "Exact logical path confirmation required");
  return kvEngine(registry).change(actor, id, input, "delete");
});
