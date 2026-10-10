import { getSession } from "./auth";
import prisma from "./db";
import { KvRegistry } from "./kv-registry";
import { KV_BODY_BYTES, KvError, kvConfig, type KvActor } from "./kv-contract";
import { secretNamespaces } from "./secret-client";
import { secretErrorResponse, secretResponse } from "./secret-http";
import type { z } from "zod";

export function kvRegistry() { return new KvRegistry(prisma, secretNamespaces(), kvConfig()); }
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
    } catch (error) { return secretErrorResponse(error); }
  };
}

export async function kvBody<T>(request: Request, schema: z.ZodType<T>, maximum = KV_BODY_BYTES): Promise<T> {
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > maximum)) throw new KvError(413, "KV request exceeds the body limit");
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new KvError(400, "JSON request body required");
  if (!request.body) throw new KvError(400, "JSON request body required");
  const reader = request.body.getReader(), chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    while (true) {
      const next = await reader.read(); if (next.done) break;
      bytes += next.value.byteLength;
      if (bytes > maximum) { await reader.cancel(); throw new KvError(413, "KV request exceeds the body limit"); }
      chunks.push(next.value);
    }
    let value: unknown;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks))); }
    catch { throw new KvError(400, "Invalid KV JSON body"); }
    const parsed = schema.safeParse(value);
    if (!parsed.success) throw new KvError(400, "Invalid KV request fields");
    return parsed.data;
  } finally { reader.releaseLock(); }
}

export function metadataCursor(request: Request): string | undefined {
  const cursor = new URL(request.url).searchParams.get("cursor");
  if (cursor !== null && (!/^[A-Za-z0-9_-]{1,128}$/.test(cursor))) throw new KvError(400, "Invalid metadata cursor");
  return cursor ?? undefined;
}
