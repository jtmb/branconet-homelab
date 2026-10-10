import { z } from "zod";
import { KvError, type KvActor } from "./kv-contract";
import type { KvNativeEngine } from "./kv-native-engine";
import { dataChange, nativeDelete, nativeDestroy, nativeReconcile, nativeRollback } from "./kv-schemas";

const target = { pathId: z.string().uuid() };
export const automationRequest = z.discriminatedUnion("operation", [
  z.object({ operation: z.literal("status"), ...target }).strict(),
  z.object({ operation: z.literal("capabilities"), ...target }).strict(),
  z.object({ operation: z.literal("versions"), ...target }).strict(),
  z.object({ operation: z.literal("read"), ...target, version: z.number().int().positive().optional() }).strict(),
  dataChange.extend({ operation: z.literal("update"), ...target }).strict(),
  nativeDelete.extend({ operation: z.literal("delete"), ...target }).strict(),
  nativeDestroy.extend({ operation: z.literal("destroy"), ...target }).strict(),
  nativeRollback.extend({ operation: z.literal("rollback"), ...target }).strict(),
  nativeReconcile.extend({ operation: z.literal("reconcile"), ...target }).strict(),
  z.object({ operation: z.literal("resolve"), operationId: z.string().uuid() }).strict(),
]);

export async function runAutomation(engine: KvNativeEngine, actor: KvActor, input: z.infer<typeof automationRequest>) {
  if (!actor.identityId) throw new KvError(401, "KV automation identity required");
  switch (input.operation) {
    case "status": return engine.status(actor, input.pathId);
    case "capabilities": return engine.registry.capabilities(actor, input.pathId);
    case "versions": return engine.versions(actor, input.pathId);
    case "read": return engine.read(actor, input.pathId, input.version);
    case "update": return engine.change(actor, input.pathId, input);
    case "rollback": return engine.change(actor, input.pathId, input, "rollback");
    case "reconcile": return engine.change(actor, input.pathId, input, "reconcile");
    case "destroy": return engine.destroy(actor, input.pathId, input);
    case "delete": {
      const path = await engine.registry.path(input.pathId);
      if (input.confirmPath !== path.path) throw new KvError(400, "Exact logical path confirmation required");
      return engine.change(actor, input.pathId, input, "delete");
    }
    case "resolve": return engine.resolve(actor, input.operationId);
  }
}
