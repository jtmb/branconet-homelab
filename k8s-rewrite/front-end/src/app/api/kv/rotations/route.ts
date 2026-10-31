import { z } from "zod/v3";
import { KvError } from "@/lib/kv-contract";
import { kvBody, kvEngine, kvHuman, metadataCursor } from "@/lib/kv-http";
import { KvRotations } from "@/lib/kv-rotation";
import { rotationAction, rotationPrepare } from "@/lib/kv-schemas";
import { KubectlRotationConsumer } from "@/lib/kv-rotation-consumer";
import { kubectlJSON } from "@/lib/k8s";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, request) => {
  const params = new URL(request.url).searchParams, pathId = params.get("pathId");
  if ([...params.keys()].some(key => !["pathId", "cursor"].includes(key) || params.getAll(key).length !== 1) || !z.string().uuid().safeParse(pathId).success) throw new KvError(400, "Explicit path and valid rotation metadata filters required");
  return new KvRotations(kvEngine(registry)).list(actor, pathId!, metadataCursor(request));
});
export const POST = kvHuman(async (registry, actor, request) => new KvRotations(kvEngine(registry)).prepare(actor, await kvBody(request, rotationPrepare, 4096)), 201);
export const PATCH = kvHuman(async (registry, actor, request) => {
  const input = await kvBody(request, rotationAction, 4096), rotations = new KvRotations(kvEngine(registry), new KubectlRotationConsumer(kubectlJSON));
  switch (input.action) {
    case "generate": return rotations.generate(actor, input.rotationId, input);
    case "acknowledge": return rotations.acknowledge(actor, input.rotationId, input);
    case "cancel": return rotations.cancel(actor, input.rotationId, input.revision, input.confirmPath);
    case "resolve": return rotations.resolve(actor, input.rotationId);
  }
});
