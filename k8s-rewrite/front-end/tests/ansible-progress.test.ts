import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { type ChildProcess } from "node:child_process";
import { ansibleSelection, ANSIBLE_ROLES } from "../src/lib/ansible-selection";
import { observeAnsibleProcess } from "../src/lib/ansible-progress";

function fixture(signal?: AbortSignal) {
  const child = new EventEmitter() as ChildProcess;
  child.stdout = new PassThrough(); child.stderr = new PassThrough();
  const kills: string[] = []; child.kill = ((kind: string) => { kills.push(kind); return true; }) as ChildProcess["kill"];
  let cleanup = 0;
  const events = observeAnsibleProcess(child, signal, () => { cleanup++; });
  const data: string[] = [], roles: unknown[] = [], closed: { exitCode: number | null; fullOutput: string }[] = [];
  events.on("data", text => data.push(text)); events.on("role-progress", role => roles.push(role)); events.on("close", result => closed.push(result));
  return { child, kills, data, roles, closed, cleanup: () => cleanup };
}
const protocol = (text: string) => "BORTUS_PROGRESS_V1 " + text + "\n";
const marker = "private-arbitrary-credential-fixture";

test("provisioning selection is fixed public metadata and rejects paths/options/private role values", () => {
  assert.deepEqual(ansibleSelection(), { playbook: "site.yml", roles: [] });
  assert.deepEqual(ansibleSelection("site.yml", [...ANSIBLE_ROLES]), { playbook: "site.yml", roles: [...ANSIBLE_ROLES] });
  for (const [playbook, roles] of [["../../" + marker + ".yml", []], ["--extra-vars", []], ["site.yml", [marker]], ["site.yml", ["dns", "dns"]], ["site.yml", "dns"], [null, []]]) {
    assert.throws(() => ansibleSelection(playbook, roles), error => error instanceof Error && !error.message.includes(marker));
  }
});

test("only exact producer records survive split chunks, malformed frames and arbitrary stdout/stderr", () => {
  const run = fixture();
  run.child.stdout!.emit("data", Buffer.from("TASK [" + marker + " : secret label]\nok: [" + marker + "] => {\"stdout\":\"" + marker + "\"}\n"));
  run.child.stderr!.emit("data", Buffer.from("module stderr " + marker));
  const start = Buffer.from(protocol("start"));
  for (const byte of start) run.child.stdout!.emit("data", Buffer.from([byte]));
  run.child.stdout!.emit("data", Buffer.from(protocol("role:kubernetes:running").repeat(500)));
  run.child.stdout!.emit("data", Buffer.from(protocol("role:" + marker + ":running") + protocol("role:dns:running") + protocol("role:dns:success")));
  // A large single line is discarded with at most 160 buffered bytes, then parsing resumes.
  run.child.stdout!.emit("data", Buffer.from(marker.repeat(100000) + "\n" + protocol("complete:success")));
  run.child.emit("close", 0);
  assert.equal(run.closed.length, 1); assert.equal(run.closed[0].exitCode, 0);
  assert.equal(run.closed[0].fullOutput, run.data.join(""));
  assert(!JSON.stringify([run.closed, run.roles, run.data]).includes(marker));
  assert.deepEqual(run.roles, [{ role: "kubernetes", status: "running" }, { role: "dns", status: "running" }, { role: "kubernetes", status: "success" }, { role: "dns", status: "success" }]);
  assert(run.closed[0].fullOutput.includes("Raw runner output withheld"));
  assert(run.closed[0].fullOutput.length < 1024); assert.equal(run.cleanup(), 1);
  assert.equal(run.child.stdout!.listenerCount("data"), 0); assert.equal(run.child.listenerCount("close"), 0);
});

test("unsupported/raw-only zero exit fails closed and valid progress cannot override failed process/role state", () => {
  for (const [records, code] of [[marker + "\n", 0], [protocol("start"), 0], [protocol("start") + protocol("complete:success"), 7], [protocol("start") + protocol("role:secrets:failed") + protocol("role:secrets:running") + protocol("complete:success"), 0]] as const) {
    const run = fixture(); run.child.stdout!.emit("data", Buffer.from(records)); run.child.emit("close", code);
    assert.notEqual(run.closed[0].exitCode, 0); assert(run.closed[0].fullOutput.includes("Provisioning failed"));
    assert(!run.closed[0].fullOutput.includes(marker));
  }
});

test("LF and CRLF accept the same exact records; embedded controls and private suffixes never become progress", () => {
  const run = fixture();
  run.child.stdout!.emit("data", Buffer.from(protocol("start").replace("\n", "\r\n") + protocol("role:network:running").replace("\n", "\r\n")));
  run.child.stdout!.emit("data", Buffer.from(protocol("role:dns:\rrunning") + protocol("role:secrets:running:" + marker)));
  run.child.stdout!.emit("data", Buffer.from(protocol("complete:success").replace("\n", "\r\n"))); run.child.emit("close", 0);
  assert.equal(run.closed[0].exitCode, 0); assert(!run.closed[0].fullOutput.includes(marker));
  assert.deepEqual(run.roles, [{ role: "network", status: "running" }, { role: "network", status: "success" }]);
});

test("spawn errors never echo exception text; cancellation stays pending until child closes and cleanup is singular", () => {
  const failed = fixture(); failed.child.emit("error", new Error(marker)); failed.child.emit("close", 0);
  assert.equal(failed.closed.length, 1); assert.equal(failed.cleanup(), 1); assert(!failed.closed[0].fullOutput.includes(marker));
  assert(failed.closed[0].fullOutput.includes("could not start"));
  const signal = new AbortController(), run = fixture(signal.signal);
  run.child.stdout!.emit("data", Buffer.from(protocol("start") + protocol("role:bootstrap:running")));
  signal.abort(); assert.deepEqual(run.kills, ["SIGTERM"]); assert.equal(run.closed.length, 0);
  run.child.stdout!.emit("data", Buffer.from(protocol("complete:success"))); run.child.emit("close", 0);
  assert.notEqual(run.closed[0].exitCode, 0); assert(run.closed[0].fullOutput.includes("cancelled; inspect partial effects"));
  assert.equal(run.cleanup(), 1);
  run.child.stdout!.emit("data", Buffer.from(marker)); assert(!run.closed[0].fullOutput.includes(marker));
});
