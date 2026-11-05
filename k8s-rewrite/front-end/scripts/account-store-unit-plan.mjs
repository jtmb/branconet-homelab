import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as firstGroupPlan, replacements as firstGroup } from './unit-test-plan.mjs';

export const constructorReplacement = Object.freeze({
  original: 'tests/account-store-constructor-source.test.ts',
  sha256: '1e7d4bbb71ff6f2a8e5aa38c021ec00997af12ee8cd49bd65d634c20084367c7',
  current: 'tests/account-store-constructor-node22.test.mjs', controls: 30,
});

// Extend the frozen first-group planner without changing its two mappings or
// its five qualified safeguards. Every other discovered test remains selected.
export function planFromInputs(names, read) {
  const prior = firstGroupPlan(names, read);
  const row = constructorReplacement;
  assert.ok(prior.discovered.includes(row.original), `Missing historical input: ${row.original}`);
  assert.ok(prior.discovered.includes(row.current), `Missing replacement: ${row.current}`);
  const original = read(row.original).replaceAll('\r\n', '\n');
  assert.equal(createHash('sha256').update(original).digest('hex'), row.sha256, `Historical input changed: ${row.original}`);
  const replacements = [...firstGroup, row];
  const mapped = new Map(replacements.map(entry => [entry.original, entry.current]));
  const selected = [...new Set(prior.discovered.map(name => mapped.get(name) ?? name))];
  assert.equal(selected.length, prior.discovered.length - replacements.length);
  return { discovered: prior.discovered, replacements, selected,
    retainedUnmapped: prior.discovered.filter(name => !mapped.has(name) && !replacements.some(entry => entry.current === name)),
    scope: 'Three explicit Node22 replacements; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}

export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}

export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 1 && args[0] === '--plan') return [];
  assert.ok(args.length === 2 && args[0] === '--group', 'Unknown unit runner arguments');
  if (args[1] === 'account-source-node22') return firstGroup.map(row => row.current);
  assert.equal(args[1], 'account-store-node22', 'Unknown unit runner group');
  return [constructorReplacement.current];
}
