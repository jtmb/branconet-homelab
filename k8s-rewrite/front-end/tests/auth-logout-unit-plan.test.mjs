import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, logoutReplacement, executionFor } from '../scripts/auth-logout-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/ansible-selection-unit-plan.mjs';
import { unitTestPlan as constructorPlan } from '../scripts/account-store-unit-plan.mjs';
import { unitTestPlan as firstPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const plan = unitTestPlan(root);
test('M01 five explicit mappings retain all 265 declaration controls without duplicates', () => {
  assert.equal(plan.replacements.length, 5); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 265);
  assert.deepEqual(plan.replacements.at(-1), logoutReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 5);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 future TS and MJS discovery cannot silently lose unmapped inputs', () => {
  const extended = planFromInputs([...names, 'future-logout.test.ts', 'future-logout.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-logout.test.${ext}`));
});
test('M03 each missing replacement refuses', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
});
test('M04 every historical authority must remain discoverable', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('M05 all five historical hashes reject byte drift', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
});
test('M06 exact CRLF representation preserves all canonical authorities', () => {
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), plan);
});
test('M07 all three frozen planners retain contracts and their metadata stays selected', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [previousPlan, 4]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== logoutReplacement.original), plan.selected);
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M08 logout group contains only the new projection; default and plan are exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'auth-logout-node22']), [logoutReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M09 all three prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M10 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'auth-logout-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
