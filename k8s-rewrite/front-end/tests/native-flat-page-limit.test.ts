import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeTlsFixture } from "./helpers/native-tls";
import { createSecretTransport, nativeSecrets, nativeRequestDiagnostics } from "../src/lib/secret-client";
import { SecretError } from "../src/lib/cluster-secrets";

test("actual TLS flat pages use16MiB while generic values retain4MiB and retries retain32MiB charge", { timeout: 30000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-flat-page-"));
  const keys = ["KUBECONFIG", "BORTUS_SECRET_NAMESPACES", "BORTUS_HISTORY_NAMESPACE"] as const;
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try {
    native = await nativeTlsFixture(dir); process.env.KUBECONFIG = native.config;
    process.env.BORTUS_SECRET_NAMESPACES = "flat-limit"; process.env.BORTUS_HISTORY_NAMESPACE = "history";
    const stored = native.seed("flat-limit", "public", { payload: "", empty: "" });
    const body = native.objects.get("flat-limit/public")!;
    const overhead = Buffer.byteLength(JSON.stringify({ apiVersion: "v1", kind: "SecretList", metadata: { continue: "" }, items: [stored] }));
    body.data!.payload = "A".repeat(16 * 1024 * 1024 - overhead);
    const rows = await nativeSecrets().list();
    assert.equal(rows.length, 1); assert.deepEqual(rows[0].keys, ["empty", "payload"]);
    assert.equal(Object.hasOwn(rows[0], "data"), false); assert.equal(native.calls.length, 1);
    assert.equal(native.calls[0].responseBytes, 16 * 1024 * 1024); assert.equal(native.calls[0].limit, 200);
    await assert.rejects(createSecretTransport().read("flat-limit", "public"), error => error instanceof SecretError && error.status === 503 && error.message === "Kubernetes Secret response exceeds the size limit");
    assert.equal(native.calls.length, 2);
    native.calls.length = 0; body.data!.payload += "A";
    await assert.rejects(nativeSecrets().list(), error => error instanceof SecretError && error.status === 503 && error.message === "Kubernetes Secret list exceeds the aggregate byte limit");
    assert.deepEqual(native.calls.map(call => call.limit), [200, 10]);
    assert.ok(native.calls.every(call => call.responseBytes === 16 * 1024 * 1024 + 1));
    assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 8, maxQueued: 64 });
  } finally {
    for (const key of keys) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
    await native?.close();
    assert.equal(path.dirname(path.resolve(dir)), path.resolve(tmpdir())); assert.ok(path.basename(dir).startsWith("bortus-flat-page-"));
    await rm(dir, { recursive: true, force: true });
  }
});
