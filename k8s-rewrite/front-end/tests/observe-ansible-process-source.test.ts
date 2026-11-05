import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";

// Only the exact declaration runs. All process/event/signal objects are PUBLIC fakes.
const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "An explicit compiler infrastructure binding is required");
const ts = createRequire(import.meta.url)(compilerPath) as typeof import("typescript");
const sourcePath = fileURLToPath(new URL("../src/lib/ansible-progress.ts", import.meta.url));
const source = ts.createSourceFile(sourcePath, readFileSync(sourcePath, "utf8"), ts.ScriptTarget.Latest, true);
const declarations = source.statements.filter((node): node is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "observeAnsibleProcess"
  && !!node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(declarations.length, 1);
const selected = declarations[0].getText(source).replace(/^export\s+/, "");
const compiled = ts.transpileModule(selected, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None }, reportDiagnostics: true,
});
assert.equal(compiled.diagnostics?.length, 0);
const roles = Object.freeze(["bootstrap", "kubernetes", "network", "dns", "storage", "longhorn", "nfs", "samba", "ingress", "gitops", "secrets"]);
const prefix = "BORTUS_PROGRESS_V1 ";
for (const [name, expected] of [["PREFIX", JSON.stringify(prefix)], ["LINE_BYTES", "160"]]) {
  const values = source.statements.filter(ts.isVariableStatement).flatMap(n => [...n.declarationList.declarations])
    .filter(n => n.name.getText(source) === name);
  assert.equal(values.length, 1);
  assert.equal(values[0].initializer?.getText(source), expected);
}

type Listener = (...args: unknown[]) => void;
class Events {
  listeners = new Map<string, Listener[]>();
  trace: string[];
  label: string;
  constructor(trace: string[] = [], label = "emitter") { this.trace = trace; this.label = label; }
  on(name: string, listener: Listener) {
    this.trace.push(`${this.label}.on:${name}`);
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]); return this;
  }
  removeListener(name: string, listener: Listener) {
    this.trace.push(`${this.label}.remove:${name}`);
    this.listeners.set(name, (this.listeners.get(name) ?? []).filter(x => x !== listener)); return this;
  }
  emit(name: string, ...args: unknown[]) {
    this.trace.push(`${this.label}.emit:${name}`);
    for (const listener of [...(this.listeners.get(name) ?? [])]) listener(...args);
    return (this.listeners.get(name)?.length ?? 0) > 0;
  }
  count() { return [...this.listeners.values()].reduce((n, x) => n + x.length, 0); }
}
class PublicProcess extends Events {
  stdout: Events | null;
  stderr: Events | null;
  kills: unknown[] = [];
  constructor(trace: string[]) {
    super(trace, "proc"); this.stdout = new Events(trace, "stdout"); this.stderr = new Events(trace, "stderr");
  }
  kill(signal: unknown) { this.trace.push(`proc.kill:${signal}`); this.kills.push(signal); return true; }
}
class PublicSignal {
  aborted = false;
  listeners: Listener[] = [];
  trace: string[];
  constructor(trace: string[]) { this.trace = trace; }
  addEventListener(name: string, fn: Listener, options: unknown) {
    assert.equal(name, "abort"); assert.equal((options as { once: boolean }).once, true);
    this.trace.push("signal.add:abort:once"); this.listeners.push(fn);
  }
  removeEventListener(name: string, fn: Listener) {
    assert.equal(name, "abort"); this.trace.push("signal.remove:abort"); this.listeners = this.listeners.filter(x => x !== fn);
  }
  abort() { this.aborted = true; for (const fn of [...this.listeners]) fn(); }
}
type Observe = (proc: PublicProcess, signal?: PublicSignal, onClose?: () => void) => Events;
function load(bindings: Record<string, unknown> = {}): Observe {
  return vm.runInNewContext(`${compiled.outputText}\nobserveAnsibleProcess;`, {
    EventEmitter: Events, Map, Buffer, ANSIBLE_ROLES: roles, PREFIX: prefix, LINE_BYTES: 160, ...bindings,
  }, { timeout: 1000 }) as Observe;
}
type CloseRecord = { exitCode: number; fullOutput: string };
function fixture(options: { signal?: boolean; aborted?: boolean; stdout?: boolean; stderr?: boolean; observe?: Observe; defaultClose?: boolean } = {}) {
  const trace: string[] = [], proc = new PublicProcess(trace), signal = options.signal ? new PublicSignal(trace) : undefined;
  if (options.stdout === false) proc.stdout = null;
  if (options.stderr === false) proc.stderr = null;
  if (signal) signal.aborted = options.aborted ?? false;
  let callbackCount = 0;
  const emitter = (options.observe ?? load())(proc, signal, options.defaultClose ? undefined : () => { trace.push("onClose"); callbackCount++; });
  emitter.trace = trace;
  const data: string[] = [], progress: { role: string; status: string }[] = [], closed: CloseRecord[] = [];
  emitter.on("data", text => { trace.push("consumer.data"); data.push(text as string); });
  emitter.on("role-progress", value => { trace.push("consumer.role"); progress.push(value as { role: string; status: string }); });
  emitter.on("close", value => { trace.push("consumer.close"); closed.push(value as CloseRecord); });
  const bytes = (value: Buffer) => proc.stdout?.emit("data", value);
  const text = (value: string) => bytes(Buffer.from(value, "utf8"));
  const record = (value: string, ending = "\n") => text(prefix + value + ending);
  const close = (code: unknown = 0) => proc.emit("close", code);
  return { trace, proc, signal, emitter, data, progress, closed, bytes, text, record, close, callbacks: () => callbackCount };
}
function result(f: ReturnType<typeof fixture>, code: number, expected: string) {
  assert.equal(f.closed.length, 1); assert.equal(f.closed[0].exitCode, code);
  assert.equal(f.closed[0].fullOutput, expected); assert.equal(f.data.join(""), expected);
  assert.equal(f.proc.count(), 0); assert.equal(f.proc.stdout?.count() ?? 0, 0); assert.equal(f.proc.stderr?.count() ?? 0, 0);
  assert.equal(f.signal?.listeners.length ?? 0, 0);
}
const started = "[Provisioning started]\n", done = "[Provisioning completed]\n", failed = "[Provisioning failed]\n";
const withheld = "[Raw runner output withheld]\n", unavailable = "[Supported progress unavailable; inspect the operator runner]\n";

test("source-derived registration order and optional abort listener", () => {
  const f = fixture({ signal: true });
  assert.deepEqual(f.trace.slice(0, 5), ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error", "signal.add:abort:once"]);
  f.close(); result(f, -1, unavailable + failed);
});
test("complete exact protocol succeeds without roles", () => {
  const f = fixture(); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, started + done); assert.equal(f.callbacks(), 1);
});
test("LF and CRLF framing have equal supported meaning", () => {
  const f = fixture(); f.record("start", "\r\n"); f.record("role:dns:running", "\r\n"); f.record("complete:success", "\r\n"); f.close();
  result(f, 0, started + "[Role dns: running]\n[Role dns: success]\n" + done);
});
const stream = prefix + "start\n" + prefix + "complete:success\n";
for (let split = 0; split <= Buffer.byteLength(stream); split++) test(`supported byte split ${split}`, () => {
  const f = fixture(), bytes = Buffer.from(stream); f.bytes(bytes.subarray(0, split)); f.bytes(bytes.subarray(split)); f.close(); result(f, 0, started + done);
});
test("one-byte PUBLIC chunks preserve framing", () => {
  const f = fixture(); for (const byte of Buffer.from(stream)) f.bytes(Buffer.from([byte])); f.close(); result(f, 0, started + done);
});
for (const role of roles) {
  test(`supported ${role} running closes success`, () => {
    const f = fixture(); f.record("start"); f.record(`role:${role}:running`); f.record("complete:success"); f.close();
    result(f, 0, started + `[Role ${role}: running]\n[Role ${role}: success]\n` + done);
    assert.equal(f.progress.map(x => `${x.role}:${x.status}`).join(","), `${role}:running,${role}:success`);
  });
  test(`supported ${role} failure dominates later running`, () => {
    const f = fixture(); f.record("start"); f.record(`role:${role}:failed`); f.record(`role:${role}:running`); f.record("complete:success"); f.close();
    result(f, -1, started + `[Role ${role}: failed]\n` + failed); assert.equal(f.progress.length, 1);
  });
  test(`supported ${role} running then failed retains one failure`, () => {
    const f = fixture(); f.record("start"); f.record(`role:${role}:running`); f.record(`role:${role}:failed`); f.record(`role:${role}:failed`); f.record("complete:success"); f.close();
    result(f, -1, started + `[Role ${role}: running]\n[Role ${role}: failed]\n` + failed); assert.equal(f.progress.length, 2);
  });
  test(`supported ${role} duplicate running is inert`, () => {
    const f = fixture(); f.record("start"); f.record(`role:${role}:running`); f.record(`role:${role}:running`); f.record("complete:success"); f.close();
    assert.equal(f.progress.length, 2); result(f, 0, started + `[Role ${role}: running]\n[Role ${role}: success]\n` + done);
  });
}
test("all roles keep arrival order through final projection", () => {
  const f = fixture(), reversed = [...roles].reverse(); f.record("start");
  for (const role of reversed) f.record(`role:${role}:running`);
  f.record("complete:success"); f.close();
  assert.equal(f.progress.map(x => x.role).join(","), [...reversed, ...reversed].join(","));
  result(f, 0, started + reversed.map(r => `[Role ${r}: running]\n`).join("") + reversed.map(r => `[Role ${r}: success]\n`).join("") + done);
});
for (const code of [1, 2, -2, null]) test(`supported process close ${code} fails completed protocol`, () => {
  const f = fixture(); f.record("start"); f.record("complete:success"); f.close(code); result(f, code === null ? -1 : code, started + failed);
});
for (const records of [[], ["start"], ["complete:success"], ["role:dns:running"], ["complete:failed"]]) test(`missing progress ${JSON.stringify(records)}`, () => {
  const f = fixture(); for (const record of records) f.record(record); f.close();
  result(f, -1, (records[0] === "start" ? started : records.length ? withheld : "") + unavailable + failed);
});
test("failed completion projects running roles to failed", () => {
  const f = fixture(); f.record("start"); f.record("role:dns:running"); f.record("complete:failed"); f.close();
  result(f, -1, started + "[Role dns: running]\n[Role dns: failed]\n" + failed);
});
test("first completion is immutable and later nonempty records warn once", () => {
  const f = fixture(); f.record("start"); f.record("complete:failed"); f.record("complete:success"); f.record("role:dns:running"); f.close(); result(f, -1, started + withheld + failed);
});
test("duplicate start warns once without erasing supported state", () => {
  const f = fixture(); f.record("start"); f.record("start"); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, started + withheld + done);
});
for (const text of ["PUBLIC_UNTRUSTED", "bortus_progress_v1 start", prefix + "start ", prefix + "role:DNS:running", prefix + "role:dns:success", prefix + "complete:SUCCESS", prefix + "role:unknown:running"]) test(`untrusted PUBLIC line ${JSON.stringify(text)}`, () => {
  const f = fixture(); f.record("start"); f.text(text + "\n"); f.record("complete:success"); f.close(); result(f, 0, started + withheld + done); assert.ok(!f.closed[0].fullOutput.includes(text));
});
for (const byte of [...Array.from({ length: 32 }, (_, i) => i).filter(x => x !== 10 && x !== 13), 127, 128, 255]) test(`invalid PUBLIC byte ${byte} discards complete line`, () => {
  const f = fixture(); f.bytes(Buffer.from([byte])); f.record("start"); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, withheld + started + done);
});
for (const length of [159, 160, 161, 500]) test(`PUBLIC line length ${length} withheld and next line recovers`, () => {
  const f = fixture(); f.text("X".repeat(length) + "\n"); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, withheld + started + done);
});
test("empty lines and empty stderr chunks are silent", () => {
  const f = fixture(); f.text("\n\r\n"); f.proc.stderr?.emit("data", Buffer.alloc(0)); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, started + done);
});
test("stderr and multiple discarded streams emit one fixed notice", () => {
  const f = fixture(); f.proc.stderr?.emit("data", Buffer.from("PUBLIC_STDERR")); f.text("PUBLIC_STDOUT\n"); f.record("start"); f.record("complete:success"); f.close(); result(f, 0, withheld + started + done);
});
for (const suffix of ["PUBLIC_PARTIAL", "\r", "X".repeat(161)]) test(`unfinished PUBLIC line length ${suffix.length} is never accepted on close`, () => {
  const f = fixture(); f.record("start"); f.text(suffix); f.close(); result(f, -1, started + withheld + unavailable + failed);
});
test("unterminated completion remains unavailable", () => {
  const f = fixture(); f.record("start"); f.record("complete:success", ""); f.close(); result(f, -1, started + withheld + unavailable + failed);
});
test("double trailing CR is not a supported exact record", () => {
  const f = fixture(); f.record("start", "\r\r\n"); f.record("complete:success"); f.close(); result(f, -1, withheld + unavailable + failed);
});
for (const options of [{ stdout: false }, { stderr: false }, { stdout: false, stderr: false }]) test(`optional streams ${JSON.stringify(options)}`, () => {
  const f = fixture(options); if (options.stdout !== false) { f.record("start"); f.record("complete:success"); }
  f.close(); result(f, options.stdout === false ? -1 : 0, options.stdout === false ? unavailable + failed : started + done);
});
test("synthetic already-aborted signal requests SIGTERM once", () => {
  const f = fixture({ signal: true, aborted: true }); assert.deepEqual(f.proc.kills, ["SIGTERM"]);
  f.signal?.abort(); f.close(null); result(f, -1, "[Provisioning cancelled; inspect partial effects]\n" + failed); assert.equal(f.proc.kills.length, 1);
});
test("synthetic abort overrides successful protocol without inventing exit", () => {
  const f = fixture({ signal: true }); f.record("start"); f.record("role:dns:running"); f.record("complete:success"); f.signal?.abort();
  assert.equal(f.closed.length, 0); assert.deepEqual(f.proc.kills, ["SIGTERM"]); f.close(7);
  result(f, 7, started + "[Role dns: running]\n[Provisioning cancelled; inspect partial effects]\n[Role dns: failed]\n" + failed);
});
test("process error finishes once, removes listeners, and suppresses later events", () => {
  const f = fixture({ signal: true }); f.proc.emit("error", new Error("PUBLIC_FAILURE")); f.close(); f.signal?.abort(); f.record("start");
  result(f, -1, "[Provisioning runner could not start]\n" + failed); assert.equal(f.callbacks(), 1); assert.equal(f.proc.kills.length, 0);
});
test("finish cleanup then close emission then callback order", () => {
  const f = fixture({ signal: true }); f.record("start"); f.record("complete:success"); f.close();
  assert.deepEqual(f.trace.slice(-8), ["stdout.remove:data", "stderr.remove:data", "proc.remove:close", "proc.remove:error", "signal.remove:abort", "consumer.close", "onClose"].flatMap(x => x === "consumer.close" ? ["emitter.emit:close", x] : [x]));
  result(f, 0, started + done);
});
test("data precedes role-progress and close fullOutput includes final data", () => {
  const f = fixture(); f.record("start"); const before = f.trace.length; f.record("role:dns:running");
  assert.deepEqual(f.trace.slice(before), ["stdout.emit:data", "emitter.emit:data", "consumer.data", "emitter.emit:role-progress", "consumer.role"]);
  f.record("complete:success"); f.close(); assert.equal(f.closed[0].fullOutput, f.data.join(""));
});
test("omitted onClose default is inert", () => {
  const f = fixture({ defaultClose: true }); f.close(); result(f, -1, unavailable + failed); assert.equal(f.callbacks(), 0);
});
test("independent observer instances retain no shared state", () => {
  const a = fixture(), b = fixture(); assert.notEqual(a.emitter, b.emitter); a.record("start"); a.record("complete:success"); a.close(); b.close();
  result(a, 0, started + done); result(b, -1, unavailable + failed);
});

// Immediate fault injection characterizes JavaScript propagation, not OS failures.
const publicFault = new Error("PUBLIC_IMMEDIATE_FAULT");
test("JS characterization: emitter constructor failure precedes Map", () => {
  let map = 0;
  const observe = load({ EventEmitter: class { constructor() { throw publicFault; } }, Map: class { constructor() { map++; } } });
  assert.throws(() => observe(new PublicProcess([])), x => x === publicFault); assert.equal(map, 0);
});
test("JS characterization: Map constructor failure precedes registrations", () => {
  const trace: string[] = [], observe = load({ Map: class { constructor() { throw publicFault; } } });
  assert.throws(() => observe(new PublicProcess(trace)), x => x === publicFault); assert.deepEqual(trace, []);
});
for (const at of ["stdout", "stderr", "close", "error", "abort-add", "aborted-get"]) test(`JS characterization: registration fault ${at} stops immediately`, () => {
  const trace: string[] = [], proc = new PublicProcess(trace), signal = new PublicSignal(trace);
  if (at === "stdout" || at === "stderr") Object.defineProperty(proc, at, { get() { throw publicFault; } });
  else if (at === "close" || at === "error") { const original = proc.on.bind(proc); proc.on = (name, fn) => { if (name === at) throw publicFault; return original(name, fn); }; }
  else if (at === "abort-add") signal.addEventListener = () => { throw publicFault; };
  else Object.defineProperty(signal, "aborted", { get() { throw publicFault; } });
  assert.throws(() => load()(proc, signal), x => x === publicFault);
  const expected: Record<string, string[]> = { stdout: [], stderr: ["stdout.on:data"], close: ["stdout.on:data", "stderr.on:data"], error: ["stdout.on:data", "stderr.on:data", "proc.on:close"], "abort-add": ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error"], "aborted-get": ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error", "signal.add:abort:once"] };
  assert.deepEqual(trace, expected[at]);
});
test("JS characterization: kill throws after cancellation is marked", () => {
  const f = fixture({ signal: true }); let calls = 0; f.proc.kill = () => { calls++; throw publicFault; };
  assert.throws(() => f.signal?.abort(), x => x === publicFault); f.signal?.abort(); assert.equal(calls, 1);
  f.close(); result(f, -1, "[Provisioning cancelled; inspect partial effects]\n" + failed);
});
test("JS characterization: onClose throws after public close and cleanup", () => {
  const proc = new PublicProcess([]), emitter = load()(proc, undefined, () => { throw publicFault; }); let closes = 0;
  emitter.on("close", () => { closes++; }); assert.throws(() => proc.emit("close", 0), x => x === publicFault);
  assert.equal(closes, 1); assert.equal(proc.count(), 0); proc.emit("close", 0); assert.equal(closes, 1);
});
test("JS characterization: close-listener throw precedes callback after cleanup", () => {
  const f = fixture(); f.emitter.on("close", () => { throw publicFault; });
  assert.throws(() => f.close(), x => x === publicFault); assert.equal(f.closed.length, 1); assert.equal(f.callbacks(), 0); assert.equal(f.proc.count(), 0);
});
test("JS characterization: cleanup throw prevents close/callback and ended prevents retry", () => {
  const f = fixture(); f.proc.stdout!.removeListener = () => { throw publicFault; };
  assert.throws(() => f.close(), x => x === publicFault); f.close(); assert.equal(f.closed.length, 0); assert.equal(f.callbacks(), 0);
  assert.equal(f.data.join(""), unavailable + failed);
});
test("JS characterization: malformed close code cannot satisfy strict numeric zero", () => {
  const f = fixture(); f.record("start"); f.record("complete:success"); f.close("0");
  assert.equal(f.closed[0].exitCode as unknown, "0"); assert.equal(f.closed[0].fullOutput, started + failed);
});
test("first successful completion survives later failed completion record", () => {
  const f = fixture(); f.record("start"); f.record("complete:success"); f.record("complete:failed"); f.close();
  result(f, 0, started + withheld + done);
});
test("JS characterization: Buffer conversion fault precedes protocol recognition", () => {
  const f = fixture({ observe: load({ Buffer: { from() { throw publicFault; } } }) });
  assert.throws(() => f.record("start"), x => x === publicFault); f.close(); result(f, -1, withheld + unavailable + failed);
});
for (const method of ["get", "set"]) test(`JS characterization: roles Map.${method} fault precedes role publication`, () => {
  class FaultMap extends Map<string, string> {
    get(key: string) { if (method === "get") throw publicFault; return super.get(key); }
    set(key: string, value: string) { if (method === "set") throw publicFault; return super.set(key, value); }
  }
  const f = fixture({ observe: load({ Map: FaultMap }) }); f.record("start");
  assert.throws(() => f.record("role:dns:running"), x => x === publicFault); assert.equal(f.progress.length, 0);
});
for (const condition of ["cancelled", "start-failure", "nonzero", "not-started", "not-completed", "failed-completion"]) test(`success predicate short-circuits Map.values for ${condition}`, () => {
  let calls = 0;
  class CountMap extends Map<string, string> { values(): never { calls++; throw publicFault; } }
  const f = fixture({ signal: true, observe: load({ Map: CountMap }) });
  if (condition !== "not-started") f.record("start");
  if (["cancelled", "start-failure", "nonzero"].includes(condition)) f.record("complete:success");
  if (condition === "failed-completion") f.record("complete:failed");
  if (condition === "cancelled") f.signal?.abort();
  if (condition === "start-failure") f.proc.emit("error"); else f.close(condition === "nonzero" ? 2 : 0);
  assert.equal(calls, 0); assert.equal(f.closed.length, 1); assert.notEqual(f.closed[0].exitCode, 0);
});
test("JS characterization: Map.values fault occurs only after complete success predicate", () => {
  class FaultMap extends Map<string, string> { values(): never { throw publicFault; } }
  const f = fixture({ observe: load({ Map: FaultMap }) }); f.record("start"); f.record("complete:success");
  assert.throws(() => f.close(), x => x === publicFault); f.close(); assert.equal(f.closed.length, 0); assert.equal(f.callbacks(), 0);
});
