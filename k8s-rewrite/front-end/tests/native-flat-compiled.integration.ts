import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, writeFile, readFile, rm, lstat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import net, { type AddressInfo } from "node:net";
import { once } from "node:events";
import { PrismaClient } from "@prisma/client";
import { SignJWT } from "jose";
import { nativeTlsFixture } from "./helpers/native-tls";

test("compiled native GET loads the actual selector and preserves the complete audit-small metadata oracle", { timeout: 60000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-compiled-native-"));
  const database = "file:" + path.join(dir, "fixture.db").replaceAll("\\", "/");
  const db = new PrismaClient({ datasources: { db: { url: database } } });
  let child: ChildProcess | undefined, native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  const stop = async () => {
    if (child && child.exitCode === null) {
      const exited = once(child, "exit"); child.kill("SIGTERM");
      const timer = setTimeout(() => child?.kill("SIGKILL"), 5000);
      try { await exited; } finally { clearTimeout(timer); }
    }
    if (child) console.log("COMPILED_NATIVE_CLEANUP " + JSON.stringify({ pid: child.pid, exitCode: child.exitCode, signal: child.signalCode }));
  };
  try {
    assert.equal((await lstat(path.resolve("native/secret-flat-selector.node"))).isFile(), true, "An actual built native selector is required");
    native = await nativeTlsFixture(dir, 12);
    const namespaces = ["apps", ...Array.from({ length: 17 }, (_, i) => "scope-" + String(i).padStart(2, "0"))];
    const privateMarker = "synthetic private annotation";
    for (let i = 0; i < 334; i++) {
      const namespace = namespaces[i % 18], name = "secret-" + String(i).padStart(5, "0");
      native.seed(namespace, name, { payload: Buffer.alloc(64, 7).toString("base64"), original_under_score: "", empty: "" }, { metadata: { labels: { fixture: "metadata" }, annotations: { "kubectl.kubernetes.io/last-applied-configuration": privateMarker } } });
      native.objects.get(namespace + "/" + name)!.metadata!.resourceVersion = "10";
    }
    const aliases = path.join(dir, "aliases.json"); await writeFile(aliases, "[]");
    const observed = path.join(dir, "native-load.json"), preload = path.resolve(process.env.BORTUS_TEST_NATIVE_LOAD_PROBE ?? "tests/helpers/native-load-probe.cjs");
    const env: NodeJS.ProcessEnv = { PATH: process.env.PATH, HOME: dir, DATABASE_URL: database, BOTRUS_JWT_SECRET: "synthetic-compiled-native-signing", BOTRUS_SECRETS_KEY: "synthetic-compiled-native-lookup", BORTUS_SECRET_NAMESPACES: namespaces.join(","), BORTUS_SECRET_ALIASES_FILE: aliases, BORTUS_KV_GUARDED_ADOPTION: "false", BORTUS_DISABLE_PROVISIONING: "true", KUBECONFIG: native.config, NODE_ENV: "production", NEXT_TELEMETRY_DISABLED: "1", HOSTNAME: "127.0.0.1", BORTUS_TEST_NATIVE_LOAD_RECORD: observed };
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    const account = await db.user.create({ data: { username: "compiled_reader", passwordHash: "unused fixture", role: "readonly" } });
    const token = await new SignJWT({ sub: account.id, username: account.username, sessionVersion: account.sessionVersion }).setProtectedHeader({ alg: "HS256" }).setIssuedAt().setExpirationTime("1h").sign(new TextEncoder().encode(env.BOTRUS_JWT_SECRET));
    const socket = net.createServer(); socket.listen(0, "127.0.0.1"); await once(socket, "listening"); env.PORT = String((socket.address() as AddressInfo).port); await new Promise<void>(resolve => socket.close(() => resolve()));
    const origin = "http://127.0.0.1:" + env.PORT;
    child = spawn(process.execPath, ["--require", preload, path.resolve(".next/standalone/server.js")], { env, stdio: "ignore" });
    console.log("COMPILED_NATIVE_PROCESS " + JSON.stringify({ pid: child.pid }));
    const end = Date.now() + 30000; let ready = false;
    while (Date.now() < end) {
      if (child.exitCode !== null) throw Error("Compiled native server exited");
      try { if ((await fetch(origin + "/api/health/live", { signal: AbortSignal.timeout(500) })).ok) { ready = true; break; } } catch { /* bounded startup only */ }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.equal(ready, true);
    const response = await fetch(origin + "/api/secrets", { headers: { cookie: "botrus_auth_token=" + token }, signal: AbortSignal.timeout(15000) });
    if (response.status !== 200) {
      const result = await response.clone().json().catch(() => null);
      console.log("COMPILED_NATIVE_STATUS " + JSON.stringify({ expected: 200, actual: response.status, fixedLoaderError: result?.error === "Invalid Kubernetes Secret summary response", nativeLoadObserved: await lstat(observed).then(() => true, () => false) }));
    }
    assert.equal(response.status, 200);
    const result = await response.json(), rows = result.secrets;
    assert.equal(rows.length, 334, "Incomplete native metadata inventory");
    assert.equal(new Set(rows.map((row: { namespace: string; name: string }) => row.namespace + "/" + row.name)).size, 334);
    for (const row of rows) {
      const i = Number(row.name.slice(7)); assert.equal(row.name, "secret-" + String(i).padStart(5, "0")); assert.equal(row.namespace, namespaces[i % 18]); assert.equal(row.type, "Opaque"); assert.equal(row.resourceVersion, "10");
      assert.deepEqual([...row.keys].sort(), ["empty", "original_under_score", "payload"]);
      assert.equal("data" in row || "annotations" in row || "managedFields" in row, false);
    }
    assert.equal(JSON.stringify(result).includes(privateMarker), false);
    const load = JSON.parse(await readFile(observed, "utf8")); assert.equal(load.loaded, true);
    assert.equal(native.calls.length, 18); assert.equal(native.calls.every(call => call.method === "GET" && !call.metadata), true);
    console.log("COMPILED_NATIVE_PROOF " + JSON.stringify({ actualLoaded: true, artifactDigest: load.artifactDigest, objects: 334, namespaces: 18, completePrivateProjection: true }));
  } finally {
    await stop(); await native?.close(); await db.$disconnect();
    assert.equal(path.dirname(dir), tmpdir()); assert(path.basename(dir).startsWith("bortus-compiled-native-")); await rm(dir, { recursive: true, force: true });
  }
});
