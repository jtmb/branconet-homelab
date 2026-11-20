// DISTINCT NEW PUBLIC208 controls; historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";
// Only the exact declaration runs. All process/event/signal objects are PUBLIC fakes.
const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
const sourcePath = fileURLToPath(new URL("../src/lib/ansible-progress.ts", import.meta.url));
const source = ts.createSourceFile(sourcePath, readFileSync(sourcePath, "utf8"), ts.ScriptTarget.Latest, true);
const declarations = source.statements.filter((node) => ts.isFunctionDeclaration(node) && node.name?.text === "observeAnsibleProcess"
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
class Events {
    listeners = new Map();
    trace;
    label;
    constructor(trace = [], label = "emitter") { this.trace = trace; this.label = label; }
    on(name, listener) {
        this.trace.push(`${this.label}.on:${name}`);
        this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]);
        return this;
    }
    removeListener(name, listener) {
        this.trace.push(`${this.label}.remove:${name}`);
        this.listeners.set(name, (this.listeners.get(name) ?? []).filter(x => x !== listener));
        return this;
    }
    emit(name, ...args) {
        this.trace.push(`${this.label}.emit:${name}`);
        for (const listener of [...(this.listeners.get(name) ?? [])])
            listener(...args);
        return (this.listeners.get(name)?.length ?? 0) > 0;
    }
    count() { return [...this.listeners.values()].reduce((n, x) => n + x.length, 0); }
}
class PublicProcess extends Events {
    stdout;
    stderr;
    kills = [];
    constructor(trace) {
        super(trace, "proc");
        this.stdout = new Events(trace, "stdout");
        this.stderr = new Events(trace, "stderr");
    }
    kill(signal) { this.trace.push(`proc.kill:${signal}`); this.kills.push(signal); return true; }
}
class PublicSignal {
    aborted = false;
    listeners = [];
    trace;
    constructor(trace) { this.trace = trace; }
    addEventListener(name, fn, options) {
        assert.equal(name, "abort");
        assert.equal(options.once, true);
        this.trace.push("signal.add:abort:once");
        this.listeners.push(fn);
    }
    removeEventListener(name, fn) {
        assert.equal(name, "abort");
        this.trace.push("signal.remove:abort");
        this.listeners = this.listeners.filter(x => x !== fn);
    }
    abort() { this.aborted = true; for (const fn of [...this.listeners])
        fn(); }
}
function load(bindings = {}) {
    return vm.runInNewContext(`${compiled.outputText}\nobserveAnsibleProcess;`, {
        EventEmitter: Events, Map, Buffer, ANSIBLE_ROLES: roles, PREFIX: prefix, LINE_BYTES: 160, ...bindings,
    }, { timeout: 1000 });
}
function fixture(options = {}) {
    const trace = [], proc = new PublicProcess(trace), signal = options.signal ? new PublicSignal(trace) : undefined;
    if (options.stdout === false)
        proc.stdout = null;
    if (options.stderr === false)
        proc.stderr = null;
    if (signal)
        signal.aborted = options.aborted ?? false;
    let callbackCount = 0;
    const emitter = (options.observe ?? load())(proc, signal, options.defaultClose ? undefined : () => { trace.push("onClose"); callbackCount++; });
    emitter.trace = trace;
    const data = [], progress = [], closed = [];
    emitter.on("data", text => { trace.push("consumer.data"); data.push(text); });
    emitter.on("role-progress", value => { trace.push("consumer.role"); progress.push(value); });
    emitter.on("close", value => { trace.push("consumer.close"); closed.push(value); });
    const bytes = (value) => proc.stdout?.emit("data", value);
    const text = (value) => bytes(Buffer.from(value, "utf8"));
    const record = (value, ending = "\n") => text(prefix + value + ending);
    const close = (code = 0) => proc.emit("close", code);
    return { trace, proc, signal, emitter, data, progress, closed, bytes, text, record, close, callbacks: () => callbackCount };
}
function result(f, code, expected) {
    assert.equal(f.closed.length, 1);
    assert.equal(f.closed[0].exitCode, code);
    assert.equal(f.closed[0].fullOutput, expected);
    assert.equal(f.data.join(""), expected);
    assert.equal(f.proc.count(), 0);
    assert.equal(f.proc.stdout?.count() ?? 0, 0);
    assert.equal(f.proc.stderr?.count() ?? 0, 0);
    assert.equal(f.signal?.listeners.length ?? 0, 0);
}
const started = "[Provisioning started]\n", done = "[Provisioning completed]\n", failed = "[Provisioning failed]\n";
const withheld = "[Raw runner output withheld]\n", unavailable = "[Supported progress unavailable; inspect the operator runner]\n";
control("source-derived registration order and optional abort listener", () => {
    const f = fixture({ signal: true });
    assert.deepEqual(f.trace.slice(0, 5), ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error", "signal.add:abort:once"]);
    f.close();
    result(f, -1, unavailable + failed);
});
control("complete exact protocol succeeds without roles", () => {
    const f = fixture();
    f.record("start");
    f.record("complete:success");
    f.close();
    result(f, 0, started + done);
    assert.equal(f.callbacks(), 1);
});
control("LF and CRLF framing have equal supported meaning", () => {
    const f = fixture();
    f.record("start", "\r\n");
    f.record("role:dns:running", "\r\n");
    f.record("complete:success", "\r\n");
    f.close();
    result(f, 0, started + "[Role dns: running]\n[Role dns: success]\n" + done);
});
const stream = prefix + "start\n" + prefix + "complete:success\n";
for (let split = 0; split <= Buffer.byteLength(stream); split++)
    control(`supported byte split ${split}`, () => {
        const f = fixture(), bytes = Buffer.from(stream);
        f.bytes(bytes.subarray(0, split));
        f.bytes(bytes.subarray(split));
        f.close();
        result(f, 0, started + done);
    });
control("one-byte PUBLIC chunks preserve framing", () => {
    const f = fixture();
    for (const byte of Buffer.from(stream))
        f.bytes(Buffer.from([byte]));
    f.close();
    result(f, 0, started + done);
});
for (const role of roles) {
    control(`supported ${role} running closes success`, () => {
        const f = fixture();
        f.record("start");
        f.record(`role:${role}:running`);
        f.record("complete:success");
        f.close();
        result(f, 0, started + `[Role ${role}: running]\n[Role ${role}: success]\n` + done);
        assert.equal(f.progress.map(x => `${x.role}:${x.status}`).join(","), `${role}:running,${role}:success`);
    });
    control(`supported ${role} failure dominates later running`, () => {
        const f = fixture();
        f.record("start");
        f.record(`role:${role}:failed`);
        f.record(`role:${role}:running`);
        f.record("complete:success");
        f.close();
        result(f, -1, started + `[Role ${role}: failed]\n` + failed);
        assert.equal(f.progress.length, 1);
    });
    control(`supported ${role} running then failed retains one failure`, () => {
        const f = fixture();
        f.record("start");
        f.record(`role:${role}:running`);
        f.record(`role:${role}:failed`);
        f.record(`role:${role}:failed`);
        f.record("complete:success");
        f.close();
        result(f, -1, started + `[Role ${role}: running]\n[Role ${role}: failed]\n` + failed);
        assert.equal(f.progress.length, 2);
    });
    control(`supported ${role} duplicate running is inert`, () => {
        const f = fixture();
        f.record("start");
        f.record(`role:${role}:running`);
        f.record(`role:${role}:running`);
        f.record("complete:success");
        f.close();
        assert.equal(f.progress.length, 2);
        result(f, 0, started + `[Role ${role}: running]\n[Role ${role}: success]\n` + done);
    });
}
control("all roles keep arrival order through final projection", () => {
    const f = fixture(), reversed = [...roles].reverse();
    f.record("start");
    for (const role of reversed)
        f.record(`role:${role}:running`);
    f.record("complete:success");
    f.close();
    assert.equal(f.progress.map(x => x.role).join(","), [...reversed, ...reversed].join(","));
    result(f, 0, started + reversed.map(r => `[Role ${r}: running]\n`).join("") + reversed.map(r => `[Role ${r}: success]\n`).join("") + done);
});
for (const code of [1, 2, -2, null])
    control(`supported process close ${code} fails completed protocol`, () => {
        const f = fixture();
        f.record("start");
        f.record("complete:success");
        f.close(code);
        result(f, code === null ? -1 : code, started + failed);
    });
for (const records of [[], ["start"], ["complete:success"], ["role:dns:running"], ["complete:failed"]])
    control(`missing progress ${JSON.stringify(records)}`, () => {
        const f = fixture();
        for (const record of records)
            f.record(record);
        f.close();
        result(f, -1, (records[0] === "start" ? started : records.length ? withheld : "") + unavailable + failed);
    });
control("failed completion projects running roles to failed", () => {
    const f = fixture();
    f.record("start");
    f.record("role:dns:running");
    f.record("complete:failed");
    f.close();
    result(f, -1, started + "[Role dns: running]\n[Role dns: failed]\n" + failed);
});
control("first completion is immutable and later nonempty records warn once", () => {
    const f = fixture();
    f.record("start");
    f.record("complete:failed");
    f.record("complete:success");
    f.record("role:dns:running");
    f.close();
    result(f, -1, started + withheld + failed);
});
control("duplicate start warns once without erasing supported state", () => {
    const f = fixture();
    f.record("start");
    f.record("start");
    f.record("start");
    f.record("complete:success");
    f.close();
    result(f, 0, started + withheld + done);
});
for (const text of ["PUBLIC_UNTRUSTED", "bortus_progress_v1 start", prefix + "start ", prefix + "role:DNS:running", prefix + "role:dns:success", prefix + "complete:SUCCESS", prefix + "role:unknown:running"])
    control(`untrusted PUBLIC line ${JSON.stringify(text)}`, () => {
        const f = fixture();
        f.record("start");
        f.text(text + "\n");
        f.record("complete:success");
        f.close();
        result(f, 0, started + withheld + done);
        assert.ok(!f.closed[0].fullOutput.includes(text));
    });
for (const byte of [...Array.from({ length: 32 }, (_, i) => i).filter(x => x !== 10 && x !== 13), 127, 128, 255])
    control(`invalid PUBLIC byte ${byte} discards complete line`, () => {
        const f = fixture();
        f.bytes(Buffer.from([byte]));
        f.record("start");
        f.record("start");
        f.record("complete:success");
        f.close();
        result(f, 0, withheld + started + done);
    });
for (const length of [159, 160, 161, 500])
    control(`PUBLIC line length ${length} withheld and next line recovers`, () => {
        const f = fixture();
        f.text("X".repeat(length) + "\n");
        f.record("start");
        f.record("complete:success");
        f.close();
        result(f, 0, withheld + started + done);
    });
control("empty lines and empty stderr chunks are silent", () => {
    const f = fixture();
    f.text("\n\r\n");
    f.proc.stderr?.emit("data", Buffer.alloc(0));
    f.record("start");
    f.record("complete:success");
    f.close();
    result(f, 0, started + done);
});
control("stderr and multiple discarded streams emit one fixed notice", () => {
    const f = fixture();
    f.proc.stderr?.emit("data", Buffer.from("PUBLIC_STDERR"));
    f.text("PUBLIC_STDOUT\n");
    f.record("start");
    f.record("complete:success");
    f.close();
    result(f, 0, withheld + started + done);
});
for (const suffix of ["PUBLIC_PARTIAL", "\r", "X".repeat(161)])
    control(`unfinished PUBLIC line length ${suffix.length} is never accepted on close`, () => {
        const f = fixture();
        f.record("start");
        f.text(suffix);
        f.close();
        result(f, -1, started + withheld + unavailable + failed);
    });
control("unterminated completion remains unavailable", () => {
    const f = fixture();
    f.record("start");
    f.record("complete:success", "");
    f.close();
    result(f, -1, started + withheld + unavailable + failed);
});
control("double trailing CR is not a supported exact record", () => {
    const f = fixture();
    f.record("start", "\r\r\n");
    f.record("complete:success");
    f.close();
    result(f, -1, withheld + unavailable + failed);
});
for (const options of [{ stdout: false }, { stderr: false }, { stdout: false, stderr: false }])
    control(`optional streams ${JSON.stringify(options)}`, () => {
        const f = fixture(options);
        if (options.stdout !== false) {
            f.record("start");
            f.record("complete:success");
        }
        f.close();
        result(f, options.stdout === false ? -1 : 0, options.stdout === false ? unavailable + failed : started + done);
    });
control("synthetic already-aborted signal requests SIGTERM once", () => {
    const f = fixture({ signal: true, aborted: true });
    assert.deepEqual(f.proc.kills, ["SIGTERM"]);
    f.signal?.abort();
    f.close(null);
    result(f, -1, "[Provisioning cancelled; inspect partial effects]\n" + failed);
    assert.equal(f.proc.kills.length, 1);
});
control("synthetic abort overrides successful protocol without inventing exit", () => {
    const f = fixture({ signal: true });
    f.record("start");
    f.record("role:dns:running");
    f.record("complete:success");
    f.signal?.abort();
    assert.equal(f.closed.length, 0);
    assert.deepEqual(f.proc.kills, ["SIGTERM"]);
    f.close(7);
    result(f, 7, started + "[Role dns: running]\n[Provisioning cancelled; inspect partial effects]\n[Role dns: failed]\n" + failed);
});
control("process error finishes once, removes listeners, and suppresses later events", () => {
    const f = fixture({ signal: true });
    f.proc.emit("error", new Error("PUBLIC_FAILURE"));
    f.close();
    f.signal?.abort();
    f.record("start");
    result(f, -1, "[Provisioning runner could not start]\n" + failed);
    assert.equal(f.callbacks(), 1);
    assert.equal(f.proc.kills.length, 0);
});
control("finish cleanup then close emission then callback order", () => {
    const f = fixture({ signal: true });
    f.record("start");
    f.record("complete:success");
    f.close();
    assert.deepEqual(f.trace.slice(-8), ["stdout.remove:data", "stderr.remove:data", "proc.remove:close", "proc.remove:error", "signal.remove:abort", "consumer.close", "onClose"].flatMap(x => x === "consumer.close" ? ["emitter.emit:close", x] : [x]));
    result(f, 0, started + done);
});
control("data precedes role-progress and close fullOutput includes final data", () => {
    const f = fixture();
    f.record("start");
    const before = f.trace.length;
    f.record("role:dns:running");
    assert.deepEqual(f.trace.slice(before), ["stdout.emit:data", "emitter.emit:data", "consumer.data", "emitter.emit:role-progress", "consumer.role"]);
    f.record("complete:success");
    f.close();
    assert.equal(f.closed[0].fullOutput, f.data.join(""));
});
control("omitted onClose default is inert", () => {
    const f = fixture({ defaultClose: true });
    f.close();
    result(f, -1, unavailable + failed);
    assert.equal(f.callbacks(), 0);
});
control("independent observer instances retain no shared state", () => {
    const a = fixture(), b = fixture();
    assert.notEqual(a.emitter, b.emitter);
    a.record("start");
    a.record("complete:success");
    a.close();
    b.close();
    result(a, 0, started + done);
    result(b, -1, unavailable + failed);
});
// Immediate fault injection characterizes JavaScript propagation, not OS failures.
const publicFault = new Error("PUBLIC_IMMEDIATE_FAULT");
control("JS characterization: emitter constructor failure precedes Map", () => {
    let map = 0;
    const observe = load({ EventEmitter: class {
            constructor() { throw publicFault; }
        }, Map: class {
            constructor() { map++; }
        } });
    assert.throws(() => observe(new PublicProcess([])), x => x === publicFault);
    assert.equal(map, 0);
});
control("JS characterization: Map constructor failure precedes registrations", () => {
    const trace = [], observe = load({ Map: class {
            constructor() { throw publicFault; }
        } });
    assert.throws(() => observe(new PublicProcess(trace)), x => x === publicFault);
    assert.deepEqual(trace, []);
});
for (const at of ["stdout", "stderr", "close", "error", "abort-add", "aborted-get"])
    control(`JS characterization: registration fault ${at} stops immediately`, () => {
        const trace = [], proc = new PublicProcess(trace), signal = new PublicSignal(trace);
        if (at === "stdout" || at === "stderr")
            Object.defineProperty(proc, at, { get() { throw publicFault; } });
        else if (at === "close" || at === "error") {
            const original = proc.on.bind(proc);
            proc.on = (name, fn) => { if (name === at)
                throw publicFault; return original(name, fn); };
        }
        else if (at === "abort-add")
            signal.addEventListener = () => { throw publicFault; };
        else
            Object.defineProperty(signal, "aborted", { get() { throw publicFault; } });
        assert.throws(() => load()(proc, signal), x => x === publicFault);
        const expected = { stdout: [], stderr: ["stdout.on:data"], close: ["stdout.on:data", "stderr.on:data"], error: ["stdout.on:data", "stderr.on:data", "proc.on:close"], "abort-add": ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error"], "aborted-get": ["stdout.on:data", "stderr.on:data", "proc.on:close", "proc.on:error", "signal.add:abort:once"] };
        assert.deepEqual(trace, expected[at]);
    });
control("JS characterization: kill throws after cancellation is marked", () => {
    const f = fixture({ signal: true });
    let calls = 0;
    f.proc.kill = () => { calls++; throw publicFault; };
    assert.throws(() => f.signal?.abort(), x => x === publicFault);
    f.signal?.abort();
    assert.equal(calls, 1);
    f.close();
    result(f, -1, "[Provisioning cancelled; inspect partial effects]\n" + failed);
});
control("JS characterization: onClose throws after public close and cleanup", () => {
    const proc = new PublicProcess([]), emitter = load()(proc, undefined, () => { throw publicFault; });
    let closes = 0;
    emitter.on("close", () => { closes++; });
    assert.throws(() => proc.emit("close", 0), x => x === publicFault);
    assert.equal(closes, 1);
    assert.equal(proc.count(), 0);
    proc.emit("close", 0);
    assert.equal(closes, 1);
});
control("JS characterization: close-listener throw precedes callback after cleanup", () => {
    const f = fixture();
    f.emitter.on("close", () => { throw publicFault; });
    assert.throws(() => f.close(), x => x === publicFault);
    assert.equal(f.closed.length, 1);
    assert.equal(f.callbacks(), 0);
    assert.equal(f.proc.count(), 0);
});
control("JS characterization: cleanup throw prevents close/callback and ended prevents retry", () => {
    const f = fixture();
    f.proc.stdout.removeListener = () => { throw publicFault; };
    assert.throws(() => f.close(), x => x === publicFault);
    f.close();
    assert.equal(f.closed.length, 0);
    assert.equal(f.callbacks(), 0);
    assert.equal(f.data.join(""), unavailable + failed);
});
control("JS characterization: malformed close code cannot satisfy strict numeric zero", () => {
    const f = fixture();
    f.record("start");
    f.record("complete:success");
    f.close("0");
    assert.equal(f.closed[0].exitCode, "0");
    assert.equal(f.closed[0].fullOutput, started + failed);
});
control("first successful completion survives later failed completion record", () => {
    const f = fixture();
    f.record("start");
    f.record("complete:success");
    f.record("complete:failed");
    f.close();
    result(f, 0, started + withheld + done);
});
control("JS characterization: Buffer conversion fault precedes protocol recognition", () => {
    const f = fixture({ observe: load({ Buffer: { from() { throw publicFault; } } }) });
    assert.throws(() => f.record("start"), x => x === publicFault);
    f.close();
    result(f, -1, withheld + unavailable + failed);
});
for (const method of ["get", "set"])
    control(`JS characterization: roles Map.${method} fault precedes role publication`, () => {
        class FaultMap extends Map {
            get(key) { if (method === "get")
                throw publicFault; return super.get(key); }
            set(key, value) { if (method === "set")
                throw publicFault; return super.set(key, value); }
        }
        const f = fixture({ observe: load({ Map: FaultMap }) });
        f.record("start");
        assert.throws(() => f.record("role:dns:running"), x => x === publicFault);
        assert.equal(f.progress.length, 0);
    });
for (const condition of ["cancelled", "start-failure", "nonzero", "not-started", "not-completed", "failed-completion"])
    control(`success predicate short-circuits Map.values for ${condition}`, () => {
        let calls = 0;
        class CountMap extends Map {
            values() { calls++; throw publicFault; }
        }
        const f = fixture({ signal: true, observe: load({ Map: CountMap }) });
        if (condition !== "not-started")
            f.record("start");
        if (["cancelled", "start-failure", "nonzero"].includes(condition))
            f.record("complete:success");
        if (condition === "failed-completion")
            f.record("complete:failed");
        if (condition === "cancelled")
            f.signal?.abort();
        if (condition === "start-failure")
            f.proc.emit("error");
        else
            f.close(condition === "nonzero" ? 2 : 0);
        assert.equal(calls, 0);
        assert.equal(f.closed.length, 1);
        assert.notEqual(f.closed[0].exitCode, 0);
    });
control("JS characterization: Map.values fault occurs only after complete success predicate", () => {
    class FaultMap extends Map {
        values() { throw publicFault; }
    }
    const f = fixture({ observe: load({ Map: FaultMap }) });
    f.record("start");
    f.record("complete:success");
    assert.throws(() => f.close(), x => x === publicFault);
    f.close();
    assert.equal(f.closed.length, 0);
    assert.equal(f.callbacks(), 0);
});
assert.equal(count, 208);
