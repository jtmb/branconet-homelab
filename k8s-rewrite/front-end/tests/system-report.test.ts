import { test } from "node:test";
import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import { runtimeImage, workloadInventory, type InventorySnapshot } from "../src/lib/system-report-inventory";
import { normalizeTrivy, trivyArguments, executeScanner, localTrivyScanner, type Scanner } from "../src/lib/system-report-scanner";
import { SystemReportJobs, REPORT_LIMITS } from "../src/lib/system-report-jobs";
import { resultStale, safeAdvisoryURL, type ScanResult, type Inventory } from "../src/lib/system-report-types";

const digest = "sha256:" + "a".repeat(64), reference = `registry.example/app@${digest}`;
const now = Date.parse("2026-10-25T20:00:00Z"), database = { UpdatedAt: "2026-10-25T19:00:00Z", NextUpdate: "2026-10-26T01:00:00Z" };
function snapshot(): InventorySnapshot {
  return { sampledAt: new Date(now).toISOString(), stale: false,
    replicasets: [{ metadata: { uid: "rs1", namespace: "apps", ownerReferences: [{ kind: "Deployment", name: "api", controller: true }] } }],
    services: [{ metadata: { name: "api", namespace: "apps" }, spec: { selector: { app: "api", tier: "backend" } } },
      { metadata: { name: "wrong-tier", namespace: "apps" }, spec: { selector: { app: "api", tier: "frontend" } } },
      { metadata: { name: "empty", namespace: "apps" }, spec: { selector: {} } },
      { metadata: { name: "other-ns", namespace: "other" }, spec: { selector: { app: "api" } } }],
    pods: [{ metadata: { name: "api-1", namespace: "apps", labels: { app: "api", tier: "backend" }, ownerReferences: [{ kind: "ReplicaSet", uid: "rs1", controller: true, name: "api-rs" }] },
      spec: { containers: [{ name: "app", image: "registry.example/app:v1" }] },
      status: { containerStatuses: [{ name: "app", imageID: `docker-pullable://${reference}`, state: { running: {} } }],
        initContainerStatuses: [{ name: "sidecar", imageID: reference, state: { running: {} } }, { name: "done" }],
        ephemeralContainerStatuses: [{ name: "debug", imageID: reference, state: { running: {} } }] } },
    { metadata: { name: "other", namespace: "other", labels: { app: "api" }, ownerReferences: [{ kind: "StatefulSet", name: "store", controller: true }] },
      status: { containerStatuses: [{ name: "app", imageID: reference, state: { running: {} } }, { name: "missing", state: { running: {} } },
        { name: "opaque", imageID: `containerd://${digest}`, state: { running: {} } }, { name: "waiting", imageID: reference }] } }] };
}
function rawReport() { return { SchemaVersion: 2, Metadata: { RepoDigests: [reference], OS: { EOSL: true } }, Results: [{ Target: "alpine", Packages: [{ Name: "openssl" }], Vulnerabilities: [
  { VulnerabilityID: "CVE-TEST-1", PkgName: "openssl", InstalledVersion: "1", FixedVersion: "2", Severity: "CRITICAL", PrimaryURL: "https://advisories.example/test" },
  { VulnerabilityID: "CVE-TEST-2", PkgName: "openssl", InstalledVersion: "1", Severity: "future-severity", PrimaryURL: "javascript:alert(1)", References: ["https://advisories.example/2"] },
] }] }; }
function complete(): ScanResult { return normalizeTrivy(rawReport(), reference, database, now); }
function inventory(): Inventory { return workloadInventory({ ...snapshot(), pods: snapshot().pods!.slice(0, 1) }); }
function scanner(scan: Scanner["scan"] = async () => complete()): Scanner { return { status: async () => ({ configured: true, message: "fixture", cacheKey: "db1" }), scan }; }

test("runtime identity accepts pullable digests, refuses mutable/opaque/malicious references", () => {
  assert.deepEqual(runtimeImage(`docker-pullable://${reference}`), { digest, reference });
  for (const value of [undefined, "alpine:latest", `containerd://${digest}`, digest, `https://registry.example/app@${digest}`, `--option@${digest}`, `../app@${digest}`, reference + "\n", reference + ";evil"]) assert.equal(runtimeImage(value), null, value);
});
test("inventory deduplicates digest across aliases/namespaces and includes running init/ephemeral only", () => {
  const value = workloadInventory(snapshot());
  assert.equal(value.runningContainers, 6); assert.equal(value.images.length, 3);
  const image = value.images[0]; assert.equal(image.consumers.length, 4);
  assert.equal(image.consumers[0].workload, "Deployment/api");
  assert.deepEqual(image.consumers[0].services, ["api"]);
  assert.equal(image.consumers[3].workload, "StatefulSet/store");
  assert.deepEqual(image.consumers[3].services, ["other-ns"]);
  assert.deepEqual(image.consumers.map(c => c.kind), ["container", "init", "ephemeral", "container"]);
  assert.equal(value.images.filter(i => i.state === "unsupported").length, 2);
});
test("unavailable/stale ownership and Service mapping remain explicit without falsely empty coverage", () => {
  const value = workloadInventory({ ...snapshot(), services: undefined, replicasets: undefined, stale: true });
  assert.equal(value.stale, true); assert.equal(value.images[0].consumers[0].services, null);
  assert.equal(value.images[0].consumers[0].workload, "ReplicaSet/api-rs");
  assert.equal(value.warnings.length, 3);
  const missing = workloadInventory({ ...snapshot(), pods: undefined });
  assert.equal(missing.available, false); assert.equal(missing.images.length, 0); assert.ok(missing.warnings[0].includes("unknown"));
});
test("controller resolution requires namespace and controller UID, not names or label coincidence", () => {
  const input = snapshot(); input.replicasets![0].metadata!.namespace = "elsewhere";
  assert.equal(workloadInventory(input).images[0].consumers[0].workload, "ReplicaSet/api-rs");
  input.replicasets![0].metadata!.namespace = "apps"; input.replicasets![0].metadata!.uid = "different";
  assert.equal(workloadInventory(input).images[0].consumers[0].workload, "ReplicaSet/api-rs");
});
test("normalization preserves severity/fixes/advisories/freshness/coverage and rejects wrong image identity", () => {
  const value = complete(); assert.equal(value.state, "complete"); assert.equal(value.findings.length, 2);
  assert.equal(value.findings[0].severity, "CRITICAL"); assert.equal(value.findings[0].fixed, "2");
  assert.equal(value.findings[1].severity, "UNKNOWN"); assert.equal(value.findings[1].url, "https://advisories.example/2");
  assert.equal(value.endOfLife, true); assert.equal(value.packageCount, 1); assert.equal(resultStale(value, now), false);
  assert.equal(resultStale(value, now + 86400000), true);
  const bad = rawReport(); bad.Metadata.RepoDigests = ["registry.example/app@sha256:" + "b".repeat(64)];
  assert.throws(() => normalizeTrivy(bad, reference, database));
});
test("empty, missing and oversized package analysis never becomes a no-match success", () => {
  const input = rawReport(); input.Results = [];
  assert.equal(normalizeTrivy(input, reference, database).state, "unsupported");
  const input2 = rawReport(); input2.Results[0].Packages = [];
  assert.equal(normalizeTrivy(input2, reference, database).state, "unsupported");
  assert.throws(() => normalizeTrivy({ ...rawReport(), Results: [{ Target: "missing" }] }, reference, database));
  assert.equal(normalizeTrivy({ ...rawReport(), Results: Array(1001).fill({}) }, reference, database).state, "unsupported");
});
test("unsafe advisory links and absent freshness are refused conservatively", () => {
  for (const url of ["javascript:alert(1)", "http://example.org", "https://user:secret@example.org", "data:text/html,hello", null]) assert.equal(safeAdvisoryURL(url), null);
  assert.equal(resultStale({ ...complete(), dbUpdatedAt: undefined }, now), true);
  assert.equal(resultStale({ ...complete(), dbUpdatedAt: "not-a-date" }, now), true);
  assert.equal(resultStale({ ...complete(), scannedAt: new Date(now + 3600000).toISOString() }, now), true);
});
test("scanner command disables external matching/updaters/telemetry, shell and mutable tags", () => {
  const args = trivyArguments(reference, tmpdir());
  for (const flag of ["--skip-db-update", "--skip-java-db-update", "--skip-check-update", "--skip-version-check", "--offline-scan", "--disable-telemetry", "--max-image-size"]) assert.ok(args.includes(flag));
  assert.equal(args.at(-1), reference); assert.equal(args[args.indexOf("--image-src") + 1], "remote");
  assert.throws(() => trivyArguments("alpine:latest", tmpdir()));
});
test("absent scanner/database has an honest unsupported capability", async () => {
  assert.equal((await localTrivyScanner("relative-path", "relative-cache").status()).configured, false);
});
test("job start coalesces repeated concurrent requests and digest scan runs exactly once", async () => {
  let calls = 0; const controllers = new Map();
  const jobs = new SystemReportJobs(async () => inventory(), scanner(async () => { calls++; return complete(); }), controllers, () => now);
  const [one, two] = await Promise.all([jobs.start(), jobs.start()]);
  assert.equal(one!.id, two!.id); await jobs.settled();
  assert.equal(calls, 1); assert.equal(controllers.size, 0); assert.equal((await jobs.report()).images[0].state, "complete");
  await jobs.start(); await jobs.settled(); assert.equal(calls, 1, "same digest and DB uses cache");
});
test("database revision and stale cached data invalidate scan cache", async () => {
  let calls = 0, clock = now, dbKey = "one";
  const fake = scanner(async () => { calls++; return complete(); }); fake.status = async () => ({ configured: true, message: "fixture", cacheKey: dbKey });
  const jobs = new SystemReportJobs(async () => inventory(), fake, new Map(), () => clock);
  await jobs.start(); await jobs.settled(); dbKey = "two"; await jobs.start(); await jobs.settled(); assert.equal(calls, 2);
  clock += 86400000; await jobs.start(); await jobs.settled(); assert.equal(calls, 3);
});
test("cancel waits for active scan drain, prevents new job and leaves unscanned images incomplete", async () => {
  let finish!: () => void; let entered!: () => void; const started = new Promise<void>(r => entered = r);
  const inv = inventory(); inv.images.push({ ...inv.images[0], key: "other", digest: "sha256:" + "b".repeat(64), reference: "registry.example/other@sha256:" + "b".repeat(64) });
  let calls = 0;
  const jobs = new SystemReportJobs(async () => inv, scanner(async (_ref, signal) => { calls++; entered(); await new Promise<void>(r => { finish = r; }); assert.equal(signal.aborted, true); return complete(); }), new Map(), () => now);
  const job = await jobs.start(); await started; jobs.cancel(job!.id);
  assert.equal((await jobs.start())!.id, job!.id); finish(); await jobs.settled();
  assert.equal(calls, 1); assert.equal((await jobs.report()).job!.state, "cancelled");
  assert.ok((await jobs.report()).images.every(image => image.state === "cancelled"));
  assert.throws(() => jobs.cancel(job!.id), { status: 409 });
});
test("deadline aborts scanner and releases registry; stale/unavailable/oversize inventories refuse startup", async () => {
  const controllers = new Map();
  const jobs = new SystemReportJobs(async () => inventory(), scanner(async (_ref, signal) => { await new Promise<void>(r => signal.addEventListener("abort", () => r(), { once: true })); return complete(); }), controllers, () => now, { ...REPORT_LIMITS, deadlineMs: 10 });
  await jobs.start(); await jobs.settled(); assert.equal((await jobs.report()).job!.state, "error"); assert.equal(controllers.size, 0);
  for (const inv of [{ ...inventory(), stale: true }, { ...inventory(), available: false }]) {
    await assert.rejects(new SystemReportJobs(async () => inv, scanner(), new Map()).start(), { status: 503 });
  }
  await assert.rejects(new SystemReportJobs(async () => inventory(), scanner(), new Map(), () => now, { ...REPORT_LIMITS, images: 0 }).start(), { status: 422 });
});
test("report byte ceiling preserves failure state and does not retain oversized results", async () => {
  const jobs = new SystemReportJobs(async () => inventory(), scanner(), new Map(), () => now, { ...REPORT_LIMITS, resultBytes: 1 });
  await jobs.start(); await jobs.settled(); const image = (await jobs.report()).images[0];
  assert.equal(image.state, "error"); assert.equal(image.findings.length, 0); assert.match(image.message!, /size limit/);
});
test("failed scanner result is not cached and consumers reconcile against latest inventory", async () => {
  let calls = 0; let inv = inventory();
  const jobs = new SystemReportJobs(async () => inv, scanner(async () => { calls++; return { state: "error", findings: [], message: "fixture" }; }), new Map(), () => now);
  await jobs.start(); await jobs.settled(); await jobs.start(); await jobs.settled(); assert.equal(calls, 2);
  inv = { ...inv, images: [], runningContainers: 0 }; assert.equal((await jobs.report()).images.length, 0);
});
test("actual child process gets a scrubbed environment and drains on cancellation/timeout/output failure", { timeout: 10000 }, async () => {
  process.env.BORTUS_TEST_PRIVATE_MARKER = "must-not-cross";
  try {
    const output = await executeScanner(process.execPath, ["-e", "process.stdout.write(JSON.stringify({secret:process.env.BORTUS_TEST_PRIVATE_MARKER,home:process.env.HOME,go:process.env.GOMAXPROCS}))"], tmpdir(), new AbortController().signal);
    assert.deepEqual(JSON.parse(output), { home: tmpdir(), go: "1" });
    await assert.rejects(executeScanner(process.execPath, ["-e", "setTimeout(()=>{},20000)"], tmpdir(), new AbortController().signal, tmpdir(), { timeoutMs: 50, outputBytes: 100, errorBytes: 100 }), /timeout/);
    await assert.rejects(executeScanner(process.execPath, ["-e", "process.stdout.write('x'.repeat(1000))"], tmpdir(), new AbortController().signal, tmpdir(), { timeoutMs: 2000, outputBytes: 100, errorBytes: 100 }), /output limit/);
    const controller = new AbortController(); const processResult = executeScanner(process.execPath, ["-e", "setTimeout(()=>{},20000)"], tmpdir(), controller.signal); controller.abort();
    await assert.rejects(processResult, /cancelled/);
  } finally { delete process.env.BORTUS_TEST_PRIVATE_MARKER; }
});
