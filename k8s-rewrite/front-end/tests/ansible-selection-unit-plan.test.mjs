import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, selectionReplacement, executionFor } from '../scripts/ansible-selection-unit-plan.mjs';
import { unitTestPlan as priorPlan, executionFor as priorExecution } from '../scripts/account-store-unit-plan.mjs';
import { unitTestPlan as firstPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const plan = unitTestPlan(root);
test('M01 four mappings preserve all 235 declaration controls and every unmapped test', () => {
  assert.equal(plan.replacements.length, 4);
  assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 235);
  assert.deepEqual(plan.replacements.at(-1), selectionReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 4);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 unknown future TS and MJS tests remain selected', () => {
  const extended = planFromInputs([...names, 'future-selection.test.ts', 'future-selection.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-selection.test.${ext}`));
});
test('M03 missing replacement refuses for each of the four mappings', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
});
test('M04 missing historical authority refuses for every mapping', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('M05 any historical byte drift refuses and canonical CRLF remains equivalent', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), plan);
});
test('M06 both frozen planner contracts and all prior metadata files remain selected', () => {
  const first = firstPlan(root); const previous = priorPlan(root);
  assert.equal(first.replacements.length, 2); assert.equal(previous.replacements.length, 3);
  assert.deepEqual(plan.replacements.slice(0, 2), first.replacements);
  assert.deepEqual(plan.replacements.slice(0, 3), previous.replacements);
  assert.deepEqual(previous.selected.filter(name => name !== selectionReplacement.original), plan.selected);
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M07 narrow new group dispatches only the new selection projection', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'ansible-selection-node22']), [selectionReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []);
  assert.equal(executionFor(plan, []), plan.selected);
});
test('M08 both prior groups retain their exact frozen dispatch', () => {
  for (const name of ['account-source-node22', 'account-store-node22'])
    assert.deepEqual(executionFor(plan, ['--group', name]), priorExecution(priorPlan(root), ['--group', name]));
});
test('M09 unsupported or surplus runner arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'ansible-selection-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
