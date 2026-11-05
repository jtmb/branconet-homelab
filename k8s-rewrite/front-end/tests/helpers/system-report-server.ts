import { execFileSync, spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile, rm, chmod } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { once } from "node:events";
import net, { type AddressInfo } from "node:net";
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";
import { SignJWT } from "jose";
import { fakeKubectl } from "./fake-kubectl";
export const fixtureDigest = "sha256:" + "a".repeat(64);
export async function systemReportServer(port = 0) {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-report-http-"));
  const database = `file:${path.join(dir, "fixture.db").replaceAll("\\", "/")}`, secret = "public-disposable-system-report-test-only";
  const kubectl = await fakeKubectl(dir), cache = path.join(dir, "cache");
  await mkdir(path.join(cache, "db"), { recursive: true });
  const metadata = { Version: 2, UpdatedAt: new Date(Date.now() - 3600000).toISOString(), NextUpdate: new Date(Date.now() + 3600000).toISOString() };
  await writeFile(path.join(cache, "db", "metadata.json"), JSON.stringify(metadata));
  await writeFile(path.join(cache, "db", "trivy.db"), "fixture-only");
  const mode = path.join(dir, "scanner-mode"), calls = path.join(dir, "scanner-calls");
  await writeFile(mode, "complete");
  const scanner = path.join(dir, process.platform === "win32" ? "scanner.exe" : "scanner");
  const json = { SchemaVersion: 2, Trivy: { Version: "fixture-only" }, Metadata: { RepoDigests: [`example.invalid/api@${fixtureDigest}`] }, Results: [{ Target: "fixture OS", Packages: [{ Name: "zlib" }], Vulnerabilities: [
    { VulnerabilityID: "CVE-2022-37434", Severity: "CRITICAL", PkgName: "zlib", InstalledVersion: "1.2.12-r0", FixedVersion: "1.2.12-r2", PrimaryURL: "https://avd.aquasec.com/nvd/cve-2022-37434", Title: "Heap-based buffer overflow" },
    { VulnerabilityID: "CVE-FIXTURE-2", Severity: "HIGH", PkgName: "openssl", InstalledVersion: "1.0", PrimaryURL: "javascript:bad", Title: "Fixture only: no fix reported" },
  ] }] };
  if (process.platform === "win32") {
    const source = path.join(dir, "scanner.cs");
    await writeFile(source, `using System; using System.IO; using System.Threading;
class Scanner { static int Main() {
File.AppendAllText(${JSON.stringify(calls)},"scan\\n");
string mode=File.ReadAllText(${JSON.stringify(mode)}).Trim();
int count=0; while(mode=="hold" && count++<1500) { Thread.Sleep(20); mode=File.ReadAllText(${JSON.stringify(mode)}).Trim(); }
if(mode=="error") { Console.Error.Write("private-fixture-error-must-not-leak"); return 1; }
if(mode=="invalid") { Console.Write("not-json"); return 0; }
Console.Write(${JSON.stringify(JSON.stringify(json))});return 0;
}}`);
    execFileSync("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe", ["/nologo", `/out:${scanner}`, source], { timeout: 15000, stdio: "pipe" });
  } else {
    await writeFile(scanner, `#!${process.execPath}
const fs=require('node:fs');fs.appendFileSync(${JSON.stringify(calls)},'scan\\n');let mode=fs.readFileSync(${JSON.stringify(mode)},'utf8').trim(),count=0;
while(mode==='hold'&&count++<1500){Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,20);mode=fs.readFileSync(${JSON.stringify(mode)},'utf8').trim();}
if(mode==='error'){process.stderr.write('private-fixture-error-must-not-leak');process.exit(1);}process.stdout.write(mode==='invalid'?'not-json':${JSON.stringify(JSON.stringify(json))});`);
    await chmod(scanner, 0o755);
  }
  const pod = (name: string, ns: string, id = fixtureDigest) => ({ metadata: { name, namespace: ns, labels: { app: "api" }, ownerReferences: [{ controller: true, kind: "Deployment", name: "api" }] },
    spec: { containers: [{ name: "app", image: "example.invalid/api:1.0" }] }, status: { phase: "Running", containerStatuses: [{ name: "app", ready: true, imageID: id ? `example.invalid/api@${id}` : "", state: { running: { startedAt: new Date().toISOString() } } }] } });
  const pods = [pod("api-0", "apps"), pod("api-1", "apps"), pod("edge", "infra", "")];
  if (process.env.BORTUS_QA_STATE === "unavailable") await writeFile(path.join(kubectl.bin, "failure.txt"), "all");
  await writeFile(path.join(kubectl.bin, "pods.json"), JSON.stringify({ items: pods }));
  await writeFile(path.join(kubectl.bin, "services.json"), JSON.stringify({ items: [{ metadata: { name: "api", namespace: "apps" }, spec: { selector: { app: "api" } } }] }));
  const config = path.join(dir, "config"); await writeFile(config, "public fixture only");
  const env: NodeJS.ProcessEnv = { ...process.env, ...kubectl.env, DATABASE_URL: database, BOTRUS_JWT_SECRET: secret,
    KUBECONFIG: config, BORTUS_TRIVY_PATH: scanner, BORTUS_TRIVY_CACHE_DIR: cache, NEXT_TELEMETRY_DISABLED: "1", BORTUS_DISABLE_PROVISIONING: "true", NODE_ENV: "production", HOSTNAME: "127.0.0.1" };
  delete env.KUBERNETES_SERVICE_HOST; delete env.RUST_LOG;
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe", timeout: 30000 });
  const db = new PrismaClient({ datasources: { db: { url: database } } });
  const cookies: Record<string, string> = {};
  const passwordHash = await bcrypt.hash("public-fixture-password", 4);
  for (const [username, role, engineAdmin] of [["operator", "write", true], ["readonly", "readonly", false], ["scoped", "write", false]] as const) {
    const user = await db.user.create({ data: { username, role, engineAdmin, passwordHash } });
    const token = await new SignJWT({ sub: user.id, username, sessionVersion: 0 }).setProtectedHeader({ alg: "HS256" }).setIssuedAt().setExpirationTime("1h").sign(new TextEncoder().encode(secret));
    cookies[username] = `botrus_auth_token=${token}`;
  }
  if (!port) {
    const holder = net.createServer(); holder.listen(0, "127.0.0.1"); await once(holder, "listening");
    port = (holder.address() as AddressInfo).port; await new Promise<void>(r => holder.close(() => r()));
  }
  let log = "";
  const child = spawn(process.execPath, [path.resolve(".next/standalone/server.js")], { env: { ...env, PORT: String(port) }, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", chunk => { log = (log + chunk).slice(-65536); }); child.stderr.on("data", chunk => { log = (log + chunk).slice(-65536); });
  const base = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(`${base}/api/health/live`)).ok) break; } catch { /* Wait for owned local server. */ }
    if (child.exitCode !== null || attempt === 99) throw Error("Disposable report server failed to start");
    await new Promise(r => setTimeout(r, 100));
  }
  return { base, dir, db, mode, calls, cache, scanner, kubectl, pods, cookies, logs: () => log,
    async stop() {
      if (child.exitCode === null) { child.kill(); await once(child, "exit"); }
      await db.$disconnect(); await rm(dir, { recursive: true, force: true });
    } };
}
