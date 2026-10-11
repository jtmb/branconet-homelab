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
  constructor() { super(503, "Kubernetes Secret response exceeds the size limit"); }
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

    async function request(method: string, route: string, body?: unknown, deadline = Date.now() + 8000, metadata = false, byteLimit = 4 * 1024 * 1024, transferBudget?: SecretListBudget): Promise<{ value: any; bytes: number }> {
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
          const req = https.request(base + route, options, response => {
            // API errors/redirects can contain submitted values. Never read or forward those bodies.
            if (!response.statusCode || response.statusCode < 200 || response.statusCode >= 300) {
              response.destroy(); reject(secretFailure({ code: response.statusCode })); return;
            }
            const chunks: Buffer[] = []; let bytes = 0;
            response.on("data", (chunk: Buffer) => {
              bytes += chunk.length;
              // Count every delivered byte, including rejected/retried page prefixes, before buffering.
              try { transferBudget?.consumeBytes(chunk.length); }
              catch (error) { response.destroy(); reject(error); return; }
              if (bytes > Math.min(4 * 1024 * 1024, byteLimit)) { response.destroy(); reject(new SecretPageTooLarge()); return; }
              if (chunks.length >= 16384) { response.destroy(); reject(new SecretError(503, "Kubernetes Secret response exceeds the size limit")); return; }
              chunks.push(chunk);
            });
            response.once("error", reject);
            response.once("end", () => {
              try {
                const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
                if (!value || typeof value !== "object") throw Error();
                resolve({ value, bytes });
              } catch { reject(new SecretError(503, "Invalid Kubernetes Secret response")); }
            });
          });
          req.once("error", reject);
          if (serialized !== undefined) req.setHeader("Content-Length", Buffer.byteLength(serialized));
          req.end(serialized);
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
      list: async (namespace, options) => {
        const items: V1Secret[] = [], cursors = new Set<string>();
        const budget = options?.budget ?? new SecretListBudget(); let cursor = ""; let limit: number = initialListPageLimit;
        try { do {
          let result: { value: any; bytes: number };
          for (;;) {
            try {
              result = await request("GET", route(namespace) + "?limit=" + limit + (cursor ? "&continue=" + encodeURIComponent(cursor) : ""), undefined, budget.deadline, false, budget.remainingBytes(), budget);
              break;
            } catch (error) {
              if (!(error instanceof SecretPageTooLarge) || limit === 1) throw error;
              // Skip directly to the existing first fallback, avoiding another charged oversized prefix.
              // Keep the cursor and smaller limit: 200 (or compatibility 20) -> 10 -> 5 -> 2 -> 1.
              limit = limit === 200 ? 10 : Math.max(1, Math.floor(limit / 2)); budget.check();
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
