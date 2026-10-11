import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { mkdtemp, writeFile, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer, request as forward, type Server } from "node:http";
import { once } from "node:events";
import { randomBytes } from "node:crypto";
import { PrismaClient } from "@prisma/client";
import { SignJWT } from "jose";
import { fakeKubectl } from "./helpers/fake-kubectl";
import { nativeTlsFixture } from "./helpers/native-tls";

async function port() {
  const holder = createServer();
  holder.listen(0, "127.0.0.1"); await once(holder, "listening");
  const number = (holder.address() as { port: number }).port;
  await new Promise<void>(resolve => holder.close(() => resolve()));
  return number;
}
async function main() {
const root = process.cwd();
const dir = await mkdtemp(path.join(tmpdir(), "bortus-ui-test-"));
const servers: Server[] = [];
const requestCounts = new Map<string, number>();
let activeStreams = 0;
let child: ChildProcess | undefined;
let db: PrismaClient | undefined;
let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
let delayedReveal = false;
let valueRequests = 0;
let failKvMounts = false;
let failKvStatus = false;
let delayKvStatus = false;
let delayedKvStatusPath: string | undefined;
let releaseKvStatus: (() => void) | undefined;
let delayKvCapabilities = false;
let releaseKvCapabilities: (() => void) | undefined;
const kvFixture = process.env.BORTUS_UI_KV_FIXTURE === "true";
const fluxFixture = process.env.BORTUS_UI_FLUX_FIXTURE === "true";
const fluxHolds = new Set<string>(), fluxFailures = new Set<string>();
const fluxReleases = new Map<string, () => void>();
const activeFlux = new Map<string, number>(), maxActiveFlux = new Map<string, number>();
const fluxReadEvents: { id: number; key: string; event: string; at: number; active: number; writableFinished?: boolean }[] = [];
let nextFluxRead = 0, droppedFluxEvents = 0;
function fluxReadEvent(event: typeof fluxReadEvents[number]) {
  if (fluxReadEvents.length < 2000) fluxReadEvents.push(event); else droppedFluxEvents++;
}
const guardedKvFixture = kvFixture && process.env.BORTUS_UI_KV_GUARDED_FIXTURE === "true";
const fixtureMountId = "10000000-0000-4000-8000-000000000000", fixturePathId = "20000000-0000-4000-8000-000000000000";
try {
  const fixture = await fakeKubectl(dir);
  const created = "2026-10-01T00:00:00Z";
  const pod = (name: string, namespace: string, restarts: number) => ({
    apiVersion: "v1", kind: "Pod", metadata: { name, namespace, uid: name, creationTimestamp: created, labels: { app: "fixture", tier: "front" } },
    spec: { nodeName: "fixture-node", containers: [{ name: "app", image: "example.invalid/fixture:v1" }] },
    status: { phase: "Running", podIP: "10.0.0.1", containerStatuses: [{ name: "app", ready: true, restartCount: restarts }] },
  });
  const data = {
    nodes: { items: [{ metadata: { name: "fixture-node", uid: "node-one", creationTimestamp: created }, status: { capacity: { cpu: "250m", memory: "2Gi" }, conditions: [{ type: "Ready", status: "True" }], nodeInfo: { kubeletVersion: "v1.34.1" }, addresses: [{ type: "InternalIP", address: "10.0.0.2" }] } }] },
    pods: { items: [pod("sort-fixture-12", "kube-system", 12), pod("sort-fixture-2", "apps", 2), pod("sort-fixture-7", "apps", 7),
      ...Array.from({ length: 205 }, (_, index) => pod("large-pod-" + index, "apps", index))] },
    namespaces: { items: [{ metadata: { name: "apps", creationTimestamp: created }, status: { phase: "Active" } }] },
    deployments: { items: [{ apiVersion: "apps/v1", kind: "Deployment", metadata: { name: "scaled-zero", namespace: "apps", uid: "dep-one", generation: 1 }, spec: { replicas: 0 }, status: { observedGeneration: 1 } }] },
    replicasets: { items: [] }, services: { items: [] }, ingress: { items: [] },
    pvc: { items: [{ metadata: { name: "fixture-claim", namespace: "apps", uid: "claim-one" }, spec: { resources: { requests: { storage: "512Mi" } } }, status: { phase: "Bound" } }] },
    pv: { items: [] }, sc: { items: [] }, "volumes.longhorn.io": { items: [] },
  };
  for (const [resource, body] of Object.entries(data)) await writeFile(path.join(fixture.bin, resource + ".json"), JSON.stringify(body));
  if (fluxFixture) {
    const repositories = Array.from({ length: 201 }, (_, index) => ({
      apiVersion: "source.toolkit.fluxcd.io/v1", kind: "GitRepository",
      metadata: { name: index < 5 ? `sort-repo-${index}` : `fixture-repo-${String(index).padStart(4, "0")}`, namespace: "flux-system", uid: `fixture-source-${index}`, resourceVersion: "17", creationTimestamp: created },
      spec: { url: "https://example.invalid/" + "repository-path-".repeat(12) + "repo.git", ref: { branch: "long-branch-".repeat(20) } },
      status: { lastHandledReconcileAt: index === 1 ? null : index === 2 ? "invalid-date" : index === 4 ? "2025-01-01T00:00:00Z" : created, artifact: { revision: index === 1 ? null : `main:fixture-${index}` }, conditions: [{ type: "Ready", status: "True" }] },
    }));
    const inventory = (count: number) => ({ entries: Array.from({ length: count }, (_, index) => ({ id: `apps_fixture-deployment-${String(index).padStart(4, "0")}_apps_Deployment`, v: "v1" })) });
    const bundles = Array.from({ length: 201 }, (_, index) => ({ apiVersion: "kustomize.toolkit.fluxcd.io/v1", kind: "Kustomization",
      metadata: { name: `fixture-bundle-${String(index).padStart(4, "0")}`, namespace: "flux-system", uid: `fixture-bundle-uid-${index}`, resourceVersion: "1", creationTimestamp: created },
      spec: { sourceRef: { kind: "GitRepository", name: "sort-repo-0" }, path: "./" + "long-path/".repeat(30), targetNamespace: "apps" },
      status: { lastHandledReconcileAt: created, conditions: [{ type: "Ready", status: "True" }], inventory: inventory(index === 0 ? 201 : index === 1 ? 2 : index === 2 ? 10 : 12) },
    }));
    for (const [resource, body] of Object.entries({ gitrepositories: { items: repositories }, gitrepository: repositories[0], kustomizations: { items: bundles }, kustomization: bundles[0], helmreleases: { items: [] }, events: { items: [] } }))
      await writeFile(path.join(fixture.bin, resource + ".json"), JSON.stringify(body));
    await writeFile(path.join(fixture.bin, "allow-flux-sync"), "synthetic annotation success only");
    await writeFile(path.join(fixture.bin, "allow-flux-mutations"), "synthetic Flux CRD mutation success only");
  }
  await writeFile(path.join(fixture.bin, "pv-table.txt"), "fixture-volume Retain Bound fixture-storage 512Mi fixture-claim " + created + "\n");
  const database = "file:" + path.join(dir, "ui.db").replaceAll("\\", "/");
  const kubeconfig = path.join(dir, "config.json");
  await writeFile(kubeconfig, JSON.stringify({ apiVersion: "v1", kind: "Config", clusters: [{ name: "fixture", cluster: { server: "https://127.0.0.1:1" } }], users: [{ name: "fixture", user: {} }], contexts: [{ name: "fixture", context: { cluster: "fixture", user: "fixture" } }], "current-context": "fixture" }));
  if (process.env.BORTUS_UI_NATIVE_FIXTURE === "true") {
    native = await nativeTlsFixture(dir);
    native.seed("apps", "editor-fixture", { editable: Buffer.from("fixture initial native value").toString("base64"), unrelated: Buffer.from("fixture unrelated native value").toString("base64") },
      { metadata: { labels: { fixture: "retained" }, annotations: { "fixture-private": "fixture annotation value" } } });
    if (process.env.BORTUS_UI_SECRET_TABLE_FIXTURE === "true") {
      const encoded = Buffer.from("fixture table private value").toString("base64");
      for (let index = 0; index < 327; index++) native.seed("apps", "large-secret-" + String(index).padStart(4, "0"), { original_under_scored_key: encoded });
      native.seed("apps", "many-keys-fixture", Object.fromEntries(["__proto__", "constructor", "toString",
        ...Array.from({ length: 600 }, (_, index) => "original_under_scored_key_" + String(index).padStart(4, "0"))].map(key => [key, encoded])));
      for (const [name, count] of [["two", 2], ["seven", 7], ["twelve", 12]] as const) native.seed("apps", "count-fixture-" + name,
        Object.fromEntries(Array.from({ length: count }, (_, index) => ["key_" + index, encoded])));
      native.seed("apps", "empty-keys-fixture", {});
      native.seed("apps", "immutable-fixture", { original_under_scored_key: encoded }, { immutable: true });
    }
  }
  const clean = Object.fromEntries(["SystemRoot", "WINDIR", "COMSPEC", "PATH", "TEMP", "TMP", "USERPROFILE", "HOME", "SystemDrive", "APPDATA", "LOCALAPPDATA"].filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
  const signing = randomBytes(48).toString("hex");
  const env = { ...clean, ...fixture.env, DATABASE_URL: database, BOTRUS_JWT_SECRET: signing, BOTRUS_SECRETS_KEY: randomBytes(32).toString("hex"), KUBECONFIG: native?.config ?? kubeconfig,
    BORTUS_SECRET_NAMESPACES: "apps", BORTUS_DISABLE_PROVISIONING: "true", BORTUS_KV_GUARDED_ADOPTION: guardedKvFixture ? "true" : "false", NODE_ENV: "production" as const, HOSTNAME: "127.0.0.1", PORT: String(await port()) };
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
  db = new PrismaClient({ datasources: { db: { url: database } } });
  const writer = await db.user.create({ data: { username: "fixture_writer", passwordHash: "unused", role: "write", engineAdmin: true } });
  const reader = await db.user.create({ data: { username: "fixture_reader", passwordHash: "unused", role: "readonly" } });
  const scoped = await db.user.create({ data: { username: "fixture_scoped", passwordHash: "unused", role: "write", engineAdmin: false } });
  if (kvFixture) {
    if (!native) throw new Error("KV UI fixture requires BORTUS_UI_NATIVE_FIXTURE=true");
    await db.kvMount.createMany({ data: Array.from({ length: 205 }, (_, index) => ({ id: "10000000-0000-4000-8000-" + String(index).padStart(12, "0"), name: index ? "mount-" + String(index).padStart(4, "0") : "services", namespaces: JSON.stringify(["apps"]) })) });
    for (let index = 0; index < 205; index++) {
      const count = [3, 2, 7, 12][index] ?? 1, name = "kv-fixture-" + String(index).padStart(4, "0");
      const fields = Array.from({ length: count }, (_, key) => ({ field: index === 0 ? ["__proto__", "constructor", "toString"][key] : "field_" + key, key: index === 0 ? ["__proto__", "constructor", "toString"][key] : "original_under_scored_key_" + key }));
      native.seed("apps", name, Object.fromEntries([...fields.map((item, key) => [item.key, index === 0 && key === 1 ? Buffer.from([0, 255]).toString("base64") : index === 0 && key === 2 ? "" : Buffer.from("fixture KV private value").toString("base64")]), ...(index === 0 ? [["unrelated_native_key", Buffer.from("fixture unrelated native value").toString("base64")]] : [])]),
        index === 0 ? { type: "Opaque", metadata: { labels: { fixture: "retained" }, annotations: { "fixture-private": "fixture annotation value" } } } : {});
      await db.kvPath.create({ data: { id: "20000000-0000-4000-8000-" + String(index).padStart(12, "0"), mountId: fixtureMountId,
        path: index === 0 ? "services/api" : index === 1 ? "services/apiculture" : index === 4 ? "services/api/denied" : "services/service-" + String(index).padStart(4, "0"), namespace: "apps", name, retention: [2, 7, 12][index] ?? 20,
        fields: { create: fields.map(item => ({ ...item, namespace: "apps", name })) } } });
    }
    const actions = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"];
    await db.kvPolicy.createMany({ data: [
      { principal: "user:" + writer.id, prefix: "", effect: "allow", actions: JSON.stringify(actions) },
      { principal: "user:" + reader.id, prefix: "", effect: "allow", actions: JSON.stringify(["list"]) },
      { principal: "user:" + scoped.id, mountId: fixtureMountId, prefix: "services/api", effect: "allow", actions: JSON.stringify(["list", "read", "update", "create"]) },
      { principal: "user:" + scoped.id, mountId: fixtureMountId, prefix: "services/api/denied", effect: "deny", actions: JSON.stringify(actions) },
    ] });
    if (guardedKvFixture) await db.kvPath.create({ data: { id: "30000000-0000-4000-8000-000000000000", mountId: fixtureMountId, path: "services/new-empty", namespace: "apps", name: "kv-ui-new-empty", retention: 20,
      fields: { create: [{ field: "empty", key: "empty", namespace: "apps", name: "kv-ui-new-empty" }] } } });
  }
  await db.user.createMany({ data: Array.from({ length: 205 }, (_, index) => ({ username: "large_user_" + index, passwordHash: "unused", role: "readonly" })) });
  await db.variable.createMany({ data: Array.from({ length: 205 }, (_, index) => ({ key: "fixture_config_" + index, value: "nonsecret " + index, category: "fixture", encrypted: false })) });
  await db.appSetting.create({ data: { key: "allow_registration", value: "false" } });
  await db.secretReference.createMany({ data: Array.from({ length: 603 }, (_, index) => ({
    alias: "fixture_alias_" + String(index).padStart(4, "0"), namespace: "apps", name: "fixture-secret", key: "key_" + index,
  })) });
  await db.job.createMany({ data: [
    { id: "completed-ui-job", playbook: "fixture.yml", status: "success", output: "🌍 fixture captured output\n".repeat(10000) },
    { id: "running-ui-job", playbook: "fixture.yml", status: "running", output: "fixture running output\n" },
  ] });
  const token = (user: typeof writer) => new SignJWT({ sub: user.id, username: user.username, sessionVersion: user.sessionVersion }).setProtectedHeader({ alg: "HS256" }).setIssuedAt().setExpirationTime("1h").sign(new TextEncoder().encode(signing));
  const origin = "http://127.0.0.1:" + env.PORT;
  child = spawn(process.execPath, [path.resolve(".next/standalone/server.js")], { env, stdio: ["ignore", "pipe", "pipe"] });
  let output = "";
  child.stdout?.on("data", chunk => { output = (output + chunk).slice(-65536); });
  child.stderr?.on("data", chunk => { output = (output + chunk).slice(-65536); });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error("Disposable UI server exited");
    try { if ((await fetch(origin + "/api/health/live", { signal: AbortSignal.timeout(500) })).ok) { ready = true; break; } } catch { /* startup */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!ready) throw new Error("Disposable UI server did not become ready");
  async function gateway(credential: string) {
    const server = createServer(async (request, response) => {
      const url = new URL(request.url ?? "/", origin);
      if (url.pathname === "/__fixture/status") {
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ requests: Object.fromEntries(requestCounts), activeStreams, valueRequests, nativeObjects: native?.objects.size ?? 0, pendingKvStatus: !!releaseKvStatus, pendingKvCapabilities: !!releaseKvCapabilities,
          heldFluxReplies: [...fluxReleases.keys()], activeFluxReads: Object.fromEntries(activeFlux), maxActiveFluxReads: Object.fromEntries(maxActiveFlux), fluxReadEvents, droppedFluxEvents }));
        return;
      }
      if (fluxFixture && url.pathname === "/__fixture/flux-control" && request.method === "POST") {
        let raw = ""; for await (const chunk of request) { raw += chunk; if (raw.length > 1024) { response.writeHead(413); response.end(); return; } }
        const action = JSON.parse(raw).action;
        if (action === "withdraw-admin" || action === "restore-admin") await db!.user.update({ where: { id: writer.id }, data: { engineAdmin: action === "restore-admin" } });
        else if (action === "hold-hierarchy") fluxHolds.add("hierarchy");
        else if (action === "hold-progress") fluxHolds.add("progress");
        else if (action === "hold-sync") fluxHolds.add("sync");
        else if (action === "hold-removal") fluxHolds.add("removal");
        else if (action === "release-replies") for (const release of [...fluxReleases.values()]) release();
        else if (action === "fail-hierarchy" || action === "restore-hierarchy") { if (action === "fail-hierarchy") fluxFailures.add("hierarchy"); else fluxFailures.delete("hierarchy"); }
        else if (action === "hold-discovery") await writeFile(path.join(fixture.bin, "hold-flux-discovery"), "synthetic bounded discovery hold");
        else if (action === "release-discovery") await rm(path.join(fixture.bin, "hold-flux-discovery"), { force: true });
        else { response.writeHead(400); response.end(); return; }
        response.writeHead(204); response.end(); return;
      }
      if (native && url.pathname === "/__fixture/native-status") {
        const object = native.objects.get("apps/editor-fixture");
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ reads: native.calls.filter(call => call.method === "GET" && call.path.endsWith("/editor-fixture")).length,
          writes: native.calls.filter(call => call.method === "PUT" || call.method === "POST" || call.method === "DELETE").length,
          objectRetained: !!object, editablePresent: Object.hasOwn(object?.data ?? {}, "editable"), editableEmpty: object?.data?.editable === "",
          unrelatedPreserved: object?.data?.unrelated === Buffer.from("fixture unrelated native value").toString("base64"),
          metadataPreserved: object?.metadata?.labels?.fixture === "retained" && object.metadata.annotations?.["fixture-private"] === "fixture annotation value" }));
        return;
      }
      if (kvFixture && native && url.pathname === "/__fixture/kv-status") {
        const object = native.objects.get("apps/kv-fixture-0000"), state = JSON.parse(object?.metadata?.annotations?.["bortus.io/kv-state"] ?? '{"paths":[]}');
        const ownValues = new Map(Object.entries(object?.data ?? {}));
        const selected = state.paths.find((item: { id: string }) => item.id === fixturePathId);
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ head: selected?.head ?? 0, tombstone: selected?.tombstone ?? false, committedVersions: selected?.versions.length ?? 0,
          binaryOriginalPreserved: ownValues.get("constructor") === Buffer.from([0, 255]).toString("base64"), emptyOriginalPreserved: ownValues.get("toString") === "",
          unrelatedPreserved: object?.data?.unrelated_native_key === Buffer.from("fixture unrelated native value").toString("base64"),
          metadataPreserved: object?.metadata?.labels?.fixture === "retained" && object.metadata.annotations?.["fixture-private"] === "fixture annotation value", typePreserved: object?.type === "Opaque" }));
        return;
      }
      if (native && url.pathname === "/__fixture/native-control" && request.method === "POST") {
        let raw = ""; for await (const chunk of request) { raw += chunk; if (raw.length > 1024) { response.writeHead(413); response.end(); return; } }
        const action = JSON.parse(raw).action;
        if (action === "delay-reveal") delayedReveal = true;
        else if (action === "withdraw-admin" || action === "restore-admin") await db!.user.update({ where: { id: writer.id }, data: { engineAdmin: action === "restore-admin" } });
        else if (kvFixture && (action === "fail-kv-mounts" || action === "restore-kv-mounts")) failKvMounts = action === "fail-kv-mounts";
        else if (kvFixture && (action === "fail-kv-status" || action === "restore-kv-status")) failKvStatus = action === "fail-kv-status";
        else if (kvFixture && (action === "delay-kv-status" || action === "delay-kv-empty-status")) { delayKvStatus = true; delayedKvStatusPath = action === "delay-kv-status" ? fixturePathId : "30000000-0000-4000-8000-000000000000"; }
        else if (kvFixture && action === "release-kv-status") releaseKvStatus?.();
        else if (kvFixture && action === "delay-kv-capabilities") delayKvCapabilities = true;
        else if (kvFixture && action === "release-kv-capabilities") releaseKvCapabilities?.();
        else if (kvFixture && action === "change-kv-retention") await db!.kvPath.update({ where: { id: fixturePathId }, data: { retention: 5, revision: { increment: 1 } } });
        else if (kvFixture && action === "change-kv-mount") await db!.kvMount.update({ where: { id: fixtureMountId }, data: { revision: { increment: 1 } } });
        else if (kvFixture && action === "deny-kv-update") await db!.kvPolicy.create({ data: { principal: "user:" + scoped.id, mountId: fixtureMountId, prefix: "services/api", effect: "deny", actions: JSON.stringify(["update"]) } });
        else if (kvFixture && action === "deny-kv-read") await db!.kvPolicy.create({ data: { principal: "user:" + scoped.id, mountId: fixtureMountId, prefix: "services/api", effect: "deny", actions: JSON.stringify(["read"]) } });
        else if (kvFixture && action === "change-kv-native-revision") { const object = native.objects.get("apps/kv-fixture-0000")!; object.metadata!.resourceVersion = "fixture-external-" + Date.now(); }
        else if (kvFixture && action === "change-kv-native-managed-field") { const object = native.objects.get("apps/kv-fixture-0000")!; Object.defineProperty(object.data!, "__proto__", { value: Buffer.from("synthetic externally changed selected field").toString("base64"), enumerable: true, writable: true, configurable: true }); object.metadata!.resourceVersion = "fixture-external-managed-" + Date.now(); }
        else if (action === "external-change") { const object = native.objects.get("apps/editor-fixture")!; native.seed("apps", "editor-fixture", object.data ?? {}, object); }
        else { response.writeHead(400); response.end(); return; }
        response.writeHead(204); response.end(); return;
      }
      const requestKey = request.method + " " + url.pathname;
      requestCounts.set(requestKey, (requestCounts.get(requestKey) ?? 0) + 1);
      const fluxPhase = url.pathname === "/api/flux/hierarchy" ? "hierarchy" : url.pathname.endsWith("/delete-progress") ? "progress" : url.pathname.endsWith("/sync") ? "sync" : request.method === "DELETE" && url.pathname.startsWith("/api/flux/repos/") ? "removal" : "";
      if (fluxFixture && request.method === "GET" && url.pathname.startsWith("/api/flux/")) {
        const readId = ++nextFluxRead;
        const active = (activeFlux.get(requestKey) ?? 0) + 1; activeFlux.set(requestKey, active);
        maxActiveFlux.set(requestKey, Math.max(maxActiveFlux.get(requestKey) ?? 0, active));
        fluxReadEvent({ id: readId, key: requestKey, event: "start", at: Date.now(), active });
        response.once("finish", () => fluxReadEvent({ id: readId, key: requestKey, event: "finish", at: Date.now(), active: activeFlux.get(requestKey) ?? 0, writableFinished: response.writableFinished }));
        response.once("close", () => {
          const remaining = Math.max(0, (activeFlux.get(requestKey) ?? 0) - 1); activeFlux.set(requestKey, remaining);
          fluxReadEvent({ id: readId, key: requestKey, event: "close", at: Date.now(), active: remaining, writableFinished: response.writableFinished });
        });
      }
      if (fluxFixture && fluxFailures.has(fluxPhase)) { response.writeHead(503, { "Content-Type": "application/json" }); response.end(JSON.stringify({ error: "Fixture Flux metadata unavailable" })); return; }
      if (request.method === "GET" && (url.pathname === "/api/secrets" && url.searchParams.has("key") || /^\/api\/kv\/paths\/[^/]+\/(?:versions\/[^/]+\/)?data$/.test(url.pathname))) valueRequests++;
      if (kvFixture && failKvMounts && request.method === "GET" && url.pathname === "/api/kv/mounts") { response.writeHead(503, { "Content-Type": "application/json" }); response.end(JSON.stringify({ error: "Fixture mount metadata unavailable" })); return; }
      if (kvFixture && failKvStatus && request.method === "GET" && url.pathname === `/api/kv/paths/${fixturePathId}/status`) { response.writeHead(503, { "Content-Type": "application/json" }); response.end(JSON.stringify({ error: "Fixture native status unavailable" })); return; }
      if (url.pathname.startsWith("/_next/static/")) {
        try {
          const staticRoot = path.resolve(root, ".next/static");
          const file = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice("/_next/static/".length)));
          if (!file.startsWith(staticRoot + path.sep)) throw new Error("Invalid static path");
          response.setHeader("Content-Type", file.endsWith(".js") ? "application/javascript" : file.endsWith(".css") ? "text/css" : "application/octet-stream");
          response.end(await readFile(file));
        } catch { response.writeHead(404); response.end(); }
        return;
      }
      const upstream = forward(origin + request.url, { method: request.method, headers: { ...request.headers, cookie: "botrus_auth_token=" + credential, host: "127.0.0.1:" + env.PORT } }, result => {
        if (result.headers["content-type"]?.startsWith("text/event-stream")) {
          activeStreams++;
          let ended = false;
          const end = () => { if (!ended) { ended = true; activeStreams--; } };
          result.once("end", end); result.once("close", end); response.once("close", end);
        }
        response.writeHead(result.statusCode ?? 502, result.headers);
        if (fluxFixture && fluxHolds.has(fluxPhase)) {
          fluxHolds.delete(fluxPhase); result.pause();
          fluxReleases.set(fluxPhase, () => { fluxReleases.delete(fluxPhase); if (!response.destroyed) result.pipe(response); else result.destroy(); });
        } else if (kvFixture && delayKvStatus && request.method === "GET" && url.pathname === `/api/kv/paths/${delayedKvStatusPath ?? fixturePathId}/status`) {
          delayKvStatus = false; result.pause(); releaseKvStatus = () => { releaseKvStatus = undefined; if (!response.destroyed) result.pipe(response); else result.destroy(); };
        } else if (kvFixture && delayKvCapabilities && request.method === "GET" && url.pathname === `/api/kv/paths/${fixturePathId}/capabilities`) {
          delayKvCapabilities = false; result.pause(); releaseKvCapabilities = () => { releaseKvCapabilities = undefined; if (!response.destroyed) result.pipe(response); else result.destroy(); };
        } else if (delayedReveal && request.method === "GET" && url.pathname === "/api/secrets" && url.searchParams.has("key")) {
          delayedReveal = false; result.pause(); setTimeout(() => { if (!response.destroyed) result.pipe(response); else result.destroy(); }, 4000);
        } else result.pipe(response);
      });
      response.once("close", () => upstream.destroy());
      upstream.on("error", () => { if (!response.destroyed) { if (!response.headersSent) response.writeHead(502); response.end(); } });
      request.pipe(upstream);
    });
    server.listen(0, "127.0.0.1"); await once(server, "listening"); servers.push(server);
    return "http://127.0.0.1:" + (server.address() as { port: number }).port;
  }
  console.log("UI_FIXTURE_READY " + JSON.stringify({ dir, writerUrl: await gateway(await token(writer)), readerUrl: await gateway(await token(reader)), scopedUrl: await gateway(await token(scoped)) }));
  process.stdin.resume();
  await new Promise<void>(resolve => {
    process.once("SIGINT", resolve); process.once("SIGTERM", resolve);
    process.stdin.on("data", chunk => { if (chunk.toString().trim() === "stop") resolve(); });
  });
} finally {
  for (const server of servers) { server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve())); }
  if (child && child.exitCode === null && child.signalCode === null) { child.kill(); await once(child, "exit"); }
  await db?.$disconnect();
  await native?.close();
  const tempRoot = path.resolve(tmpdir());
  if (!path.resolve(dir).startsWith(tempRoot + path.sep) || !path.basename(dir).startsWith("bortus-ui-test-")) throw new Error("Unsafe UI fixture cleanup target");
  await rm(dir, { recursive: true, force: true });
  process.stdin.pause();
}
}
void main().catch(error => { console.error(error instanceof Error ? error.message : "Disposable UI fixture failed"); process.exitCode = 1; });
