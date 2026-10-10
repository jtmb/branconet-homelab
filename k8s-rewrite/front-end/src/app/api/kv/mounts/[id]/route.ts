import { kvHuman, kvBody } from "@/lib/kv-http";
import { mountUpdate, removeMetadata } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const PATCH = kvHuman(async (registry, actor, request, { id }) => {
  const { revision, ...input } = await kvBody(request, mountUpdate);
  return registry.changeMount(actor, id, revision, input);
});
export const DELETE = kvHuman(async (registry, actor, request, { id }) => registry.changeMount(actor, id, (await kvBody(request, removeMetadata)).revision, null));
