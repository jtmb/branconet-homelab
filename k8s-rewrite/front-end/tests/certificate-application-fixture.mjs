/**
 * Real built Next application + current Prisma/auth, synthetic local cluster.
 * H fixture state only; no production kubeconfig/Secret/identity is supplied.
 * Run from the frontend, inside its qualified dependency/build mounts.
 */
import fs from "node:fs";
import path from "node:path";
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { once } from "node:events";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";

const root = process.cwd(), base = process.env.BORTUS_CERTIFICATE_FIXTURE_DIR;
if (!base || !base.startsWith("/artifacts/")) throw Error("Explicit H-backed fixture directory required");
fs.mkdirSync(base, { mode: 0o700 });
const require = createRequire(path.join(root, "package.json"));
const { PrismaClient } = require("@prisma/client");
const bcrypt = require("bcryptjs");
const bin = path.join(base, "bin");
fs.mkdirSync(bin, { mode: 0o700 });
const now = () => new Date().toISOString();
const policyName = "bortus-certificate-policy", observationsName = "bortus-certificate-observations";
const objectPath = name => path.join(bin, name + ".json");
const read = name => JSON.parse(fs.readFileSync(objectPath(name), "utf8"));
const write = (name, value) => fs.writeFileSync(objectPath(name), JSON.stringify(value));
const map = (name, data) => ({ kind: "ConfigMap", apiVersion: "v1",
  metadata: { name, namespace: "bortus", uid: name + "-fixture-uid", resourceVersion: "10" }, data });
write(policyName, map(policyName, { "policy.json": JSON.stringify({
  version: 1, mode: "monitor", scanIntervalSeconds: 300, expiryWarningDays: 7,
}), "audit.json": "[]" }));
write(observationsName, map(observationsName, { "snapshot.json": JSON.stringify({
  version: 1, heartbeatAt: now(), policy: { uid: policyName + "-fixture-uid", revision: "10" }, mode: "monitor",
  sources: ["certificates.cert-manager.io", "certificatesigningrequests.certificates.k8s.io"].map(resource =>
    ({ resource, checkedAt: now(), available: true })),
  observations: [{ resource: "certificates.cert-manager.io", uid: "certificate-fixture", namespace: "whoami",
    name: "lan-tls", state: "healthy", observedAt: now(), notAfter: "2027-01-16T12:00:00Z" }],
  notificationsPending: 0, lastRun: { id: "fixture-scan", startedAt: now(), finishedAt: now(), state: "complete" },
}) }));
write("certificates.cert-manager.io", { kind: "CertificateList", items: [{
  metadata: { name: "lan-tls", namespace: "whoami", uid: "certificate-fixture" },
  spec: { dnsNames: ["whoami.branconet.lan"], issuerRef: { kind: "ClusterIssuer", name: "fixture-ca" } },
  status: { notAfter: "2027-01-16T12:00:00Z", renewalTime: "2027-01-01T12:00:00Z",
    conditions: [{ type: "Ready", status: "True" }] },
}] });
write("certificatesigningrequests.certificates.k8s.io", { kind: "CertificateSigningRequestList", items: [{
  metadata: { name: "pending-fixture", uid: "csr-fixture", creationTimestamp: now() },
  spec: { username: "system:node:fixture-node", signerName: "kubernetes.io/kubelet-serving" },
}] });
fs.writeFileSync(path.join(bin, "kubectl"), `#!/usr/local/bin/node
const fs=require('node:fs'),path=require('node:path');
const d=process.env.BORTUS_CERTIFICATE_FAKE_BIN,a=process.argv.slice(2),get=a.indexOf('get'),patch=a.indexOf('patch');
if(!d)process.exit(90);
if(get>=0){
 const resource=a[get+1],name=resource==='configmap'?a[get+2]:resource;
 if(!/^[a-z0-9.-]+$/.test(name))process.exit(1);
 const f=path.join(d,name+'.json');
 if(resource==='configmap'&&!fs.existsSync(f))process.exit(1);
 process.stdout.write(fs.existsSync(f)?fs.readFileSync(f,'utf8'):'{"items":[]}');process.exit(0);
}
if(patch>=0&&a[patch+1]==='configmap'&&a[patch+2]==='${policyName}'){
 const target=path.join(d,'${policyName}.json'),lock=target+'.lock';let fd;
 try{
  fd=fs.openSync(lock,'wx');
  const value=JSON.parse(fs.readFileSync(target,'utf8')),ops=JSON.parse(a[a.indexOf('-p')+1]);
  if(ops.length!==4||ops[0].path!=='/metadata/uid'||ops[1].path!=='/metadata/resourceVersion'||
     value.metadata.uid!==ops[0].value||value.metadata.resourceVersion!==ops[1].value)process.exitCode=1;
  else{
   if(ops[2].path!=='/data/policy.json'||ops[3].path!=='/data/audit.json')throw Error('invalid fixture patch');
   value.data['policy.json']=ops[2].value;value.data['audit.json']=ops[3].value;
   value.metadata.resourceVersion=String(Number(value.metadata.resourceVersion)+1);
   fs.writeFileSync(target,JSON.stringify(value));process.stdout.write(JSON.stringify(value));
  }
 }catch{process.exitCode=1}finally{if(fd!==undefined){fs.closeSync(fd);fs.unlinkSync(lock)}}
}else process.exit(1);
`, { mode: 0o700 });
const config = path.join(base, "kubeconfig.json"), database = "file:" + path.join(base, "synthetic.sqlite");
fs.writeFileSync(config, JSON.stringify({ apiVersion: "v1", kind: "Config", clusters: [], users: [], contexts: [] }));
const appPort = Number(process.env.BORTUS_CERTIFICATE_APP_PORT ?? 21585);
const controlPort = Number(process.env.BORTUS_CERTIFICATE_CONTROL_PORT ?? 21584);
const env = { ...process.env, DATABASE_URL: database, BOTRUS_JWT_SECRET: randomBytes(48).toString("hex"),
  BORTUS_DISABLE_PROVISIONING: "true", KUBECONFIG: config, BORTUS_CERTIFICATE_FAKE_BIN: bin,
  PATH: `${bin}:${process.env.PATH}`, PORT: String(appPort), HOSTNAME: "127.0.0.1", NODE_ENV: "production" };
delete env.KUBERNETES_SERVICE_HOST; delete env.KUBERNETES_SERVICE_PORT;
execFileSync(process.execPath, [path.join(root, "node_modules/prisma/build/index.js"), "migrate", "deploy"],
  { env, stdio: "pipe", timeout: 30000 });
const db = new PrismaClient({ datasources: { db: { url: database } } });
const password = "Certificate-fixture-only-2026";
const hash = await bcrypt.hash(password, 4);
const operator = await db.user.create({ data: { username: "certificate_operator", passwordHash: hash, role: "write", engineAdmin: true } });
await db.user.create({ data: { username: "certificate_reader", passwordHash: hash, role: "readonly" } });
await db.user.create({ data: { username: "certificate_scoped", passwordHash: hash, role: "write", engineAdmin: false } });
await db.appSetting.create({ data: { key: "allow_registration", value: "false" } });
const standalone = path.join(root, ".next/standalone");
for (const [target, source] of [[".next/static", path.join(root, ".next/static")], ["public", path.join(root, "public")]]) {
  const destination = path.join(standalone, target);
  if (!fs.existsSync(destination)) fs.symlinkSync(source, destination);
}
const child = spawn(process.execPath, [path.join(standalone, "server.js")], { env, stdio: ["ignore", "pipe", "pipe"] });
let serverOutput = "";
for (const stream of [child.stdout, child.stderr]) stream.on("data", value => { serverOutput = (serverOutput + value).slice(-16384); });
const control = createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    if (request.method !== "POST" || url.pathname !== "/control") { response.writeHead(404); response.end(); return; }
    const action = url.searchParams.get("action");
    if (action === "ack" || action === "offline") {
      const value = read(observationsName), snapshot = JSON.parse(value.data["snapshot.json"]);
      if (action === "ack") { const requested = read(policyName); snapshot.policy = { uid: requested.metadata.uid, revision: requested.metadata.resourceVersion };
        snapshot.mode = JSON.parse(requested.data["policy.json"]).mode; snapshot.heartbeatAt = now(); }
      else snapshot.heartbeatAt = new Date(Date.now() - 300000).toISOString();
      value.data["snapshot.json"] = JSON.stringify(snapshot); write(observationsName, value);
    } else if (action === "revoke-operator") await db.user.update({ where: { id: operator.id }, data: { engineAdmin: false } });
    else { response.writeHead(400); response.end(); return; }
    response.writeHead(204); response.end();
  } catch { response.writeHead(500); response.end("Synthetic fixture control failed"); }
});
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw Error("Built Next server exited: " + serverOutput);
    try { ready = (await fetch(`http://127.0.0.1:${appPort}/api/health/live`, { signal: AbortSignal.timeout(500) })).ok; } catch {}
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!ready) throw Error("Built Next server did not become ready");
  control.listen(controlPort, "127.0.0.1"); await once(control, "listening");
  console.log("CERTIFICATE_APPLICATION_FIXTURE_READY " + JSON.stringify({
    appUrl: `http://127.0.0.1:${appPort}`, controlUrl: `http://127.0.0.1:${controlPort}/control`,
    users: ["certificate_operator", "certificate_reader", "certificate_scoped"], password,
    realNextAuthAndPrisma: true, productionConnected: false,
  }));
  await new Promise(resolve => { process.once("SIGTERM", resolve); process.once("SIGINT", resolve); });
} finally {
  control.closeAllConnections(); control.close();
  if (child.exitCode === null) { child.kill("SIGTERM"); await once(child, "exit"); }
  await db.$disconnect();
}
