import { kvBody, kvEngine, kvErrorResponse, kvRegistry } from "@/lib/kv-http";
import { automationRequest, runAutomation } from "@/lib/kv-automation";
import { secretResponse } from "@/lib/secret-http";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    const registry = kvRegistry(), actor = await registry.authenticateIdentity(request.headers.get("authorization"));
    return secretResponse(await runAutomation(kvEngine(registry), actor, await kvBody(request, automationRequest)));
  } catch (error) { return kvErrorResponse(error); }
}
