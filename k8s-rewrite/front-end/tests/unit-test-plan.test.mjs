import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { planFromInputs, replacements, unitTestPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
test('discovery retains every unmapped input and accounts for exactly two explicit replacements', () => {
  const plan = unitTestPlan(root);
  assert.equal(plan.replacements.length, 2); assert.equal(plan.selected.length, plan.discovered.length - 2);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...replacements.map(row => row.current)].sort());
  assert.equal(plan.selected.length, new Set(plan.selected).size);
  assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 100);
});
test('a new unrelated test is retained automatically without an allowlist change', () => {
  const plan = planFromInputs([...names, 'future-public.test.ts', 'future-public.test.mjs'], read);
  assert.ok(plan.selected.includes('tests/future-public.test.ts')); assert.ok(plan.selected.includes('tests/future-public.test.mjs'));
});
test('missing either supported replacement refuses the entire discovery plan', () => {
  for (const row of replacements) assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
});
test('missing historical originals refuses rather than losing coverage authority', () => {
  for (const row of replacements) assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('historical byte drift refuses before any test dispatch; canonical CRLF stays equivalent', () => {
  for (const row of replacements) assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')).selected, unitTestPlan(root).selected);
});
