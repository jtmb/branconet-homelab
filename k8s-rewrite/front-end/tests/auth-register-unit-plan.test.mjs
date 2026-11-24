import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, registerReplacement, executionFor } from '../scripts/auth-register-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/auth-logout-unit-plan.mjs';
import { unitTestPlan as selectionPlan } from '../scripts/ansible-selection-unit-plan.mjs';
import { unitTestPlan as constructorPlan } from '../scripts/account-store-unit-plan.mjs';
import { unitTestPlan as firstPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const plan = unitTestPlan(root);
test('M01 six mappings retain all 343 declaration controls without duplication', () => {
  assert.equal(plan.replacements.length, 6); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 343);
  assert.deepEqual(plan.replacements.at(-1), registerReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 6);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 future TS and MJS inputs remain selected', () => {
  const extended = planFromInputs([...names, 'future-register.test.ts', 'future-register.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-register.test.${ext}`));
});
test('M03 missing replacement refuses for every mapping', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
});
test('M04 missing historical authority refuses for every mapping', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('M05 every original hash rejects byte drift', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
});
test('M06 exact CRLF representation preserves canonical authority', () => {
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), plan);
});
test('M07 all four frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [previousPlan, 5]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== registerReplacement.original), plan.selected);
});
test('M08 prior metadata safeguards and loader remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
  assert.ok(plan.selected.includes('tests/auth-register-unit-plan.test.mjs'));
});
test('M09 registration group contains only new78; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'auth-register-node22']), [registerReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all four prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'auth-register-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
