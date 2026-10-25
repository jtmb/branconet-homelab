import test from 'node:test';
import assert from 'node:assert/strict';
import { declaration } from './support/node22-source-harness.mjs';

const compile = declaration('accounts.ts', '5a858a0c7072ab0583dea19be4b9f01c49b87f7b77a3e125716d56ad8b0a8e21', 'accountFailure',
  'export function accountFailure(error: unknown) {\n  return error instanceof AccountError\n    ? NextResponse.json({ error: error.message }, { status: error.status })\n    : NextResponse.json({ error: "Account operation unavailable" }, { status: 503 });\n}');
function scenario(match, ...outputs) {
  const output = outputs.length ? outputs[0] : Symbol('PUBLIC N22 output');
  const events = []; const state = { message: 'PUBLIC N22 error', status: 422 };
  const fault = label => { events.push(label); if (state.fail === label) throw state.marker; };
  const error = Object.defineProperties({}, {
    message: { get() { fault('message'); state.onMessage?.(); return state.message; } },
    status: { get() { fault('status'); return state.status; } },
  });
  const calls = [];
  const json = function(body, options) { fault('json.call'); calls.push({ receiver: this, body, options }); return output; };
  const response = Object.defineProperty({}, 'json', { configurable: true, get() { fault('json.get'); return json; } });
  const parent = Object.defineProperty({}, Symbol.hasInstance, { get() { fault('instance.get'); return function(input) { fault('instance.call'); assert.equal(this, parent); state.input = input; return match; }; } });
  const run = compile({ AccountError: parent, NextResponse: response });
  return { events, state, error, response, parent, calls, run, output };
}
const order = match => match ? ['instance.get', 'instance.call', 'json.get', 'message', 'status', 'json.call'] : ['instance.get', 'instance.call', 'json.get', 'json.call'];
function verify(f, matched, input = f.error) {
  assert.equal(f.run(input), f.output); assert.equal(f.state.input, input);
  assert.deepEqual(f.events, order(matched)); assert.equal(f.calls.length, 1);
  const call = f.calls[0]; assert.equal(call.receiver, f.response);
  assert.deepEqual(Object.keys(call.body), ['error']); assert.deepEqual(Object.keys(call.options), ['status']);
  assert.equal(call.body.error, matched ? f.state.message : 'Account operation unavailable'); assert.equal(call.options.status, matched ? f.state.status : 503);
}
let id = 0;
const row = (label, callback) => test(`N22-F${String(++id).padStart(2, '0')}: ${label}`, callback);
row('matching member evaluation and receivers', () => verify(scenario(true), true));
row('nonmatching fixed refusal and no property reads', () => verify(scenario(false), false));
for (const [label, match, truth] of [['undefined', undefined, false], ['null', null, false], ['false', false, false], ['zero', 0, false], ['empty', '', false], ['NaN', NaN, false], ['true', true, true], ['one', 1, true], ['text', 'PUBLIC22', true], ['object', {}, true], ['array', [], true]]) row(`instance truthiness ${label}`, () => verify(scenario(match), truth));
for (const [label, input] of [['undefined', undefined], ['null', null], ['false', false], ['true', true], ['zero', 0], ['number', 22], ['NaN', NaN], ['empty', ''], ['text', 'PUBLIC22'], ['bigint', 22n], ['symbol', Symbol('input22')]]) row(`unknown input ${label}`, () => {
  // Explicit input avoids a default-argument substitution for undefined.
  const f = scenario(false); assert.equal(f.run(input), f.output); assert.equal(f.state.input, input); assert.deepEqual(f.events, order(false));
  assert.equal(f.calls[0].receiver, f.response); assert.equal(f.calls[0].body.error, 'Account operation unavailable'); assert.equal(f.calls[0].options.status, 503);
});
for (const match of [true, false]) for (const [label, output] of [['undefined', undefined], ['null', null], ['false', false], ['zero', 0], ['text', 'PUBLIC22 response'], ['symbol', Symbol('output22')], ['object', Object.freeze({ output22: true })]]) row(`synchronous result ${match}/${label}`, () => {
  verify(scenario(match, output), match);
});
for (const match of [true, false]) row(`unread returned then ${match}`, () => verify(scenario(match, Object.defineProperty({}, 'then', { get() { assert.fail('then read'); } })), match));
for (const key of ['message', 'status']) row(`opaque metadata ${key}`, () => { const f = scenario(true); f.state[key] = Object.freeze({ public22: key }); verify(f, true); });
for (const [stage, match, prefix] of [
  ['instance.get', true, ['instance.get']], ['instance.call', true, ['instance.get', 'instance.call']],
  ['json.get', true, ['instance.get', 'instance.call', 'json.get']], ['json.get', false, ['instance.get', 'instance.call', 'json.get']],
  ['message', true, ['instance.get', 'instance.call', 'json.get', 'message']], ['status', true, ['instance.get', 'instance.call', 'json.get', 'message', 'status']],
  ['json.call', true, order(true)], ['json.call', false, order(false)],
]) row(`exact no-retry fault ${stage}/${match}`, () => { const f = scenario(match); f.state.fail = stage; f.state.marker = Object.freeze({ stage22: stage }); assert.throws(() => f.run(f.error), error => error === f.state.marker); assert.deepEqual(f.events, prefix); assert.equal(f.calls.length, 0); });
row('captured JSON member survives message mutation', () => { const f = scenario(true); f.state.onMessage = () => Object.defineProperty(f.response, 'json', { value() { assert.fail('replacement JSON'); } }); verify(f, true); });
row('message precedes current status', () => { const f = scenario(true); f.state.onMessage = () => { f.state.status = 451; }; verify(f, true); });
row('fresh body and options for each call', () => { const f = scenario(true); f.run(f.error); f.run(f.error); assert.equal(f.calls.length, 2); const [a, b] = f.calls; assert.notEqual(a.body, b.body); assert.notEqual(a.options, b.options); assert.notEqual(a.body, a.options); assert.notEqual(b.body, b.options); });
for (const match of [true, false]) row(`ordinary synthetic instanceof ${match}`, () => {
  class Public22Error { message = 'PUBLIC N22 typed'; status = 451; }
  const seen = []; const response = { json(body, options) { seen.push([this, body, options]); return seen; } };
  const input = match ? new Public22Error() : { message: 'PUBLIC22 lookalike', status: 422 };
  assert.equal(compile({ AccountError: Public22Error, NextResponse: response })(input), seen); assert.equal(seen.length, 1); assert.equal(seen[0][0], response);
  assert.equal(seen[0][1].error, match ? 'PUBLIC N22 typed' : 'Account operation unavailable'); assert.equal(seen[0][2].status, match ? 451 : 503);
});
assert.equal(id, 55);
