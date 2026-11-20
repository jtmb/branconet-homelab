import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution } from './auth-logout-unit-plan.mjs';

export const registerReplacement = Object.freeze({
  original: 'tests/auth-register-post-source.test.ts',
  sha256: 'c9d6fc744d812617bfe1aa47bec83f1e0abfd9fbbb37d902a273571639ee2d7d',
  current: 'tests/auth-register-post-node22.test.mjs', controls: 78,
});

// A new layer preserves all four frozen planners and historical authorities.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = registerReplacement;
  assert.ok(prior.discovered.includes(row.original), `Missing historical input: ${row.original}`);
  assert.ok(prior.discovered.includes(row.current), `Missing replacement: ${row.current}`);
  const original = read(row.original).replaceAll('\r\n', '\n');
  assert.equal(createHash('sha256').update(original).digest('hex'), row.sha256, `Historical input changed: ${row.original}`);
  const replacements = [...prior.replacements, row];
  const mapped = new Map(replacements.map(entry => [entry.original, entry.current]));
  const selected = [...new Set(prior.discovered.map(name => mapped.get(name) ?? name))];
  assert.equal(selected.length, prior.discovered.length - replacements.length);
  return { discovered: prior.discovered, replacements, selected,
    retainedUnmapped: prior.discovered.filter(name => !mapped.has(name) && !replacements.some(entry => entry.current === name)),
    scope: 'Six explicit Node22 replacements; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'auth-register-node22') return [registerReplacement.current];
  return previousExecution(plan, args);
}
