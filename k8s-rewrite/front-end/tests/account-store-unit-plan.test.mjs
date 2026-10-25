import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, constructorReplacement, executionFor } from '../scripts/account-store-unit-plan.mjs';
import { replacements as firstGroup, planFromInputs as priorPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
test('P01 expanded discovery accounts for three replacements and retains every other test', () => {
  const plan = unitTestPlan(root);
  assert.equal(plan.replacements.length, 3);
  assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 130);
  assert.equal(plan.selected.length, plan.discovered.length - 3);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('P02 both future test extensions remain selected automatically', () => {
  const plan = planFromInputs([...names, 'future-constructor.test.ts', 'future-constructor.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(plan.selected.includes(`tests/future-constructor.test.${ext}`));
});
test('P03 every missing replacement refuses discovery including the constructor', () => {
  for (const row of [...firstGroup, constructorReplacement])
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
});
test('P04 every missing historical authority refuses discovery', () => {
  for (const row of [...firstGroup, constructorReplacement])
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('P05 all historical byte drift refuses before dispatch while canonical CRLF agrees', () => {
  for (const row of [...firstGroup, constructorReplacement])
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// changed' : '')), /Historical input changed/);
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), unitTestPlan(root));
});
test('P06 the frozen planner retains its mappings and safeguards as a separate contract', () => {
  const prior = priorPlan(names, read); const expanded = unitTestPlan(root);
  assert.equal(prior.replacements.length, 2);
  assert.deepEqual(expanded.replacements.slice(0, 2), firstGroup);
  assert.deepEqual(prior.selected.filter(name => name !== constructorReplacement.original), expanded.selected);
  assert.ok(expanded.selected.includes('tests/unit-test-plan.test.mjs'));
  assert.ok(expanded.selected.includes('tests/unit-test-loader.test.ts'));
});
test('P07 metadata and narrow groups do not dispatch completed controls accidentally', () => {
  const plan = unitTestPlan(root);
  assert.deepEqual(executionFor(plan, ['--plan']), []);
  assert.deepEqual(executionFor(plan, ['--group', 'account-store-node22']), [constructorReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--group', 'account-source-node22']), firstGroup.map(row => row.current));
  assert.equal(executionFor(plan, []), plan.selected);
});
test('P08 unsupported runner requests refuse rather than selecting arbitrary inputs', () => {
  const plan = unitTestPlan(root);
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'account-store-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
