import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { planFromInputs as previousPlan, executionFor as previousExecution, executionBatches as previousBatches } from './get-session-from-headers-unit-plan.mjs';

export const getSessionReplacement = Object.freeze({
  original: 'tests/get-session-source.test.ts',
  sha256: '4d2cb1295ccee7691ffd796cb2fae60c212907165a77e34e701c383573f2fb13',
  current: 'tests/get-session-node22.test.mjs', controls: 74,
});

// A twenty-second layer retains all twenty-one frozen planners and separate packaging metadata.
export function planFromInputs(names, read) {
  const prior = previousPlan(names, read); const row = getSessionReplacement;
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
    scope: 'Twenty-three explicit Node22 replacements plus separate session packaging metadata; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}
export function executionFor(plan, args) {
  if (args.length === 0) return plan.selected;
  if (args.length === 2 && args[0] === '--group' && args[1] === 'get-session-node22') return [getSessionReplacement.current];
  return previousExecution(plan, args);
}

// Partition only the new VM-dependent child inside each unchanged prior batch.
export function executionBatches(selected) {
  assert.ok(selected.filter(name => name === getSessionReplacement.current).length <= 1);
  return previousBatches(selected).flatMap(batch => {
    const index = batch.files.indexOf(getSessionReplacement.current);
    if (index === -1) return [batch];
    assert.deepEqual(batch.flags, []);
    return [
      { files: batch.files.slice(0, index), flags: batch.flags },
      { files: [batch.files[index]], flags: ['--experimental-vm-modules'] },
      { files: batch.files.slice(index + 1), flags: batch.flags },
    ].filter(part => part.files.length > 0);
  });
}
