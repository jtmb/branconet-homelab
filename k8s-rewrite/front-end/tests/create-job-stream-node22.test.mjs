import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct supported PUBLIC selected-declaration controls. Historical92 stay frozen.
// No real module/import/initializer/stream/timer/job/event/DB/auth/native/HTTP executes.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/lib/job-stream.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
const digest = value => createHash('sha256').update(value).digest('hex');
assert.equal(digest(source), 'c57778b4c9cae363e351cefe1c3bbeeffc4714968470a3ec2aaea2b8d8a4b639');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '427d60d39324d16f74cdd446de7133b2711b3885da3925b486c6b9e5de76b633');
const ast = ts.createSourceFile('selected-job-stream.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'createJobStream');
assert.equal(declarations.length, 1);
assert.equal(declarations[0].modifiers.filter(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword).length, 1);
const selected = declarations[0].getText(ast);
assert.equal(digest(selected), '734a582a35eb8b8691cf5810af950fa3185a763120e62884596da2a3641ebe83');
assert.equal(digest(selected.replaceAll('\n', '\r\n')), 'e56cae9b565f53f8c93399cfa44b604e23490daaedf3c4509793c9b6b3b8b14e');
const emitted = ts.transpileModule(selected.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } });
assert.equal(emitted.diagnostics.length, 0);
const factory = new vm.Script('(b => { const { TextEncoder, ReadableStream, setTimeout, clearTimeout, globalThis, JOB_CHUNK_CHARS, JSON, Array, Error, Promise } = b; ' + emitted.outputText + '; return createJobStream; })').runInNewContext(Object.create(null));
let count = 0;
const control = (...args) => { count++; return test(...args); };
function row(output = 'public', status = 'running', cursor = 0, total = cursor + Array.from(output).length) {
    return { output, status, nextOffset: cursor + Array.from(output).length, total };
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
function harness(config = {}) {
    const events = [], frames = [], timers = new Map();
    let next = 1, closed = 0;
    const globalMarker = {};
    let callbacks, strategy;
    const signal = { aborted: false, listener: undefined,
        addEventListener(name, callback, options) { events.push('listen:' + name + ':' + options.once); signal.listener = callback; },
        removeEventListener(name, callback) { events.push('unlisten:' + name); assert.equal(callback, signal.listener ?? callback); if (config.removeFault)
            throw config.removeFault; signal.listener = undefined; },
    };
    function schedule(callback, ms) {
        events.push('schedule:' + ms);
        if (config.scheduleFault)
            throw config.scheduleFault;
        if (ms === 500 && config.schedulePollFault)
            throw config.schedulePollFault;
        const handle = config.zeroHandle ? 0 : next++;
        timers.set(handle, { callback, ms });
        return handle;
    }
    function cancel(handle) { events.push('cancel:' + handle); if (config.cancelFault)
        throw config.cancelFault; timers.delete(handle); }
    const controller = {
        enqueue(frame) { events.push('enqueue'); if (config.enqueueFault)
            throw config.enqueueFault; frames.push(frame); },
        close() { events.push('close'); closed++; if (config.closeFault)
            throw config.closeFault; },
    };
    class Encoder {
        constructor() { events.push('encoder'); if (config.encoderFault)
            throw config.encoderFault; }
        encode(text) { events.push('encode'); if (config.encodeFault)
            throw config.encodeFault; return { text, byteLength: config.frameBytes ?? Buffer.byteLength(text) }; }
    }
    class Stream {
        constructor(value, options) { events.push('stream'); callbacks = value; strategy = options; if (config.streamFault)
            throw config.streamFault; }
    }
    const bindings = { TextEncoder: Encoder, ReadableStream: Stream, setTimeout: function (...args) { assert.equal(this, globalMarker); events.push('default-schedule'); return schedule.apply(this, args); }, clearTimeout: function (handle) { assert.equal(this, globalMarker); events.push('default-cancel'); cancel(handle); }, globalThis: globalMarker, JOB_CHUNK_CHARS: 4096, JSON: { stringify(value) { events.push('stringify'); if (config.stringifyFault)
                throw config.stringifyFault; return JSON.stringify(value); } }, Array: { from(value) { events.push('array-from'); if (config.arrayFault)
                throw config.arrayFault; return Array.from(value); } }, Error, Promise };
    const options = { signal, cursor: config.cursor ?? 0, schedule, cancel,
        async authorize() { events.push('authorize'); assert.equal(this, options); if (config.authorizeFault)
            throw config.authorizeFault; return config.authorization ?? true; },
        async load(cursor) { events.push('load:' + cursor); assert.equal(this, options); if (config.loadFault)
            throw config.loadFault; return Object.hasOwn(config, 'slice') ? config.slice : row(); },
    };
    if (config.defaults) {
        delete options.schedule;
        delete options.cancel;
    }
    Object.assign(options, config.options);
    const make = factory(bindings);
    const result = make(options);
    return { events, frames, timers, signal, options, bindings, result, strategy, controller, callbacks,
        start() { callbacks.start(controller); }, pull() { return callbacks.pull(); }, abort() { signal.listener?.(); }, cancel() { callbacks.cancel(); },
        fire(ms) { const found = [...timers].find(([, value]) => value.ms === ms); assert.ok(found); timers.delete(found[0]); found[1].callback(); },
        bodies() { return frames.filter(f => f.text.startsWith('id: ')).map(f => JSON.parse(f.text.split('\ndata: ')[1].slice(0, -2))); },
        closeCount() { return closed; }, };
}
const witness = () => Object.freeze({ public: 'exact-witness' });
control('setup selects only the exact declaration and constructs no real source', () => {
    const h = harness();
    assert.deepEqual(h.events, ['encoder', 'stream']);
    assert.equal(h.strategy.highWaterMark, 0);
    assert.deepEqual(Object.keys(h.callbacks), ['start', 'pull', 'cancel']);
});
control('setup reads schedule, cancel, encoder, cursor before stream construction', () => {
    const order = [];
    const h = harness({ options: { get schedule() { order.push('schedule'); return undefined; }, get cancel() { order.push('cancel'); return undefined; }, get cursor() { order.push('cursor'); return 7; } } });
    // Object.assign reads the synthetic input getters; independent selected options below pin runtime reads.
    const opts = { get schedule() { order.push('selected-schedule'); return undefined; }, get cancel() { order.push('selected-cancel'); return undefined; }, get cursor() { order.push('selected-cursor'); return 7; } };
    factory(h.bindings)(opts);
    assert.deepEqual(order.slice(-3), ['selected-schedule', 'selected-cancel', 'selected-cursor']);
});
for (const name of ['schedule', 'cancel', 'cursor'])
    control(`setup ${name} getter preserves exact thrown witness`, () => {
        const h = harness(), error = witness();
        const opts = Object.defineProperty({}, name, { get() { throw error; } });
        assert.throws(() => factory(h.bindings)(opts), value => value === error);
    });
for (const name of ['TextEncoder', 'ReadableStream'])
    control(`setup ${name} constructor preserves exact witness`, () => {
        const h = harness(), error = witness();
        h.bindings[name] = class {
            constructor() { throw error; }
        };
        assert.throws(() => factory(h.bindings)(h.options), value => value === error);
    });
for (const name of ['setTimeout', 'clearTimeout'])
    control(`nullish default ${name} bind preserves exact witness`, () => {
        const h = harness(), error = witness();
        h.bindings[name] = { bind() { throw error; } };
        assert.throws(() => factory(h.bindings)({ cursor: 0 }), value => value === error);
    });
for (const value of [null, undefined])
    control(`nullish timer defaults ${String(value)} bind inert global receiver`, () => {
        const h = harness({ options: { schedule: value, cancel: value } });
        h.start();
        h.cancel();
        assert.ok(h.events.includes('default-schedule'));
        assert.ok(h.events.includes('default-cancel'));
        assert.equal(h.closeCount(), 0);
    });
control('start connection frame precedes fixed deadline scheduling', () => {
    const h = harness();
    h.start();
    assert.deepEqual(h.events, ['encoder', 'stream', 'listen:abort:true', 'encode', 'enqueue', 'schedule:1800000']);
    assert.equal(h.frames[0].text, ': connected\n\n');
});
control('already aborted start closes without listener, output or timers', () => {
    const h = harness();
    h.signal.aborted = true;
    h.start();
    assert.deepEqual(h.events, ['encoder', 'stream', 'unlisten:abort', 'close']);
    assert.equal(h.frames.length, 0);
    assert.equal(h.timers.size, 0);
});
control('abort closes once and cancels deadline once', () => {
    const h = harness();
    h.start();
    const abort = h.signal.listener;
    abort();
    abort();
    h.cancel();
    assert.equal(h.closeCount(), 1);
    assert.equal(h.events.filter(e => e.startsWith('cancel:')).length, 1);
    assert.equal(h.timers.size, 0);
});
control('consumer cancel cleans up without controller close', () => { const h = harness(); h.start(); h.cancel(); h.cancel(); assert.equal(h.closeCount(), 0); assert.equal(h.timers.size, 0); });
control('controller close failure is swallowed after cleanup', () => { const h = harness({ closeFault: witness() }); h.start(); assert.doesNotThrow(() => h.abort()); assert.equal(h.closeCount(), 1); assert.equal(h.timers.size, 0); });
for (const field of ['cancelFault', 'removeFault'])
    control(`finish ${field} exact witness is not swallowed; closure remains idempotent`, () => {
        const error = witness(), h = harness({ [field]: error });
        h.start();
        const abort = h.signal.listener;
        assert.throws(() => abort(), value => value === error);
        assert.doesNotThrow(() => abort());
        assert.equal(h.closeCount(), 0);
    });
control('zero timer handles are characterized as uncancelled by truthiness', () => { const h = harness({ zeroHandle: true }); h.start(); h.cancel(); assert.equal(h.timers.size, 1); assert.equal(h.events.filter(e => e.startsWith('cancel:')).length, 0); });
for (const field of ['encodeFault', 'enqueueFault', 'scheduleFault'])
    control(`start ${field} preserves exact witness`, () => {
        const error = witness(), h = harness({ [field]: error });
        assert.throws(() => h.start(), value => value === error);
    });
control('signal aborted getter witness is preserved by start', () => { const error = witness(), h = harness(); Object.defineProperty(h.signal, 'aborted', { get() { throw error; } }); assert.throws(() => h.start(), value => value === error); });
control('signal listener registration witness is preserved by start', () => { const error = witness(), h = harness(); h.signal.addEventListener = () => { throw error; }; assert.throws(() => h.start(), value => value === error); });
for (const cursor of [0, 7, 4096])
    control(`authorize precedes load with exact cursor ${cursor}`, async () => {
        const h = harness({ cursor, slice: row('public', 'running', cursor) });
        h.start();
        await h.pull();
        assert.ok(h.events.indexOf('authorize') < h.events.indexOf('load:' + cursor));
        assert.equal(h.bodies()[0].cursor, cursor + 6);
        assert.equal(h.closeCount(), 0);
    });
for (const authorization of [false, null, undefined, 0, ''])
    control(`falsy authorization ${String(authorization)} refuses before load`, async () => {
        const h = harness({ options: { async authorize() { return authorization; } } });
        h.start();
        await h.pull();
        assert.deepEqual(h.bodies(), [{ error: 'Session ended', cursor: 0, done: true }]);
        assert.equal(h.events.some(e => e.startsWith('load:')), false);
        assert.equal(h.closeCount(), 1);
    });
for (const slice of [null, undefined, false, 0, ''])
    control(`falsy slice ${String(slice)} closes with fixed message`, async () => {
        const h = harness({ slice });
        h.start();
        await h.pull();
        assert.deepEqual(h.bodies(), [{ error: 'Job no longer exists', cursor: 0, done: true }]);
        assert.equal(h.closeCount(), 1);
    });
for (const field of ['authorizeFault', 'loadFault', 'arrayFault'])
    control(`pull ${field} redacts thrown public witness and closes`, async () => {
        const h = harness({ [field]: witness() });
        h.start();
        await h.pull();
        assert.deepEqual(h.bodies(), [{ error: 'Job stream unavailable', cursor: 0, done: true }]);
        assert.equal(h.closeCount(), 1);
    });
control('pending authorization abort fences load and output', async () => {
    const d = deferred(), h = harness({ options: { authorize() { return d.promise; } } });
    h.start();
    const p = h.pull();
    h.abort();
    d.resolve(true);
    await p;
    assert.equal(h.frames.length, 1);
    assert.equal(h.events.some(e => e.startsWith('load:')), false);
});
control('pending load abort fences row inspection and output', async () => {
    const d = deferred(), entered = deferred(), h = harness({ options: { load() { entered.resolve(true); return d.promise; } } });
    h.start();
    const p = h.pull();
    await entered.promise;
    h.abort();
    d.resolve(new Proxy({}, { get() { throw witness(); } }));
    await p;
    assert.equal(h.frames.length, 1);
});
for (const stage of ['authorization', 'load'])
    control(`late ${stage} rejection after cancel remains silent`, async () => {
        const d = deferred(), entered = deferred(), h = harness({ options: stage === 'authorization' ? { authorize() { entered.resolve(true); return d.promise; } } : { load() { entered.resolve(true); return d.promise; } } });
        h.start();
        const p = h.pull();
        await entered.promise;
        h.cancel();
        d.reject(witness());
        await p;
        assert.equal(h.frames.length, 1);
        assert.equal(h.closeCount(), 0);
    });
for (const slice of [row('public', 'running', 0, 1), row('', 'success', 0, 0)])
    control('cursor beyond total emits reset before output validation', async () => {
        const h = harness({ cursor: 8, slice });
        h.start();
        await h.pull();
        assert.deepEqual(h.bodies(), [{ reset: true, cursor: 0, status: slice.status }]);
        assert.equal(h.events.includes('array-from'), false);
        assert.equal(h.closeCount(), 0);
    });
control('reset cursor is used by the next explicit pull', async () => {
    let count = 0;
    const calls = [];
    const h = harness({ cursor: 9, options: { async load(cursor) { calls.push(cursor); return count++ === 0 ? row('', 'running', 0, 0) : row('x'); } } });
    h.start();
    await h.pull();
    await h.pull();
    assert.deepEqual(calls, [9, 0]);
    assert.deepEqual(h.bodies().map(b => b.cursor), [0, 1]);
});
for (const [output, count] of [['x', 1], ['😀', 1], ['a😀b', 3], ['e\u0301', 2], ['\ud800', 1]])
    control(`Unicode codepoint output ${JSON.stringify(output)} advances ${count}`, async () => {
        const h = harness({ slice: row(output) });
        h.start();
        await h.pull();
        assert.equal(h.bodies()[0].cursor, count);
        assert.equal(h.bodies()[0].output, output);
    });
for (const size of [4095, 4096, 4097])
    control(`chunk bound character count ${size}`, async () => {
        const h = harness({ slice: row('x'.repeat(size)) });
        h.start();
        await h.pull();
        assert.equal(h.bodies()[0].error, size > 4096 ? 'Job stream unavailable' : undefined);
        assert.equal(h.closeCount(), size > 4096 ? 1 : 0);
    });
for (const offset of [-1, 0, 2, 1.5, NaN, Infinity])
    control(`invalid next offset ${String(offset)} fails closed`, async () => {
        const h = harness({ slice: { ...row('x'), nextOffset: offset } });
        h.start();
        await h.pull();
        assert.equal(h.bodies()[0].error, 'Job stream unavailable');
        assert.equal(h.closeCount(), 1);
    });
control('nextOffset greater than total fails closed', async () => { const h = harness({ slice: row('xx', 'running', 0, 1) }); h.start(); await h.pull(); assert.equal(h.bodies()[0].error, 'Job stream unavailable'); });
for (const status of ['running', 'pending', 'success', 'failed'])
    control(`status ${status} publishes exact done/closure at end`, async () => {
        const h = harness({ slice: row('x', status) });
        h.start();
        await h.pull();
        const done = status === 'success' || status === 'failed';
        assert.deepEqual(h.bodies(), [{ output: 'x', status, cursor: 1, total: 1, done }]);
        assert.equal(h.closeCount(), done ? 1 : 0);
    });
for (const status of ['success', 'failed'])
    control(`terminal ${status} with remaining total stays open`, async () => { const h = harness({ slice: row('x', status, 0, 2) }); h.start(); await h.pull(); assert.equal(h.bodies()[0].done, false); assert.equal(h.closeCount(), 0); });
for (const status of ['success', 'failed'])
    control(`empty terminal ${status} emits completion`, async () => { const h = harness({ slice: row('', status) }); h.start(); await h.pull(); assert.equal(h.bodies()[0].done, true); assert.equal(h.closeCount(), 1); });
control('empty running slice polls once then reauthorizes before loading again', async () => {
    let calls = 0;
    const h = harness({ options: { async load() { return calls++ === 0 ? row('') : row('x', 'success'); } } });
    h.start();
    const p = h.pull();
    for (let i = 0; i < 6; i++)
        await Promise.resolve();
    assert.equal(h.events.filter(e => e === 'schedule:500').length, 1);
    h.fire(500);
    await p;
    assert.equal(h.events.filter(e => e === 'authorize').length, 2);
    assert.equal(h.bodies()[0].done, true);
    assert.equal(h.timers.size, 0);
});
control('abort during poll resolves waiter and cancels poll before deadline', async () => {
    const h = harness({ slice: row('') });
    h.start();
    const p = h.pull();
    for (let i = 0; i < 6; i++)
        await Promise.resolve();
    h.abort();
    await p;
    assert.deepEqual(h.events.filter(e => e.startsWith('cancel:')), ['cancel:2', 'cancel:1']);
    assert.equal(h.events.filter(e => e === 'authorize').length, 1);
    assert.equal(h.timers.size, 0);
    assert.equal(h.frames.length, 1);
});
control('consumer cancel during poll resolves waiter without close', async () => { const h = harness({ slice: row('') }); h.start(); const p = h.pull(); for (let i = 0; i < 6; i++)
    await Promise.resolve(); h.cancel(); await p; assert.equal(h.closeCount(), 0); assert.equal(h.timers.size, 0); });
control('poll scheduler failure becomes unavailable and closes', async () => { const h = harness({ slice: row(''), schedulePollFault: witness() }); h.start(); await h.pull(); assert.equal(h.bodies()[0].error, 'Job stream unavailable'); });
control('deadline publishes current cursor then closes and fences later callback', async () => { const h = harness({ cursor: 2, slice: row('x', 'running', 2) }); h.start(); await h.pull(); const callback = [...h.timers.values()][0].callback; h.fire(1800000); callback(); assert.deepEqual(h.bodies()[1], { error: 'Stream time limit reached; reconnect with the last cursor', cursor: 3, done: true }); assert.equal(h.frames.length, 3); assert.equal(h.closeCount(), 1); });
control('deadline during pending authorization fences later successful reply', async () => { const d = deferred(), h = harness({ options: { authorize() { return d.promise; } } }); h.start(); const p = h.pull(); h.fire(1800000); d.resolve(true); await p; assert.equal(h.frames.length, 2); assert.equal(h.closeCount(), 1); });
for (const bytes of [32767, 32768, 32769])
    control(`encoded frame bytes ${bytes} boundary`, async () => {
        const h = harness({ frameBytes: bytes });
        h.start();
        const p = h.pull();
        if (bytes > 32768) {
            await assert.rejects(p, { message: 'Job frame exceeds bound' });
            assert.equal(h.frames.length, 1);
            assert.equal(h.closeCount(), 0);
        }
        else {
            await p;
            assert.equal(h.frames.length, 2);
        }
    });
for (const field of ['encodeFault', 'enqueueFault', 'stringifyFault'])
    control(`fallback send ${field} exact witness rejection is preserved`, async () => {
        const error = witness(), h = harness();
        h.start();
        if (field === 'encodeFault') {
            h.bindings.TextEncoder.prototype.encode = () => { throw error; };
        }
        else if (field === 'enqueueFault')
            h.controller.enqueue = () => { throw error; };
        else
            h.bindings.JSON.stringify = () => { throw error; };
        await assert.rejects(h.pull(), value => value === error);
        assert.equal(h.closeCount(), 0);
    });
control('deadline encode failure preserves exact witness before finish', () => { const error = witness(), h = harness(); h.start(); h.bindings.TextEncoder.prototype.encode = () => { throw error; }; assert.throws(() => h.fire(1800000), value => value === error); assert.equal(h.closeCount(), 0); });
control('post-close pull never authorizes or loads', async () => { const h = harness(); h.start(); h.cancel(); await h.pull(); assert.equal(h.events.includes('authorize'), false); assert.equal(h.frames.length, 1); });
control('JSON frame keeps public newlines and Unicode inside escaped data', async () => { const h = harness({ slice: row('a\n😀') }); h.start(); await h.pull(); assert.equal(h.frames[1].text, 'id: 3\ndata: {"output":"a\\n😀","status":"running","cursor":3,"total":3,"done":false}\n\n'); });
control('thenable authorization receiver and assimilation precede load', async () => { const events = []; const h = harness({ options: { authorize() { return { then(resolve) { events.push('then'); resolve(true); } }; }, async load() { events.push('load'); return row('x'); } } }); h.start(); await h.pull(); assert.deepEqual(events, ['then', 'load']); });
control('thenable load assimilation preserves selected row', async () => { const h = harness({ options: { load() { return { then(resolve) { resolve(row('x', 'success')); } }; } } }); h.start(); await h.pull(); assert.equal(h.bodies()[0].done, true); });
control('faulting slice total getter is redacted before output is touched', async () => { const h = harness({ slice: { get total() { throw witness(); }, get output() { return assert.fail('output reached'); } } }); h.start(); await h.pull(); assert.equal(h.bodies()[0].error, 'Job stream unavailable'); });
control('first invalid chunk branch does not inspect nextOffset', async () => { const h = harness({ slice: { output: 'x'.repeat(4097), total: 5000, get nextOffset() { return assert.fail('nextOffset reached'); } } }); h.start(); await h.pull(); assert.equal(h.bodies()[0].error, 'Job stream unavailable'); });
control('invalid nextOffset equality short circuits later total read', async () => { let total = 0; const h = harness({ slice: { output: 'x', nextOffset: 2, get total() { total++; return 1; }, status: 'running' } }); h.start(); await h.pull(); assert.equal(total, 1); assert.equal(h.bodies()[0].error, 'Job stream unavailable'); });
control('success short circuits second status comparison', async () => { let status = 0; const h = harness({ slice: { ...row('x', 'success'), get status() { status++; return 'success'; } } }); h.start(); await h.pull(); assert.equal(status, 2); });
control('running status reads comparison twice and publication once', async () => { let status = 0; const h = harness({ slice: { ...row('x'), get status() { status++; return 'running'; } } }); h.start(); await h.pull(); assert.equal(status, 3); });
assert.equal(count, 92);
