import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, sessionReplacement, executionFor } from '../scripts/auth-session-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/auth-register-unit-plan.mjs';
import { unitTestPlan as logoutPlan } from '../scripts/auth-logout-unit-plan.mjs';
import { unitTestPlan as selectionPlan } from '../scripts/ansible-selection-unit-plan.mjs';
import { unitTestPlan as constructorPlan } from '../scripts/account-store-unit-plan.mjs';
import { unitTestPlan as firstPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const plan = unitTestPlan(root);
test('M01 seven mappings retain429 source controls and separate packaging metadata without duplication', () => {
  assert.equal(plan.replacements.length, 7); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 429);
  assert.deepEqual(plan.replacements.at(-1), sessionReplacement);
  assert.equal(sessionReplacement.metadataControls, 1); assert.ok(plan.selected.includes(sessionReplacement.metadata));
  assert.equal(plan.selected.length, plan.discovered.length - 7);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 future TS and MJS inputs remain selected', () => {
  const extended = planFromInputs([...names, 'future-session.test.ts', 'future-session.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-session.test.${ext}`));
});
test('M03 missing replacement or separate packaging metadata refuses', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
  assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== sessionReplacement.metadata), read), /Missing packaging metadata/);
});
test('M04 missing historical authority refuses for every mapping', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('M05 every original hash rejects byte drift including the packaging suffix', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
});
test('M06 exact CRLF representation preserves canonical authority', () => {
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), plan);
});
test('M07 all five frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [previousPlan, 6]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== sessionReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 session group contains only new86; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'auth-session-node22']), [sessionReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all five prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'auth-session-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
test('M12 NEW supported packaging inverse preserves exact historical loader and86 callbacks separately', () => {
  assert.equal(process.version, 'v22.23.3');
  const current = Buffer.from(read(sessionReplacement.original).replaceAll('\r\n', '\n'));
  const digest = value => createHash('sha256').update(value).digest('hex');
  assert.equal(digest(current), '5059b57ea27bc9f8c365af970792fbcbc9a343cc0441847853e9d41fd5efb7a7');
  const marker = Buffer.from('// NEW packaging inverse metadata control; original86 remain frozen.\n');
  const start = current.indexOf(marker);
  assert.ok(start > 0); assert.equal(current.indexOf(marker, start + marker.length), -1);
  const restored = Buffer.concat([current.subarray(0, start), Buffer.from('\n')]);
  assert.equal(digest(restored), '47598230a7b7fc6ce3a71ee7f660b14d77947e95fb121141418bff9a236f24f2');
  assert.ok(current.subarray(-2).equals(Buffer.from('}\x29;\n').subarray(-2)));
  assert.ok(!current.subarray(-2).equals(Buffer.from('\n\n')));
  // Neither frozen original loader nor callbacks are imported or evaluated.
});
