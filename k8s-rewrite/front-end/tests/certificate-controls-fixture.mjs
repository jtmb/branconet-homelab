/**
 * Bounded component/HTTP interaction fixture. No production data or credentials.
 * Uses existing test dependencies; bundles only in memory. Not a Next build or
 * production styling/accessibility qualification. Run only on loopback.
 */
import { createRequire } from "node:module";
import { createServer } from "node:http";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const dependencyRoot = process.env.BORTUS_TEST_DEPENDENCIES;
if (!dependencyRoot) throw Error("Existing BORTUS_TEST_DEPENDENCIES required; no dependency installation");
const require = createRequire(path.join(dependencyRoot, "package.json"));
const esbuild = require("esbuild");
const component = path.join(root, "src/app/(dashboard)/certificates/monitor-controls.tsx");
const serverModule = esbuild.buildSync({
  entryPoints: [path.join(root, "src/lib/certificate-control.ts")],
  bundle: true, write: false, platform: "node", format: "cjs", target: "node22",
}).outputFiles[0].text;
const loaded = new Module(path.join(dependencyRoot, "bortus-certificate-controls.cjs"));
loaded.filename = path.join(dependencyRoot, "bortus-certificate-controls.cjs");
loaded._compile(serverModule, loaded.filename);
const { certificateControls, certificatePolicyResponse, CERTIFICATE_POLICY_NAME: POLICY,
  CERTIFICATE_OBSERVATIONS_NAME: OBSERVATIONS } = loaded.exports;
const original = { version: 1, mode: "monitor", scanIntervalSeconds: 300, expiryWarningDays: 7 };
let policy, monitor, forceConflict = false, revoke = false;
function reset() {
  policy = { kind: "ConfigMap", metadata: { name: POLICY, namespace: "bortus", uid: "policy-uid", resourceVersion: "10" },
    data: { "policy.json": JSON.stringify(original), "audit.json": "[]" } };
  monitor = { version: 1, heartbeatAt: new Date().toISOString(), policy: { uid: "policy-uid", revision: "10" }, mode: "monitor",
    sources: ["certificates.cert-manager.io", "certificatesigningrequests.certificates.k8s.io"].map(resource =>
      ({ resource, checkedAt: new Date().toISOString(), available: true })),
    observations: [{ resource: "certificates.cert-manager.io", uid: "cert-one", name: "lan-tls", namespace: "whoami",
      state: "healthy", notAfter: new Date(Date.now() + 60 * 86400000).toISOString(), observedAt: new Date().toISOString() }],
    notificationsPending: 0, lastRun: { id: "fixture-run", startedAt: new Date().toISOString(), finishedAt: new Date().toISOString(), state: "complete" } };
  forceConflict = false; revoke = false;
}
reset();
const read = async args => args[2] === POLICY ? structuredClone(policy) : {
  kind: "ConfigMap", metadata: { name: OBSERVATIONS, namespace: "bortus", uid: "observations-uid", resourceVersion: "20" },
  data: { "snapshot.json": JSON.stringify(monitor) },
};
const patch = async args => {
  const operations = JSON.parse(args.at(-1));
  if (forceConflict || operations[0].value !== policy.metadata.uid || operations[1].value !== policy.metadata.resourceVersion)
    throw Object.assign(Error("synthetic conflict"), { status: 409 });
  policy.data["policy.json"] = operations[2].value;
  policy.data["audit.json"] = operations[3].value;
  policy.metadata.resourceVersion = String(Number(policy.metadata.resourceVersion) + 1);
  return structuredClone(policy);
};
const bundle = (await esbuild.build({
  stdin: { contents: `
import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import MonitorControls from ${JSON.stringify(component)};
function App(){
 const [controls,setControls]=useState(null);
 const refresh=async()=>{const r=await fetch("/fixture/controls");setControls(await r.json());};
 useEffect(()=>{void refresh();},[]);
 return controls?<main><h1>Certificate controls interaction fixture</h1><p>No production data; component/API boundary only, not production styling.</p><MonitorControls controls={controls} canManage={location.pathname==="/operator"} refresh={refresh}/></main>:<p role="status">Loading fixture…</p>;
}
createRoot(document.getElementById("root")).render(<App/>);`, loader: "tsx", resolveDir: dependencyRoot },
  bundle: true, write: false, platform: "browser", format: "iife", jsx: "automatic",
  nodePaths: [path.join(dependencyRoot, "node_modules")], define: { "process.env.NODE_ENV": '"production"' },
})).outputFiles[0].contents;
const server = createServer(async (incoming, outgoing) => {
  const origin = `http://127.0.0.1:${server.address().port}`;
  const url = new URL(incoming.url ?? "/", origin);
  const operator = incoming.headers.cookie?.includes("fixtureOperator=1") && !revoke;
  const json = (status, value) => { outgoing.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" }); outgoing.end(JSON.stringify(value)); };
  try {
    if (url.pathname === "/bundle.js") { outgoing.writeHead(200, { "Content-Type": "application/javascript" }); outgoing.end(bundle); return; }
    if (url.pathname === "/fixture/controls") { json(200, await certificateControls(read)); return; }
    if (url.pathname === "/api/certificates/policy") {
      let size = 0; const chunks = [];
      for await (const chunk of incoming) { size += chunk.length; if (size > 8192) { json(413, { error: "Fixture request too large" }); return; } chunks.push(chunk); }
      const request = new Request(origin + url.pathname, { method: "PATCH", headers: { origin: incoming.headers.origin ?? "" }, body: Buffer.concat(chunks) });
      const response = await certificatePolicyResponse(request, {
        authorize: async () => operator ? { id: "fixture-operator" } : Response.json({ error: "Engine administration required" }, { status: 403 }),
        read, patch,
      });
      outgoing.writeHead(response.status, Object.fromEntries(response.headers)); outgoing.end(await response.text()); return;
    }
    if (url.pathname === "/fixture/control" && incoming.method === "POST") {
      const action = url.searchParams.get("action");
      if (action === "reset") reset();
      else if (action === "conflict") forceConflict = true;
      else if (action === "revoke") revoke = true;
      else if (action === "offline") monitor.heartbeatAt = new Date(Date.now() - 300000).toISOString();
      else if (action === "ack") {
        monitor.policy = { uid: policy.metadata.uid, revision: policy.metadata.resourceVersion };
        monitor.mode = JSON.parse(policy.data["policy.json"]).mode;
        monitor.heartbeatAt = new Date().toISOString();
      } else { json(400, { error: "Unknown fixture action" }); return; }
      json(200, { action }); return;
    }
    if (!["/operator", "/reader"].includes(url.pathname)) { json(404, { error: "Fixture route not found" }); return; }
    outgoing.writeHead(200, { "Content-Type": "text/html", "Cache-Control": "no-store",
      "Set-Cookie": `fixtureOperator=${url.pathname === "/operator" ? "1" : "0"}; HttpOnly; SameSite=Strict; Path=/`,
      "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'" });
    outgoing.end('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BORTUS certificate control fixture</title><style>body{font:16px system-ui;max-width:1000px;margin:24px auto;padding:16px}input,select,button{font:inherit;margin:8px;padding:8px}fieldset{display:flex;flex-wrap:wrap;gap:16px}label{display:block}dt{font-weight:bold}details{margin:16px 0}:focus-visible{outline:3px solid #4848dd}li{margin:8px 0}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>');
  } catch {
    json(500, { error: "Fixture failed" });
  }
});
server.listen(Number(process.env.PORT ?? 21583), "127.0.0.1", () => {
  console.log(`CERTIFICATE_CONTROLS_FIXTURE_READY http://127.0.0.1:${server.address().port}`);
});
process.on("SIGTERM", () => server.close(() => process.exit(0)));
