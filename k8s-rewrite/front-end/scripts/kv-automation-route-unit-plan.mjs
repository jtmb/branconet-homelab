import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution } from './kv-audit-route-unit-plan.mjs';

export const kvAutomationRouteReplacement = Object.freeze({
  original: 'tests/kv-automation-route-source.test.ts',
  sha256: '8f02dae166eee6438024fb67ff5eea2a73d4f2734b0c43d0bad7c40eecfd7426',
  current: 'tests/kv-automation-route-node22.test.mjs', controls: 162,
});

// A twenty-fifth layer retains all twenty-four frozen planners and separate packaging metadata.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = kvAutomationRouteReplacement;
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
    scope: 'Twenty-six explicit Node22 replacements plus separate session packaging metadata; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'kv-automation-route-node22') return [kvAutomationRouteReplacement.current];
  return previousExecution(plan, args);
}

export { executionBatches } from './kv-audit-route-unit-plan.mjs';
