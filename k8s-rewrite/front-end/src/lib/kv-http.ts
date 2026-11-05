import { getSession } from "./auth";
import prisma from "./db";
import { KvRegistry } from "./kv-registry";
import { KV_BODY_BYTES, KV_ADMIN_METADATA_BODY_BYTES, KvError, KvMutationError, kvConfig, type KvActor } from "./kv-contract";
import { KvNativeEngine } from "./kv-native-engine";
import { createSecretTransport } from "./secret-client";
import { listAliases } from "./secret-references";
import { secretNamespaces } from "./secret-client";
import { secretErrorResponse, secretResponse } from "./secret-http";
import type { z } from "zod/v3";

export function kvRegistry() { return new KvRegistry(prisma, secretNamespaces(), kvConfig()); }
export function kvEngine(registry: KvRegistry) { return new KvNativeEngine(registry, createSecretTransport(), listAliases); }
export function kvErrorResponse(error: unknown) {
  return error instanceof KvMutationError ? secretResponse({ error: error.message, operationId: error.operationId, outcome: error.outcome }, error.status) : secretErrorResponse(error);
}
export function historyVersion(raw: string): number {
  if (!/^[1-9]\d{0,15}$/.test(raw) || !Number.isSafeInteger(Number(raw))) throw new KvError(400, "Invalid history version");
  return Number(raw);
}
type Context = { params: Promise<Record<string, string>> };
export function kvHuman(operation: (registry: KvRegistry, actor: KvActor, request: Request, params: Record<string, string>) => Promise<unknown>, status = 200) {
  return async (request: Request, context: Context) => {
    try {
      const actor = await getSession();
      if (!actor) throw new KvError(401, "Authentication required");
      const registry = kvRegistry();
      await registry.current(actor);
      const result = await operation(registry, actor, request, context?.params ? await context.params : {});
      return secretResponse(result ?? { success: true }, status);
    } catch (error) { return kvErrorResponse(error); }
  };
}

export async function kvBody<T>(request: Request, schema: z.ZodType<T>, maximum = KV_BODY_BYTES): Promise<T> {
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > maximum)) throw new KvError(413, "KV request exceeds the body limit");
  if (request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") throw new KvError(400, "JSON request body required");
  if (!request.body) throw new KvError(400, "JSON request body required");
  const reader = request.body.getReader(), chunks: Uint8Array[] = [];
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => { timer = setTimeout(() => { reject(new KvError(408, "KV request body timed out")); void reader.cancel().catch(() => {}); }, 20000); });
  let bytes = 0;
  try {
    while (true) {
      const next = await Promise.race([reader.read(), deadline]); if (next.done) break;
      bytes += next.value.byteLength;
      if (bytes > maximum || chunks.length >= 4096) { void reader.cancel().catch(() => {}); throw new KvError(413, "KV request exceeds the body limit"); }
      chunks.push(next.value);
    }
    let value: unknown;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks))); }
    catch { throw new KvError(400, "Invalid KV JSON body"); }
    const parsed = schema.safeParse(value);
    if (!parsed.success) throw new KvError(400, "Invalid KV request fields");
    return parsed.data;
  } finally { clearTimeout(timer); reader.releaseLock(); }
}

/** Policy/legacy metadata commits only. Authorization is checked before the larger read;
 * each commit still rechecks administration inside its serialized transaction. */
export async function kvAdminMetadataBody<T>(registry: KvRegistry, actor: KvActor, request: Request, schema: z.ZodType<T>): Promise<T> {
  await registry.admin(actor);
  return kvBody(request, schema, KV_ADMIN_METADATA_BODY_BYTES);
}

export function metadataCursor(request: Request): string | undefined {
  const cursor = new URL(request.url).searchParams.get("cursor");
  if (cursor !== null && (!/^[A-Za-z0-9_-]{1,128}$/.test(cursor))) throw new KvError(400, "Invalid metadata cursor");
  return cursor ?? undefined;
}
