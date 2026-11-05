import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { KvRotations } from "@/lib/kv-rotation";
import { KubectlRotationConsumer } from "@/lib/kv-rotation-consumer";
import { rotationReload } from "@/lib/kv-schemas";
import { kubectlJSON } from "@/lib/k8s";
import { KvError } from "@/lib/kv-contract";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, _request, params) => new KvRotations(kvEngine(registry), new KubectlRotationConsumer(kubectlJSON)).consumerPreview(actor, params.id));
export const POST = kvHuman(async (registry, actor, request, params) => {
  const input = await kvBody(request, rotationReload, 4096);
  if (input.rotationId !== params.id) throw new KvError(400, "Rotation target must match the route");
  return new KvRotations(kvEngine(registry), new KubectlRotationConsumer(kubectlJSON)).reload(actor, params.id, input, request.signal);
});
