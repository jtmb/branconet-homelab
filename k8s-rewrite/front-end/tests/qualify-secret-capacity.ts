// Disposable Linux benchmark: mock API and each measured client have separate processes.
import assert from "node:assert/strict";
import { fork, spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeTlsFixture } from "./helpers/native-tls";

type Scenario = "small334" | "maximumKv25" | "maximumFlat3" | "historyMetadata25";
type Mode = "baseline" | "adaptive";
type ClientResult = { mode: Mode; scenario: Scenario; receivedBodyBytes: number; elapsedMs: number; peakRss: number; [key: string]: unknown };
const scenarios: Scenario[] = ["small334", "maximumKv25", "maximumFlat3", "historyMetadata25"];
const memory = async () => {
  const status = await readFile("/proc/self/status", "utf8");
  return { rssKiB: Number(/^VmRSS:\s+(\d+)/m.exec(status)?.[1]), highWaterKiB: Number(/^VmHWM:\s+(\d+)/m.exec(status)?.[1]) };
};
const cgroup = async () => ({
  memoryCurrent: Number(await readFile("/sys/fs/cgroup/memory.current", "utf8")),
  memoryPeak: Number(await readFile("/sys/fs/cgroup/memory.peak", "utf8")),
  memoryLimit: (await readFile("/sys/fs/cgroup/memory.max", "utf8")).trim(),
  cpuMax: (await readFile("/sys/fs/cgroup/cpu.max", "utf8")).trim(),
  pidsMax: (await readFile("/sys/fs/cgroup/pids.max", "utf8")).trim(),
  cpuStat: (await readFile("/sys/fs/cgroup/cpu.stat", "utf8")).trim(),
});

async function server() {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-capacity-api-")), api = await nativeTlsFixture(dir, 12);
  process.send?.({ ready: true, config: api.config });
  process.on("message", async (message: { id: number; scenario?: Scenario; telemetry?: boolean; close?: boolean }) => {
    if (message.close) {
      await api.close();
      if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-capacity-api-")) throw new Error("Unsafe capacity benchmark cleanup target");
      await rm(dir, { recursive: true, force: true }); process.send?.({ id: message.id, closed: true }); process.disconnect(); return;
    }
    if (message.scenario) {
      api.reset();
      const scenario = message.scenario;
      if (scenario === "small334") for (let i = 0; i < 334; i++) api.seed("namespace-" + i % 18, "secret-" + i, { field: "c3ludGhldGlj" });
      else {
        const count = scenario === "maximumFlat3" ? 3 : 25, size = scenario === "maximumFlat3" ? 1024 * 1024 : 256 * 1024;
        const value = Buffer.alloc(size, 7).toString("base64");
        for (let i = 0; i < count; i++) api.seed("records", "record-" + i, { field: value }, { immutable: scenario === "historyMetadata25" });
      }
    }
    process.send?.({ id: message.id, requests: api.calls.length, producedResponseBytes: api.calls.reduce((sum, call) => sum + call.responseBytes, 0),
      limits: api.calls.map(call => call.limit), metadataOnly: api.calls.length > 0 && api.calls.every(call => call.metadata), apiMemory: await memory() });
  });
}

async function client(mode: Mode, config: string, scenario: Scenario) {
  process.env.KUBECONFIG = config;
  const beforeImport = await memory(), before = await cgroup();
  // Baseline library is a test-only snapshot; both variants share current unchanged dependencies.
  const { createSecretTransport, nativeRequestDiagnostics } = await import(mode === "baseline" ? "../baseline-lib/secret-client" : "../src/lib/secret-client");
  const { SecretListBudget, secretSummary } = await import("../src/lib/cluster-secrets");
  const budget = new SecretListBudget(), transport = createSecretTransport(), projected: unknown[] = [];
  const scopes = scenario === "small334" ? Array.from({ length: 18 }, (_, i) => "namespace-" + i) : ["records"];
  let peakRss = process.memoryUsage().rss, peakHeap = process.memoryUsage().heapUsed, peakExternal = process.memoryUsage().external;
  const sample = () => { const current = process.memoryUsage(); peakRss = Math.max(peakRss, current.rss); peakHeap = Math.max(peakHeap, current.heapUsed); peakExternal = Math.max(peakExternal, current.external); };
  const sampler = setInterval(sample, 5), cpu = process.cpuUsage(), start = performance.now();
  try {
    for (const namespace of scopes) {
      if (scenario === "historyMetadata25") projected.push(...await transport.listMetadata(namespace));
      else assert.equal((await transport.list(namespace, { budget, visit: (item: Parameters<typeof secretSummary>[0]) => { projected.push(secretSummary(item)); } })).length, 0);
    }
  } finally { sample(); clearInterval(sampler); }
  const elapsedMs = performance.now() - start;
  assert.equal(projected.length, scenario === "small334" ? 334 : scenario === "maximumFlat3" ? 3 : 25);
  assert(!JSON.stringify(projected).includes('"data":')); assert(!JSON.stringify(projected).includes('"annotations":'));
  assert.equal(nativeRequestDiagnostics().active, 0); assert.equal(nativeRequestDiagnostics().queued, 0);
  process.stdout.write(JSON.stringify({ mode, scenario, objects: projected.length, elapsedMs, receivedBodyBytes: budget.bytes,
    acceptedItems: budget.items, peakRss, peakHeap, peakExternal, beforeImport, after: await memory(), cpu: process.cpuUsage(cpu), cgroupBefore: before, cgroupAfter: await cgroup() }) + "\n");
}

async function main() {
  assert.equal(process.platform, "linux", "Controlled qualification requires Linux proc/cgroup counters");
  const child = fork(__filename, ["server"], { stdio: ["ignore", "ignore", "pipe", "ipc"] });
  let id = 0;
  const ask = (message: object) => new Promise<any>((resolve, reject) => {
    const requestId = ++id, timer = setTimeout(() => { child.off("message", receive); reject(new Error("Benchmark API timeout")); }, 10000);
    const receive = (response: any) => { if (response.id === requestId) { clearTimeout(timer); child.off("message", receive); resolve(response); } };
    child.on("message", receive); child.send({ ...message, id: requestId });
  });
  const ready = await new Promise<{ config: string }>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Benchmark API startup timeout")), 10000);
    child.once("message", (message: any) => { clearTimeout(timer); assert(message.ready); resolve(message); });
    child.once("error", reject);
  });
  const results: (ClientResult & { repeat: number; api: unknown })[] = [];
  try {
    for (const scenario of scenarios) for (let repeat = 0; repeat < 3; repeat++) for (const mode of ["baseline", "adaptive"] as const) {
      await ask({ scenario });
      const result = await new Promise<ClientResult>((resolve, reject) => {
        const current = spawn(process.execPath, [...process.execArgv, __filename, "client", mode, ready.config, scenario], { stdio: ["ignore", "pipe", "pipe"], env: { ...process.env, RUST_LOG: "" } });
        let output = "", errorBytes = 0;
        const timer = setTimeout(() => { current.kill(); reject(new Error("Benchmark client timeout")); }, 30000);
        current.stdout.on("data", chunk => { output += chunk; if (output.length > 32768) { current.kill(); reject(new Error("Oversized benchmark output")); } });
        current.stderr.on("data", chunk => { errorBytes += chunk.length; }); current.once("error", reject);
        current.once("exit", code => { clearTimeout(timer); if (code !== 0) reject(new Error("Benchmark client failed; stderr bytes " + errorBytes)); else { try { resolve(JSON.parse(output)); } catch { reject(new Error("Invalid benchmark result")); } } });
      });
      const telemetry = await ask({ telemetry: true });
      if (scenario === "small334") {
        const prior = results.find(item => item.scenario === scenario && item.mode === mode);
        if (prior) assert.equal(result.receivedBodyBytes, prior.receivedBodyBytes, "Repeat fixtures must retain identical serialized size");
      }
      results.push({ repeat, ...result, api: telemetry });
      process.stdout.write(JSON.stringify({ repeat, mode, scenario, elapsedMs: result.elapsedMs, requests: telemetry.requests, receivedBodyBytes: result.receivedBodyBytes, peakRss: result.peakRss }) + "\n");
    }
  } finally { await ask({ close: true }).catch(() => {}); if (child.connected) child.disconnect(); child.kill(); }
  process.stdout.write(JSON.stringify({ qualification: "BORTUS adaptive Secret list", runtime: process.version, processLimits: await cgroup(), results,
    limitations: ["Read-only synthetic verified-TLS API; no production count or latency refreshed", "Baseline source is 7cfedb4 one-object reader", "RSS includes module/client allocations; API runs separately", "Cgroup includes parent, mock API, measured client and filesystem cache", "Cold fresh measured clients; host/VM scheduling and certificate/TLS state still influence timings", "Full production server/image and live performance acceptance remain separate"] }) + "\n");
}

const action = process.argv[2];
(action === "server" ? server() : action === "client" ? client(process.argv[3] as Mode, process.argv[4], process.argv[5] as Scenario) : main())
  .catch(() => { process.stderr.write("Capacity qualification failed\n"); process.exitCode = 1; });
