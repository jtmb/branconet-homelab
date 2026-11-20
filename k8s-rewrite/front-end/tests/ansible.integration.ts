import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, mkdir, cp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import net, { type AddressInfo } from "node:net";
import { once } from "node:events";
import { PrismaClient } from "@prisma/client";
import { fakeAnsible } from "./helpers/fake-ansible";

test("production local jobs persist/stream fixed progress, reject selection before effects and preserve operator gates", { timeout: 120000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-ansible-http-"));
  const app = path.join(dir, "app"), database = "file:" + path.join(dir, "fixture.db").replaceAll("\\", "/");
  const marker = "private-ansible-http-fixture-value";
  let child: ChildProcess | undefined, db: PrismaClient | undefined, serverOutput = "";
  try {
    const fixture = await fakeAnsible(dir); await fixture.mode("success");
    const env: NodeJS.ProcessEnv = { ...process.env, ...fixture.env, DATABASE_URL: database,
      BOTRUS_JWT_SECRET: "synthetic-ansible-http-signing-material", BOTRUS_SECRETS_KEY: marker,
      ANSIBLE_BECOME_PASSWORD: marker, ANSIBLE_REMOTE_USER: "fixture-user", ANSIBLE_PRIVATE_KEY_FILE: path.join(dir, "fixture-key-path"),
      BORTUS_SECRET_NAMESPACES: "apps", BORTUS_SECRET_ALIASES_FILE: path.join(dir, "aliases.json"),
      BORTUS_DISABLE_PROVISIONING: "false", NODE_ENV: "production", HOSTNAME: "127.0.0.1" };
    delete env.RUST_LOG; delete env.KUBERNETES_SERVICE_HOST; delete env.KUBECONFIG;
    await writeFile(env.BORTUS_SECRET_ALIASES_FILE!, "[]");
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    db = new PrismaClient({ datasources: { db: { url: database } } });
    await cp(path.resolve(".next/standalone"), app, { recursive: true, filter: source => !/^(\.env(?:\..*)?|.*\.(?:db|sqlite)(?:-wal|-shm)?)$/.test(path.basename(source)) });
    await mkdir(path.join(dir, "ansible-playbook", "playbooks"), { recursive: true });
    await writeFile(path.join(dir, "ansible-playbook", "playbooks", "site.yml"), "# synthetic child fixture only\n");
    const holder = net.createServer(); holder.listen(0, "127.0.0.1"); await once(holder, "listening");
    const port = (holder.address() as AddressInfo).port; await new Promise<void>(resolve => holder.close(() => resolve()));
    child = spawn(process.execPath, [path.join(app, "server.js")], { cwd: app, env: { ...env, PORT: String(port) }, stdio: ["ignore", "pipe", "pipe"] });
    child.stdout?.on("data", chunk => { serverOutput += chunk.toString(); }); child.stderr?.on("data", chunk => { serverOutput += chunk.toString(); });
    const base = "http://127.0.0.1:" + port;
    let healthy = false;
    for (let i = 0; i < 80; i++) { try { if ((await fetch(base + "/api/health/live")).ok) { healthy = true; break; } } catch {}
      if (child.exitCode !== null || child.signalCode !== null) break;
      await new Promise(resolve => setTimeout(resolve, 100)); }
    assert(healthy, "Owned production fixture unavailable: " + serverOutput.replaceAll(marker, "[synthetic-private]").slice(0, 1600));
    const request = (route: string, method = "GET", body?: unknown, cookie?: string) => fetch(base + route, { method,
      headers: { ...(cookie ? { cookie } : {}), ...(body === undefined ? {} : { "content-type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const registered = await request("/api/auth/register", "POST", { username: "fixture-admin", password: "synthetic-fixture-password" });
    assert.equal(registered.status, 201);
    const cookie = registered.headers.get("set-cookie")!.split(";")[0];
    const second = await request("/api/users", "POST", { username: "fixture-scoped", password: "synthetic-fixture-password", role: "write" }, cookie);
    assert.equal(second.status, 201);
    await db.user.update({ where: { username: "fixture-scoped" }, data: { role: "write", engineAdmin: false } });
    const login = await request("/api/auth/login", "POST", { username: "fixture-scoped", password: "synthetic-fixture-password" });
    assert.equal(login.status, 200); const scoped = login.headers.get("set-cookie")!.split(";")[0];
    assert.equal((await request("/api/deploy/start", "POST", { playbook: "site.yml" }, scoped)).status, 403);
    for (const body of [{ playbook: "../" + marker }, { roles: [marker] }, { roles: ["dns", "dns"] }]) {
      const rejected = await request("/api/deploy/start", "POST", body, cookie);
      assert.equal(rejected.status, 400); assert(!(await rejected.text()).includes(marker));
    }
    assert.equal(await db.job.count(), 0); assert.equal((await fixture.calls()).length, 0);
    async function start(mode: "success" | "failed" | "unsupported" | "slow") {
      await fixture.mode(mode);
      const response = await request("/api/deploy/start", "POST", { playbook: "site.yml", roles: ["kubernetes", "dns"] }, cookie);
      assert.equal(response.status, 200); return (await response.json()).jobId as string;
    }
    async function finished(id: string) {
      for (let i = 0; i < 100; i++) { const row = await db!.job.findUniqueOrThrow({ where: { id } }); if (row.status !== "running") return row; await new Promise(resolve => setTimeout(resolve, 100)); }
      throw new Error("Synthetic provisioning job did not finish");
    }
    for (const mode of ["success", "failed", "unsupported"] as const) {
      const id = await start(mode), row = await finished(id);
      assert(!row.output.includes(marker)); assert(row.output.length < 2048); assert(row.output.includes("Raw runner output withheld"));
      assert.equal(row.status, mode === "success" ? "success" : "failed", JSON.stringify({ mode,
        started: row.output.includes("Provisioning started"), unavailable: row.output.includes("Supported progress unavailable"),
        couldNotStart: row.output.includes("could not start"), callbackSafe: await fixture.callbackSafe().catch(() => false), calls: (await fixture.calls()).length }));
      assert(row.finishedAt);
      assert(row.output.includes(mode === "success" ? "Provisioning completed" : "Provisioning failed"));
      if (mode === "unsupported") assert(row.output.includes("Supported progress unavailable"));
      const tail = await request("/api/deploy/history?jobId=" + id, "GET", undefined, cookie);
      assert.equal(tail.status, 200); assert(!(await tail.text()).includes(marker));
      const stream = await request("/api/deploy/stream?jobId=" + id, "GET", undefined, cookie);
      assert.equal(stream.status, 200); const frames = await stream.text(); assert(!frames.includes(marker)); assert(frames.includes('"done":true'));
      assert.equal((await request("/api/deploy/stream?jobId=" + id, "GET", undefined, scoped)).status, 403);
    }
    const cancelled = await start("slow");
    for (let i = 0; i < 50 && (await fixture.calls()).length < 4; i++) await new Promise(resolve => setTimeout(resolve, 50));
    assert.equal((await request("/api/deploy/stop?jobId=" + cancelled, "POST", undefined, cookie)).status, 202);
    const cancelledRow = await finished(cancelled); assert.equal(cancelledRow.status, "failed");
    assert(cancelledRow.output.includes("cancelled; inspect partial effects")); assert(!cancelledRow.output.includes(marker));
    assert.deepEqual((await request("/api/deploy/start", "GET", undefined, cookie).then(response => response.json())).activeJobIds, []);
    const calls = await fixture.calls(); assert.equal(calls.length, 4);
    assert(!JSON.stringify(calls).includes(marker)); assert(calls.every(argv => argv.includes("kubernetes,dns") && !argv.includes("--extra-vars")));
    assert(await fixture.callbackSafe()); assert(!serverOutput.includes(marker));
    const yaml = await readFile(path.join(dir, "ansible-playbook", "group_vars", "all.yml"), "utf8");
    const inventory = await readFile(path.join(dir, "ansible-playbook", "inventory", "production.ini"), "utf8");
    assert(!yaml.includes(marker)); assert(!inventory.includes(marker));
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) { child.kill(); await once(child, "exit"); }
    await db?.$disconnect();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-ansible-http-")) throw new Error("Unsafe provisioning fixture cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});
