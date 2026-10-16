import { test } from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createKubectlClient, POD_LIST_MAX_BYTES } from "../src/lib/kubectl-client";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";

const run = promisify(execFile);
test("trusted complete Pod collection accepts a real >2MiB 10k child reply and redacts every projection", async () => {
  let bytes = 0;
  const client = createKubectlClient(async (args, options) => {
    assert.deepEqual(args, ["--kubeconfig", "fixture-only", "get", "pods", "-A", "-o", "json"]);
    assert.equal(options.maxBuffer, POD_LIST_MAX_BYTES);
    assert.ok(options.timeout <= 10000);
    const result = await run(process.execPath, ["-e", `process.stdout.write(JSON.stringify({kind:"PodList",metadata:{continue:"",remainingItemCount:0},items:Array.from({length:10000},(_,i)=>({kind:"Pod",metadata:{name:"pod-"+i,namespace:"apps",uid:"uid-"+i,annotations:{private:"private-pod-value-marker"+"x".repeat(420)}},spec:{containers:[{name:"app",env:[{name:"PRIVATE",value:"private-pod-value-marker"}]}]},status:{phase:i%2?"Running":"Pending"}}))}))`], options);
    bytes = Buffer.byteLength(result.stdout);
    return result;
  }, () => true, () => ["--kubeconfig", "fixture-only"]);
  const list = await client.listPods();
  assert.ok(bytes > 2 * 1024 * 1024 && bytes < POD_LIST_MAX_BYTES);
  assert.equal(list.items.length, 10000);
  assert.equal(list.items[9999].metadata.uid, "uid-9999");
  const response = podMetadataResponse({ pods: list.items, availability: { pods: { state: "healthy", sampledAt: "2026-10-10T00:00:00Z", staleAgeMs: null, retryAfterMs: 10000, durationMs: 1 } } }, () => true, false);
  const text = await response.text();
  assert.ok(!text.includes("private-pod-value-marker"));
  const body = JSON.parse(text);
  assert.equal(body.pods.length, 10000);
  assert.ok(body.pods.every((pod: any, index: number) => pod.id === "uid-" + index && pod.name === "pod-" + index && pod.namespace === "apps"));
  assert.equal(body.privateFieldsOmitted, true);
});

test("Pod collection refuses partial, malformed, over-item and over-byte replies without output disclosure", async () => {
  for (const value of [null, [], { items: null }, { kind: "SecretList", items: [] }, { items: [null] }, { items: [{kind:"Secret"}] }, { items: Array(10001).fill({}) }, { items: [], metadata: { continue: "private-cursor-marker" } }, { items: [], metadata: { remainingItemCount: 1 } }]) {
    const client = createKubectlClient(async () => ({ stdout: JSON.stringify(value) }), () => true, () => []);
    await assert.rejects(client.listPods(), error => { assert.equal((error as any).status, 502); assert.ok(!String(error).includes("private-cursor-marker")); return true; });
  }
  const oversized = createKubectlClient((_, options) => run(process.execPath, ["-e", "process.stdout.write('private-output-marker'.repeat(500000))"], options), () => true, () => []);
  await assert.rejects(oversized.listPods(), { status: 502, message: "Cluster response exceeds the size limit" });
  assert.equal(oversized.diagnostics().active, 0);
  const untrusted = createKubectlClient(async () => ({ stdout: "x".repeat(POD_LIST_MAX_BYTES + 1) }), () => true, () => []);
  await assert.rejects(untrusted.listPods(), { status: 502, message: "Cluster response exceeds the size limit" });
});

test("trusted Pod list shares general command admission and original queue-plus-process deadline", async () => {
  let release!: (result: {stdout:string}) => void;
  let calls = 0;
  const client = createKubectlClient(async () => { calls++; return new Promise(resolve => { release = resolve; }); }, () => true, () => [], {concurrent:1,queued:1});
  const active = client.exec(["get","nodes"],1000);
  await new Promise(resolve => setImmediate(resolve));
  const queued = client.listPods(30);
  await assert.rejects(client.listPods(30), { status: 503 });
  await assert.rejects(queued, { status: 504 });
  assert.equal(calls,1);
  release({stdout:""}); await active;
  const stalled = createKubectlClient((_,options) => run(process.execPath,["-e","setTimeout(()=>{},10000)"],options),()=>true,()=>[]);
  await assert.rejects(stalled.listPods(100), {status:504});
  assert.equal(stalled.diagnostics().active,0);
  const late = createKubectlClient(async () => { await new Promise(resolve => setTimeout(resolve,30)); return {stdout:"{\"items\":[]}"}; },()=>true,()=>[]);
  await assert.rejects(late.listPods(10), {status:504});
});
