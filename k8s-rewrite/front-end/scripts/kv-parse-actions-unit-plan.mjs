import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution } from './kv-metadata-query-unit-plan.mjs';

export const kvParseActionsReplacement = Object.freeze({
  original: 'tests/kv-parse-actions-source.test.ts',
  sha256: '25c5d8312fecc0ac21a529bb44a772988c8a154ec3323cb0d0f4516b99e5a74a',
  current: 'tests/kv-parse-actions-node22.test.mjs', controls: 60,
});

// A fifty-seventh layer retains all fifty-six frozen planners and separate packaging metadata.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = kvParseActionsReplacement;
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
    scope: 'Fifty-eight explicit Node22 replacements plus separate session packaging metadata; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'kv-parse-actions-node22') return [kvParseActionsReplacement.current];
  return previousExecution(plan, args);
}

export { executionBatches } from './kv-metadata-query-unit-plan.mjs';
