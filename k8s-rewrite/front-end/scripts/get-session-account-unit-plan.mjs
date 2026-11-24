import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution } from './get-session-account-from-headers-unit-plan.mjs';

export const getSessionAccountReplacement = Object.freeze({
  original: 'tests/get-session-account-source.test.ts',
  sha256: '9fda23b9802cbfb77e5acde63b3901cbf69f5ec496d09f0f14d421c8f81da901',
  current: 'tests/get-session-account-node22.test.mjs', controls: 85,
});

// A twentieth layer retains all nineteen frozen planners and separate packaging metadata.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = getSessionAccountReplacement;
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
    scope: 'Twenty-one explicit Node22 replacements plus separate session packaging metadata; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'get-session-account-node22') return [getSessionAccountReplacement.current];
  return previousExecution(plan, args);
}

// Partition only the new VM-dependent input, preserving file order and all prior flags.
export function executionBatches(selected) {
  const index = selected.indexOf(getSessionAccountReplacement.current);
  if (index === -1) return [{ files: selected, flags: [] }];
  assert.equal(selected.lastIndexOf(getSessionAccountReplacement.current), index);
  return [
    { files: selected.slice(0, index), flags: [] },
    { files: [selected[index]], flags: ['--experimental-vm-modules'] },
    { files: selected.slice(index + 1), flags: [] },
  ].filter(batch => batch.files.length > 0);
}
