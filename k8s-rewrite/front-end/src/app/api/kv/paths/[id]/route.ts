import { kvHuman, kvBody } from "@/lib/kv-http";
import { KvError, policyAllows } from "@/lib/kv-contract";
import { pathUpdate } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const GET = kvHuman(async (registry, actor, _request, { id }) => {
  const path = await registry.path(id);
  await registry.authorize(actor, path, "list");
  if (actor.identityId && !policyAllows(await registry.rules(`user:${actor.id}`), path, "list"))
    throw new KvError(403, "KV policy denies this action");
  await registry.current(actor);
  return { id: path.id, mountId: path.mountId, path: path.path, namespace: path.namespace, name: path.name, retention: path.retention, revision: path.revision, createdAt: path.createdAt, fields: path.fields.map(({ field, key }) => ({ field, key })) };
});
export const PATCH = kvHuman(async (registry, actor, request, { id }) => {
  const input = await kvBody(request, pathUpdate);
  return registry.changeRetention(actor, id, input.revision, input.retention);
});
