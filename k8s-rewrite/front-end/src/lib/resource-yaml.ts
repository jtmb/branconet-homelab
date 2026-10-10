import { NextRequest, NextResponse } from "next/server";
import { loadAllYaml } from "@kubernetes/client-node";
import { writeFile, unlink } from "fs/promises";
import { randomUUID } from "crypto";
import { tmpdir } from "os";
import { join } from "path";
import { kubectlExec, validateNamespace, validateResourceName, KubernetesCommandError } from "./k8s";
import { RESOURCE_CAPABILITIES, type ResourceType } from "./resource-capabilities";
import { requireWrite } from "./permissions";
import { clusterRoute } from "./cluster-http";
import { invalidateCache } from "./cluster-cache";

type Context = { params: Promise<Record<string, string>> };
function target(type: ResourceType, params: Record<string, string>) {
  const capability = RESOURCE_CAPABILITIES[type];
  const name = type === "namespace" ? validateNamespace(params.name) : validateResourceName(params.name || params.hostname);
  const namespace = capability.namespaced ? validateNamespace(params.namespace) : undefined;
  return { capability, name, namespace };
}

export function validateResourceYaml(type: ResourceType, name: string, namespace: string | undefined, yaml: unknown): string {
  if (typeof yaml !== "string" || !yaml.trim() || Buffer.byteLength(yaml) > 256 * 1024)
    throw new KubernetesCommandError(400, "Supply resource YAML within the 256-KiB limit");
  let objects: any[];
  try { objects = loadAllYaml(yaml); }
  catch { throw new KubernetesCommandError(400, "Invalid resource YAML"); }
  const capability = RESOURCE_CAPABILITIES[type], object = objects[0];
  if (objects.length !== 1 || object?.kind !== capability.kind || object?.apiVersion !== capability.apiVersion || object?.metadata?.name !== name || capability.namespaced && object?.metadata?.namespace !== namespace)
    throw new KubernetesCommandError(400, "YAML must contain only the requested resource with its exact namespace and name");
  if (typeof object.metadata.resourceVersion !== "string" || !object.metadata.resourceVersion)
    throw new KubernetesCommandError(428, "Current resourceVersion is required; refresh YAML before saving");
  return yaml;
}

export function resourceYamlGet(type: ResourceType) {
  return async (_request: NextRequest, context: Context) => clusterRoute(async () => {
    const { capability, name, namespace } = target(type, await context.params);
    const yaml = await kubectlExec(["get", capability.kind.toLowerCase(), name, ...(namespace ? ["-n", namespace] : []), "-o", "yaml"]);
    if (!yaml.trim()) throw new KubernetesCommandError(502, "Empty Kubernetes YAML response");
    if (Buffer.byteLength(yaml) > 256 * 1024) throw new KubernetesCommandError(413, "Resource YAML exceeds the 256-KiB limit");
    return NextResponse.json({ yaml }, { headers: { "Cache-Control": "no-store" } });
  });
}

export function resourceYamlPut(type: ResourceType) {
  return async (request: NextRequest, context: Context) => clusterRoute(async () => {
    const auth = await requireWrite();
    if (auth instanceof NextResponse) return auth;
    if (!RESOURCE_CAPABILITIES[type].yamlEdit) return NextResponse.json({ error: "YAML editing is unavailable for this resource" }, { status: 405 });
    const { name, namespace } = target(type, await context.params);
    const body = await request.json();
    const yaml = validateResourceYaml(type, name, namespace, body?.yaml);
    const temporary = join(tmpdir(), `bortus-resource-${randomUUID()}.yaml`);
    try {
      await writeFile(temporary, yaml, { mode: 0o600 });
      await kubectlExec(["replace", "-f", temporary], 15000);
      invalidateCache();
      return NextResponse.json({ success: true }, { headers: { "Cache-Control": "no-store" } });
    } finally { await unlink(temporary).catch(() => {}); }
  });
}
