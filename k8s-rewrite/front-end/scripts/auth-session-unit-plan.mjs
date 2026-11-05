import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution } from './auth-register-unit-plan.mjs';

export const sessionReplacement = Object.freeze({
  original: 'tests/auth-session-get-source.test.ts',
  sha256: '5059b57ea27bc9f8c365af970792fbcbc9a343cc0441847853e9d41fd5efb7a7',
  current: 'tests/auth-session-get-node22.test.mjs', controls: 86,
  metadata: 'tests/auth-session-unit-plan.test.mjs', metadataControls: 1,
});

// The packaged original carries two authorities: GET86 and packaging inverse1.
// A sixth layer retains all five frozen planners and separately maps both.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = sessionReplacement;
  assert.ok(prior.discovered.includes(row.original), `Missing historical input: ${row.original}`);
  assert.ok(prior.discovered.includes(row.current), `Missing replacement: ${row.current}`);
  assert.ok(prior.discovered.includes(row.metadata), `Missing packaging metadata: ${row.metadata}`);
  const original = read(row.original).replaceAll('\r\n', '\n');
  assert.equal(createHash('sha256').update(original).digest('hex'), row.sha256, `Historical input changed: ${row.original}`);
  const replacements = [...prior.replacements, row];
  const mapped = new Map(replacements.map(entry => [entry.original, entry.current]));
  const selected = [...new Set(prior.discovered.map(name => mapped.get(name) ?? name))];
  assert.equal(selected.length, prior.discovered.length - replacements.length);
  return { discovered: prior.discovered, replacements, selected,
    retainedUnmapped: prior.discovered.filter(name => !mapped.has(name) && !replacements.some(entry => entry.current === name)),
    scope: 'Seven explicit Node22 replacements plus separate session packaging metadata; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'auth-session-node22') return [sessionReplacement.current];
  return previousExecution(plan, args);
}
