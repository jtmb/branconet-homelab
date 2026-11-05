import { nativeAsciiValueSpan } from "./secret-ascii-span";
import { KubeConfig, type V1ObjectMeta, type V1Secret } from "@kubernetes/client-node";
import https from "node:https";
import type { Agent as RequestAgent } from "node:http";
import { isDeepStrictEqual } from "node:util";
import { SecretStore, SecretError, secretFailure, validateTarget, SecretListBudget, SECRET_LIST_MAX_CONCURRENCY, type SecretTransport } from "./cluster-secrets";
import { kvConfig } from "./kv-contract";
import { KvRegistry } from "./kv-registry";
import { flatSecretGuard } from "./secret-access";
import { getSession } from "./auth";
import prisma from "./db";
import { parseSecretSummaryPage } from "./secret-summary-json";

export function secretNamespaces(): string[] {
  const scopes = (process.env.BORTUS_SECRET_NAMESPACES || "default").split(",").map(s => s.trim()).filter(Boolean);
  if (!scopes.length || scopes.length > 100) throw new SecretError(503, "Configure between one and 100 Secret namespaces");
  for (const namespace of scopes) validateTarget({ namespace, name: "scope", key: "scope" });
  return [...new Set(scopes)];
}
export interface NativeSecretTransport extends SecretTransport {
  delete(namespace: string, name: string, uid: string, resourceVersion: string): Promise<void>;
  probe(namespace: string, deadline?: number): Promise<void>;
  listMetadata(namespace: string): Promise<V1ObjectMeta[]>;
}
let active = 0;
const waiters: { enter: () => void; timer: ReturnType<typeof setTimeout> }[] = [];
async function slot(deadline: number, signal?: AbortSignal) {
  await new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(secretFailure(signal.reason));
    if (Date.now() >= deadline) return reject(new SecretError(503, "Kubernetes Secret request timed out"));
    if (active < 4) { active++; resolve(); return; }
    if (waiters.length >= 64) return reject(new SecretError(503, "Kubernetes Secret request queue is full"));
    const cleanup = () => { clearTimeout(waiter.timer); signal?.removeEventListener("abort", cancel); };
    const cancel = () => {
      cleanup(); const index = waiters.indexOf(waiter); if (index >= 0) waiters.splice(index, 1);
      reject(secretFailure(signal?.reason));
    };
    const waiter = { enter: () => {
      cleanup();
      if (signal?.aborted || Date.now() >= deadline) {
        reject(signal?.aborted ? secretFailure(signal.reason) : new SecretError(503, "Kubernetes Secret request timed out"));
        waiters.shift()?.enter(); return;
      }
      active++; resolve();
    }, timer: setTimeout(() => {
      cleanup();
      const index = waiters.indexOf(waiter); if (index >= 0) waiters.splice(index, 1);
      reject(new SecretError(503, "Kubernetes Secret request timed out"));
    }, Math.max(1, deadline - Date.now())) };
    waiters.push(waiter);
    signal?.addEventListener("abort", cancel, { once: true });
  });
}
const release = () => { active--; waiters.shift()?.enter(); };
export const nativeRequestDiagnostics = () => ({ active, queued: waiters.length, maxConcurrent: 4, maxQueued: 64 });

// Only a bounded full-list GET may retry this locally detected response ceiling.
class SecretPageTooLarge extends SecretError {
  constructor(readonly completedItems?: number) { super(503, "Kubernetes Secret response exceeds the size limit"); }
}

// An optional sizing hint, never inventory or authority: scan only existing bounded chunks.
// No decoding, concatenation, native string storage, partial objects or accepted items.
// Only literal known root headers are disambiguated. Nested member names are not compared.
export function rejectedSecretListItemCount(chunks: readonly Buffer[], limit: number): number | undefined {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 200) return;
  let length = 0;
  if (chunks.length > 16384) return;
  for (const chunk of chunks) { length += chunk.length; if (length > 4 * 1024 * 1024) return; }
  let chunkIndex = 0, offset = 0;
  const peek = (): number => {
    while (chunkIndex < chunks.length && offset === chunks[chunkIndex].length) { chunkIndex++; offset = 0; }
    return chunkIndex < chunks.length ? chunks[chunkIndex][offset] : -1;
  };
  const take = () => { const byte = peek(); if (byte >= 0) offset++; return byte; };
  const space = () => { for (;;) { const byte = peek(); if (byte !== 32 && byte !== 9 && byte !== 10 && byte !== 13) return; take(); } };
  const hex = (byte: number) => byte >= 48 && byte <= 57 || byte >= 65 && byte <= 70 || byte >= 97 && byte <= 102;
  // 1 complete, 0 valid unfinished prefix, -1 malformed/unavailable.
  const string = (): number => {
    if (take() !== 34) return -1;
    for (;;) {
      let byte = peek(); if (byte < 0) return 0;
      // Large native base64 strings usually stay in this direct, allocation-free ASCII loop.
      const chunk = chunks[chunkIndex];
      // Skip four unescaped ASCII string bytes at a time without decoding or
      // copying them. Zero-byte detection may stop early through a borrow, but
      // never skips a quote/backslash; the scalar grammar remains authoritative.
      while (offset + 4 <= chunk.length) {
        const word = chunk.readUInt32LE(offset);
        if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0)) break;
        const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
        if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 ||
          ((escape - 0x01010101) & ~escape & 0x80808080) !== 0) break;
        offset += 4;
      }
      while (offset < chunk.length && chunk[offset] >= 32 && chunk[offset] < 128 && chunk[offset] !== 34 && chunk[offset] !== 92) offset++;
      if (offset === chunk.length) continue;
      byte = take(); if (byte < 0) return 0; if (byte === 34) return 1;
      if (byte === 92) {
        const escaped = take(); if (escaped < 0) return 0;
        if (escaped === 117) { for (let i = 0; i < 4; i++) { const digit = take(); if (digit < 0) return 0; if (!hex(digit)) return -1; } }
        else if (escaped !== 34 && escaped !== 92 && escaped !== 47 && escaped !== 98 && escaped !== 102 && escaped !== 110 && escaped !== 114 && escaped !== 116) return -1;
      } else if (byte >= 128) {
        const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
        if (length < 0) return -1;
        for (let i = 0; i < length; i++) {
          const next = take(); if (next < 0) return 0;
          if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143)) return -1;
        }
      } else return -1;
    }
  };
  const longString = (): number => {
    if (take() !== 34) return -1;
    for (;;) {
      let byte = peek(); if (byte < 0) return 0;
      // Large native base64 strings usually stay in this direct, allocation-free ASCII loop.
      const chunk = chunks[chunkIndex];
      const advanced = nativeAsciiValueSpan(chunk, offset);
      if (advanced) { offset += advanced; continue; }
      // Skip four unescaped ASCII string bytes at a time without decoding or
      // copying them. Zero-byte detection may stop early through a borrow, but
      // never skips a quote/backslash; the scalar grammar remains authoritative.
      while (offset + 4 <= chunk.length) {
        const word = chunk.readUInt32LE(offset);
        if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0)) break;
        const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
        if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 ||
          ((escape - 0x01010101) & ~escape & 0x80808080) !== 0) break;
        offset += 4;
      }
      while (offset < chunk.length && chunk[offset] >= 32 && chunk[offset] < 128 && chunk[offset] !== 34 && chunk[offset] !== 92) offset++;
      if (offset === chunk.length) continue;
      byte = take(); if (byte < 0) return 0; if (byte === 34) return 1;
      if (byte === 92) {
        const escaped = take(); if (escaped < 0) return 0;
        if (escaped === 117) { for (let i = 0; i < 4; i++) { const digit = take(); if (digit < 0) return 0; if (!hex(digit)) return -1; } }
        else if (escaped !== 34 && escaped !== 92 && escaped !== 47 && escaped !== 98 && escaped !== 102 && escaped !== 110 && escaped !== 114 && escaped !== 116) return -1;
      } else if (byte >= 128) {
        const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
        if (length < 0) return -1;
        for (let i = 0; i < length; i++) {
          const next = take(); if (next < 0) return 0;
          if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143)) return -1;
        }
      } else return -1;
    }
  };
  const literal = (expected: string): number => {
    for (let i = 0; i < expected.length; i++) { const byte = take(); if (byte < 0) return 0; if (byte !== expected.charCodeAt(i)) return -1; }
    return 1;
  };
  const digit = (byte: number) => byte >= 48 && byte <= 57;
  const value = (depth: number): number => {
    if (depth > 32) return -1;
    space(); let byte = peek(); if (byte < 0) return 0;
    if (byte === 34) return chunks[chunkIndex].length - offset >= 4096 ? longString() : string();
    if (byte === 123 || byte === 91) {
      const object = byte === 123, end = object ? 125 : 93; take(); space();
      if (peek() === end) { take(); return 1; }
      for (;;) {
        if (peek() < 0) return 0;
        if (object) { const status = string(); if (status !== 1) return status; space(); byte = take(); if (byte < 0) return 0; if (byte !== 58) return -1; }
        const status = value(depth + 1); if (status !== 1) return status;
        space(); byte = take(); if (byte < 0) return 0; if (byte === end) return 1; if (byte !== 44) return -1; space();
      }
    }
    if (byte === 116) return literal("true"); if (byte === 102) return literal("false"); if (byte === 110) return literal("null");
    if (byte === 45) { take(); byte = peek(); if (byte < 0) return 0; }
    if (!digit(byte)) return -1;
    take(); if (byte !== 48) while (digit(peek())) take();
    if (peek() === 46) { take(); if (peek() < 0) return 0; if (!digit(peek())) return -1; while (digit(peek())) take(); }
    if (peek() === 101 || peek() === 69) { take(); if (peek() === 43 || peek() === 45) take(); if (peek() < 0) return 0; if (!digit(peek())) return -1; while (digit(peek())) take(); }
    return 1;
  };
  space(); if (take() !== 123) return;
  let seen = 0;
  for (;;) {
    space(); if (take() !== 34) return;
    // These constant public header names are the only strings compared or retained.
    let candidates = 15, length = 0;
    for (;;) {
      const byte = take(); if (byte === 34) break; if (byte < 0 || byte === 92) return;
      if ("apiVersion".charCodeAt(length) !== byte) candidates &= ~1;
      if ("kind".charCodeAt(length) !== byte) candidates &= ~2;
      if ("metadata".charCodeAt(length) !== byte) candidates &= ~4;
      if ("items".charCodeAt(length) !== byte) candidates &= ~8;
      if (!candidates) return; length++;
    }
    const key = length === 10 && candidates & 1 ? 1 : length === 4 && candidates & 2 ? 2 : length === 8 && candidates & 4 ? 4 : length === 5 && candidates & 8 ? 8 : 0;
    if (!key || seen & key) return; seen |= key;
    space(); if (take() !== 58) return; space();
    if (key === 8) {
      if ((seen & 3) !== 3 || take() !== 91) return;
      let count = 0;
      for (;;) {
        space(); const byte = peek(); if (byte < 0) return count > 0 ? count : undefined;
        if (byte !== 123 || count >= limit) return;
        const status = value(1); if (status !== 1) return status === 0 && count > 0 ? count : undefined;
        count++; space(); const next = take();
        if (next < 0) return count; if (next !== 44) return;
      }
    }
    const status = key === 1 ? literal('"v1"') : key === 2 ? literal('"SecretList"') : peek() === 123 ? value(1) : -1;
    if (status !== 1) return; space(); if (take() !== 44) return;
  }
}

export function createSecretTransport(initialListPageLimit: 20 | 200 = 20): NativeSecretTransport {
  try {
    if (initialListPageLimit !== 20 && initialListPageLimit !== 200)
      throw new SecretError(503, "Invalid Kubernetes Secret list page limit");
    const config = new KubeConfig();
    if (process.env.KUBECONFIG) config.loadFromDefault();
    else if (process.env.KUBERNETES_SERVICE_HOST) config.loadFromCluster();
    else config.loadFromDefault();
    const cluster = config.getCurrentCluster();
    if (!cluster || !cluster.server.startsWith("https:") || cluster.skipTLSVerify)
      throw new SecretError(503, "A TLS-verified Kubernetes API connection is required");
    const base = cluster.server.replace(/\/$/, "");
    const listAgents = new WeakMap<SecretListBudget, https.Agent>();
    const listAgent = (fresh: https.Agent, budget: SecretListBudget) => {
      // Proxy and client-certificate agents retain the SDK's fresh per-request behavior.
      // Authentication headers are never stored here; the SDK still refreshes every request.
      if (cluster.proxyUrl || fresh.constructor !== https.Agent ||
        [fresh.options.cert, fresh.options.key, fresh.options.pfx, fresh.options.passphrase].some(value => value !== undefined && value !== null)) return fresh;
      const current = listAgents.get(budget);
      if (current) {
        if (!isDeepStrictEqual(current.options, fresh.options)) return fresh;
        fresh.destroy(); return current;
      }
      Object.assign(fresh, { keepAlive: true, maxSockets: 4, maxTotalSockets: 4, maxFreeSockets: 4 });
      listAgents.set(budget, fresh);
      const timer = setTimeout(() => budget.fail(new SecretError(503, "Kubernetes Secret list timed out")), Math.max(1, budget.deadline - Date.now()));
      timer.unref();
      const cleanup = () => { clearTimeout(timer); listAgents.delete(budget); fresh.destroy(); };
      try { budget.onFinish(cleanup); }
      catch (error) { cleanup(); throw error; }
      return fresh;
    };

    async function request(method: string, route: string, body?: unknown, deadline = Date.now() + 8000, metadata = false, byteLimit = 4 * 1024 * 1024, transferBudget?: SecretListBudget, retryPageLimit?: number, summaryNamespace?: string): Promise<{ value: any; bytes: number }> {
      deadline = Math.min(deadline, Date.now() + 8000);
      transferBudget?.check();
      await slot(deadline, transferBudget?.signal);
      let authTimer: ReturnType<typeof setTimeout> | undefined;
      let authAbort: (() => void) | undefined;
      let ownedAgent: RequestAgent | undefined;
      let authenticatedOptions: https.RequestOptions | undefined;
      let finished = false;
      try {
        transferBudget?.check();
        const options: https.RequestOptions = { method, rejectUnauthorized: true, headers: {
          Accept: metadata ? "application/json;as=PartialObjectMetadataList;g=meta.k8s.io;v=v1" : "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        } };
        authenticatedOptions = options;
        // SDK authentication retains CA/client certificates, token refresh and proxies; JSON maps bypass its lossy serializer.
        const captureAgent = () => {
          const agent = options.agent;
          if (agent && typeof agent === "object") {
            ownedAgent = agent;
            // SDK authentication cannot be aborted; late completion must never open or retain a connection.
            if (finished) agent.destroy();
          }
        };
        const authentication = config.applyToHTTPSOptions(options).then(captureAgent, error => { captureAgent(); throw error; });
        await Promise.race([authentication, new Promise<never>((_, reject) => {
          authTimer = setTimeout(() => reject(new SecretError(503, "Kubernetes Secret authentication timed out")), Math.max(1, deadline - Date.now()));
          if (transferBudget) {
            authAbort = () => reject(secretFailure(transferBudget.signal.reason));
            transferBudget.signal.addEventListener("abort", authAbort, { once: true });
          }
        })]);
        clearTimeout(authTimer);
        if (authAbort) transferBudget?.signal.removeEventListener("abort", authAbort);
        transferBudget?.check();
        if (Date.now() >= deadline || options.rejectUnauthorized === false) throw new SecretError(503, "Kubernetes Secret request timed out");
        const fresh = options.agent;
        if (fresh instanceof https.Agent) {
          options.agent = transferBudget ? listAgent(fresh, transferBudget) : fresh;
          if (transferBudget && options.agent === fresh && fresh === listAgents.get(transferBudget)) ownedAgent = undefined;
        }
        const timeout = AbortSignal.timeout(Math.max(1, deadline - Date.now()));
        options.signal = transferBudget ? AbortSignal.any([timeout, transferBudget.signal]) : timeout;
        const serialized = body === undefined ? undefined : JSON.stringify(body);
        if (serialized && Buffer.byteLength(serialized) > 900 * 1024) throw new SecretError(413, "Secret object exceeds the application size limit");
        return await new Promise((resolve, reject) => {
          const chunks: Buffer[] = []; let settled = false;
          const fail = (error: unknown) => {
            if (settled) return;
            settled = true; chunks.length = 0; options.signal?.removeEventListener("abort", abort); reject(error);
          };
          const abort = () => fail(secretFailure(options.signal?.reason));
          const req = https.request(base + route, options, response => {
            // API errors/redirects can contain submitted values. Never read or forward those bodies.
            if (!response.statusCode || response.statusCode < 200 || response.statusCode >= 300) {
              fail(secretFailure({ code: response.statusCode })); response.destroy(); return;
            }
            let bytes = 0;
            response.on("data", (chunk: Buffer) => {
              bytes += chunk.length;
              // Count every delivered byte, including rejected/retried page prefixes, before buffering.
              try { transferBudget?.consumeBytes(chunk.length); }
              catch (error) { fail(error); response.destroy(); return; }
              if (settled) return;
              if (bytes > Math.min(4 * 1024 * 1024, byteLimit)) {
                try {
                  const count = retryPageLimit !== undefined && byteLimit >= 4 * 1024 * 1024 ? rejectedSecretListItemCount(chunks, retryPageLimit) : undefined;
                  transferBudget?.check();
                  if (Date.now() >= deadline) throw new SecretError(503, "Kubernetes Secret request timed out");
                  if (options.signal?.aborted) throw secretFailure(options.signal.reason);
                  fail(new SecretPageTooLarge(count));
                } catch (error) { fail(error); }
                response.destroy(); return;
              }
              if (chunks.length >= 16384) { fail(new SecretError(503, "Kubernetes Secret response exceeds the size limit")); response.destroy(); return; }
              chunks.push(chunk);
            });
            response.once("error", fail);
            response.once("end", () => {
              if (settled) return;
              try {
                transferBudget?.check();
                if (Date.now() >= deadline) throw new SecretError(503, "Kubernetes Secret request timed out");
                if (options.signal?.aborted) throw secretFailure(options.signal.reason);
                const value = summaryNamespace !== undefined && retryPageLimit !== undefined
                  ? parseSecretSummaryPage(chunks, summaryNamespace, retryPageLimit)
                  : JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
                if (!value || typeof value !== "object") throw Error();
                transferBudget?.check();
                if (Date.now() >= deadline) throw new SecretError(503, "Kubernetes Secret request timed out");
                if (options.signal?.aborted) throw secretFailure(options.signal.reason);
                settled = true; chunks.length = 0; options.signal?.removeEventListener("abort", abort);
                resolve({ value, bytes });
              } catch (error) { fail(error instanceof SecretError ? error : new SecretError(503, "Invalid Kubernetes Secret response")); }
            });
          });
          req.once("error", fail);
          if (!settled) options.signal?.addEventListener("abort", abort, { once: true });
          if (options.signal?.aborted) abort();
          try {
            if (serialized !== undefined) req.setHeader("Content-Length", Buffer.byteLength(serialized));
            req.end(serialized);
          } catch (error) { fail(error); }
        });
      } catch (error) { throw secretFailure(error); }
      finally {
        finished = true; clearTimeout(authTimer); if (authAbort) transferBudget?.signal.removeEventListener("abort", authAbort);
        ownedAgent?.destroy();
        const agent = authenticatedOptions?.agent;
        if (agent && typeof agent === "object" && (!transferBudget || agent !== listAgents.get(transferBudget))) agent.destroy();
        release();
      }
    }
    const route = (namespace: string, name?: string) => {
      validateTarget({ namespace, name: name || "scope", key: "scope" });
      return `/api/v1/namespaces/${namespace}/secrets${name ? "/" + name : ""}`;
    };
    const object = (value: any, namespace: string, name?: string): V1Secret => {
      if (value.kind !== "Secret" || value.apiVersion !== "v1" || value.metadata?.namespace !== namespace ||
        (name && value.metadata?.name !== name) || typeof value.metadata?.name !== "string" ||
        (value.data !== undefined && (!value.data || typeof value.data !== "object" || Array.isArray(value.data) || Object.values(value.data).some(v => typeof v !== "string"))))
        throw new SecretError(503, "Invalid Kubernetes Secret response");
      return value as V1Secret; // JSON.parse retains __proto__/constructor/toString and arbitrary native metadata.
    };
    return {
      read: async (namespace, name) => object((await request("GET", route(namespace, name))).value, namespace, name),
      listSummaries: async (namespace, options) => {
        const items: Awaited<ReturnType<NonNullable<NativeSecretTransport["listSummaries"]>>> = [], cursors = new Set<string>();
        const budget = options?.budget ?? new SecretListBudget(); let cursor = "", limit: number = initialListPageLimit;
        try {
          do {
            let result: { value: any; bytes: number };
            for (;;) {
              try {
                result = await request("GET", route(namespace) + "?limit=" + limit + (cursor ? "&continue=" + encodeURIComponent(cursor) : ""), undefined, budget.deadline, false, budget.remainingBytes(), budget, limit, namespace);
                break;
              } catch (error) {
                if (!(error instanceof SecretPageTooLarge) || limit === 1) throw error;
                const fallback = limit === 200 ? 10 : Math.max(1, Math.floor(limit / 2));
                limit = Math.min(fallback, error.completedItems ?? fallback); budget.check();
              }
            }
            const page = result.value as ReturnType<typeof parseSecretSummaryPage>;
            budget.consumeItems(page.items.length);
            for (const summary of page.items) { if (options?.visit) options.visit(summary); else items.push(summary); }
            cursor = page.cursor;
            if (cursor && (cursors.has(cursor) || !page.items.length)) throw new SecretError(503, "Invalid Kubernetes Secret pagination");
            if (cursor) cursors.add(cursor);
          } while (cursor);
          return items;
        } finally { if (!options?.budget) budget.finish(); }
      },
      list: async (namespace, options) => {
        const items: V1Secret[] = [], cursors = new Set<string>();
        const budget = options?.budget ?? new SecretListBudget(); let cursor = ""; let limit: number = initialListPageLimit;
        try { do {
          let result: { value: any; bytes: number };
          for (;;) {
            try {
              result = await request("GET", route(namespace) + "?limit=" + limit + (cursor ? "&continue=" + encodeURIComponent(cursor) : ""), undefined, budget.deadline, false, budget.remainingBytes(), budget, limit);
              break;
            } catch (error) {
              if (!(error instanceof SecretPageTooLarge) || limit === 1) throw error;
              // A scalar rejected-prefix hint can only reduce the existing fallback, never accept items.
              const fallback = limit === 200 ? 10 : Math.max(1, Math.floor(limit / 2));
              limit = Math.min(fallback, error.completedItems ?? fallback); budget.check();
            }
          }
          const page = result.value;
          if (page.kind !== "SecretList" || page.apiVersion !== "v1" || !Array.isArray(page.items) || page.items.length > limit)
            throw new SecretError(503, "Kubernetes Secret list exceeds the validated limits");
          budget.consumeItems(page.items.length);
          for (const raw of page.items) {
            const item = object(raw, namespace);
            if (options?.visit) options.visit(item); else items.push(item);
          }
          cursor = page.metadata?.continue || "";
          if (typeof cursor !== "string" || cursor.length > 8192 || (cursor && (cursors.has(cursor) || page.items.length === 0)))
            throw new SecretError(503, "Invalid Kubernetes Secret pagination");
          if (cursor) cursors.add(cursor);
        } while (cursor);
        return items;
        } finally { if (!options?.budget) budget.finish(); }
      },
      create: async (namespace, body) => object((await request("POST", route(namespace), body)).value, namespace, body.metadata?.name),
      replace: async (namespace, name, body) => object((await request("PUT", route(namespace, name), body)).value, namespace, name),
      delete: async (namespace, name, uid, resourceVersion) => {
        if (!uid || !resourceVersion) throw new SecretError(428, "Owned history UID and resourceVersion required");
        await request("DELETE", route(namespace, name), { apiVersion: "v1", kind: "DeleteOptions", preconditions: { uid, resourceVersion } });
      },
      listMetadata: async namespace => {
        const items: V1ObjectMeta[] = [], cursors = new Set<string>();
        const deadline = Date.now() + 15000; let cursor = "", bytes = 0;
        do {
          const result = await request("GET", route(namespace) + "?limit=100" + (cursor ? "&continue=" + encodeURIComponent(cursor) : ""), undefined, deadline, true);
          const page = result.value; bytes += result.bytes;
          if (page.kind !== "PartialObjectMetadataList" || page.apiVersion !== "meta.k8s.io/v1" || !Array.isArray(page.items) ||
            page.items.length > 100 || items.length + page.items.length > 10000 || bytes > 8 * 1024 * 1024)
            throw new SecretError(503, "Metadata-only Secret list exceeds the validated limits");
          for (const item of page.items) {
            if (item.kind !== "PartialObjectMetadata" || item.apiVersion !== "meta.k8s.io/v1" || Object.hasOwn(item, "data") || Object.hasOwn(item, "stringData") ||
              item.metadata?.namespace !== namespace || typeof item.metadata?.name !== "string")
              throw new SecretError(503, "Invalid metadata-only Secret response");
            validateTarget({ namespace, name: item.metadata.name, key: "validation" });
            items.push(item.metadata);
          }
          cursor = page.metadata?.continue || "";
          if (typeof cursor !== "string" || cursor.length > 8192 || cursor && (cursors.has(cursor) || !page.items.length))
            throw new SecretError(503, "Invalid Kubernetes Secret pagination");
          if (cursor) cursors.add(cursor);
        } while (cursor);
        return items;
      },
      probe: async (namespace, deadline = Date.now() + 8000) => {
        const { value } = await request("GET", route(namespace) + "?limit=1", undefined, deadline, true);
        if (value.kind !== "PartialObjectMetadataList" || value.apiVersion !== "meta.k8s.io/v1" || !Array.isArray(value.items) || value.items.length > 1 ||
          value.items.some((i: any) => i.kind !== "PartialObjectMetadata" || i.apiVersion !== "meta.k8s.io/v1" || i.metadata?.namespace !== namespace || Object.hasOwn(i, "data") || Object.hasOwn(i, "stringData")))
          throw new SecretError(503, "Metadata-only Secret probe unavailable");
      },
    };
  } catch (error) { throw secretFailure(error); }
}
export function nativeSecrets(legacyAlias?: string) {
  const config = kvConfig(), namespaces = secretNamespaces().filter(ns => ns !== config.historyNamespace), transport = createSecretTransport(200);
  return new SecretStore(transport, namespaces, flatSecretGuard(new KvRegistry(prisma, namespaces, config), transport, getSession, legacyAlias), SECRET_LIST_MAX_CONCURRENCY);
}
