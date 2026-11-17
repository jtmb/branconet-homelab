import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  CERTIFICATE_POLICY_NAME as POLICY, CERTIFICATE_OBSERVATIONS_NAME as OBSERVATIONS,
  certificateControls, certificatePolicyResponse, monitorView, updateCertificatePolicy,
  monitoringPolicy,
} from "../src/lib/certificate-control.ts";

const now = Date.parse("2026-11-16T12:00:00Z");
const desired = { version: 1, mode: "monitor", scanIntervalSeconds: 300, expiryWarningDays: 7 };
const cm = (name, data, revision = "10") => ({ kind: "ConfigMap",
  metadata: { name, namespace: "bortus", uid: name + "-uid", resourceVersion: revision }, data });
const policy = () => cm(POLICY, { "policy.json": JSON.stringify(desired), "audit.json": "[]" });
const snapshot = () => ({
  version: 1, heartbeatAt: new Date(now).toISOString(), policy: { uid: POLICY + "-uid", revision: "10" }, mode: "monitor",
  sources: ["certificates.cert-manager.io", "certificatesigningrequests.certificates.k8s.io"].map(resource =>
    ({ resource, checkedAt: new Date(now).toISOString(), available: true })),
  observations: [], notificationsPending: 0,
  lastRun: { id: "scan-1", startedAt: new Date(now).toISOString(), finishedAt: new Date(now).toISOString(), state: "complete" },
});
const reader = (status = snapshot(), requested = policy()) => async args => args[2] === POLICY
  ? requested : cm(OBSERVATIONS, { "snapshot.json": JSON.stringify(status) });

test("effective state requires a fresh heartbeat, complete sources and acknowledgement of the exact requested policy", async () => {
  assert.equal((await certificateControls(reader(), now)).state, "monitoring");
  const stale = snapshot(); stale.heartbeatAt = new Date(now - 181000).toISOString();
  assert.equal((await certificateControls(reader(stale), now)).state, "offline");
  const drift = snapshot(); drift.policy.revision = "9";
  assert.equal((await certificateControls(reader(drift), now)).state, "pending");
  const degraded = snapshot(); degraded.sources[0].available = false;
  assert.equal((await certificateControls(reader(degraded), now)).state, "degraded");
  degraded.sources[0].available = true; degraded.sources[0].checkedAt = new Date(now - 901000).toISOString();
  assert.equal((await certificateControls(reader(degraded), now)).state, "degraded");
  const paused = snapshot(); paused.mode = "paused";
  const requested = policy(); requested.data["policy.json"] = JSON.stringify({ ...desired, mode: "paused" });
  assert.equal((await certificateControls(reader(paused, requested), now)).state, "paused");
});

test("missing policy is not implicitly enabled and malformed snapshots cannot become a healthy monitor", async () => {
  assert.equal((await certificateControls(async () => { throw Error("private backend"); }, now)).state, "unavailable");
  const malformed = snapshot(); malformed.sources.push(malformed.sources[0]);
  assert.equal((await certificateControls(reader(malformed), now)).state, "offline");
  const projected = snapshot(); projected.secret = "never-return-this";
  assert.ok(!JSON.stringify(monitorView(cm(OBSERVATIONS, { "snapshot.json": JSON.stringify(projected) }), now)).includes("never-return-this"));
});

test("policy mode is an exact enum, not a coerced array or approval capability", () => {
  for (const mode of [["monitor"], "approve-all", true, null]) {
    assert.throws(() => monitoringPolicy({ ...desired, mode }), error => error.status === 400);
  }
  assert.throws(() => monitoringPolicy({ ...desired, approvalEnabled: true }), error => error.status === 400);
});

test("operator saves target only the fixed policy, compare UID/revision and preserve an audit record", async () => {
  let mutation;
  const changed = { ...desired, mode: "paused", expiryWarningDays: 10 };
  const updated = await updateCertificatePolicy(reader(), async args => {
    mutation = args;
    const operations = JSON.parse(args.at(-1));
    return cm(POLICY, { "policy.json": operations[2].value, "audit.json": operations[3].value }, "11");
  }, { uid: POLICY + "-uid", revision: "10", policy: changed }, "operator-1", now);
  assert.deepEqual(mutation.slice(0, 7), ["patch", "configmap", POLICY, "-n", "bortus", "--type=json", "-p"]);
  assert.deepEqual(JSON.parse(mutation.at(-1)).slice(0, 2), [
    { op: "test", path: "/metadata/uid", value: POLICY + "-uid" },
    { op: "test", path: "/metadata/resourceVersion", value: "10" },
  ]);
  assert.equal(updated.revision, "11");
  assert.equal(updated.audit[0].actor, "operator-1");
  assert.equal(updated.desired.mode, "paused");
  await assert.rejects(updateCertificatePolicy(reader(), () => { throw Error("must not mutate"); },
    { uid: POLICY + "-uid", revision: "9", policy: changed }, "operator-1", now), error => error.status === 409);
});

test("HTTP policy writes authenticate before reading, reject cross-origin/oversized bodies and never expose backend errors", async () => {
  let reads = 0, writes = 0;
  const dependencies = { authorize: async () => Response.json({ error: "Operator required" }, { status: 403 }),
    read: async () => { reads++; return policy(); }, patch: async () => { writes++; throw Error("private backend token"); } };
  const request = (body, origin = "https://bortus.branconet.lan") => new Request("https://bortus.branconet.lan/api/certificates/policy",
    { method: "PATCH", headers: { origin }, body });
  assert.equal((await certificatePolicyResponse(request("{}"), dependencies)).status, 403);
  assert.equal(reads, 0); assert.equal(writes, 0);
  dependencies.authorize = async () => ({ id: "operator-1" });
  assert.equal((await certificatePolicyResponse(request("{}", "https://attacker.invalid"), dependencies)).status, 403);
  assert.equal((await certificatePolicyResponse(request(" ".repeat(4097)), dependencies)).status, 413);
  assert.equal(reads, 0); assert.equal(writes, 0);
  const response = await certificatePolicyResponse(request(JSON.stringify({ uid: POLICY + "-uid", revision: "10", policy: desired })), dependencies);
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes("private backend token"));
  assert.equal(writes, 1);
});

test("real Python monitor publication is consumed by BORTUS without a duplicate snapshot schema", () => {
  const path = fileURLToPath(new URL("../../../scripts/migration", import.meta.url));
  const raw = execFileSync("python3", ["-B", "-c", `
import json,sqlite3,sys,datetime as dt
sys.path.insert(0,sys.argv[1])
from certificate_monitor import CertificateMonitor
from certificate_monitor_control import control_cycle,POLICY_NAME,OBSERVATIONS_NAME
now=dt.datetime(2026,11,16,12,tzinfo=dt.timezone.utc)
def get(name):
    data={'policy.json':json.dumps({'version':1,'mode':'monitor','scanIntervalSeconds':300,'expiryWarningDays':7})} if name==POLICY_NAME else {}
    return {'kind':'ConfigMap','metadata':{'name':name,'namespace':'bortus','uid':name+'-uid','resourceVersion':'10'},'data':data}
def patch(name,ops): print(json.dumps({'kind':'ConfigMap','metadata':{'name':name,'namespace':'bortus','uid':name+'-uid','resourceVersion':'11'},'data':{'snapshot.json':ops[-1]['value']}}))
with sqlite3.connect(':memory:') as db: control_cycle(CertificateMonitor(db),lambda resource:{'items':[]},get,patch,now)
`, path], { encoding: "utf8" });
  const view = monitorView(JSON.parse(raw), now);
  assert.equal(view.policyRevision, "10"); assert.equal(view.mode, "monitor");
  assert.equal(view.sources.length, 2); assert.equal(view.lastRun.state, "complete");
  assert.equal(view.notificationsPending, 0);
});
