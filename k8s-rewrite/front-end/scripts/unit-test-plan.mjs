import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

// Historical Node 24 controls stay immutable. Each explicit replacement must
// retain its public declaration coverage and bind the historical input bytes.
export const replacements = Object.freeze([
  { original: 'tests/account-error-source.test.ts', sha256: '541890b9f39ba952cc22800248d9b889ee19d0e7cc51ebb3894c38afdf5ae3ce', current: 'tests/account-error-node22.test.mjs', controls: 45 },
  { original: 'tests/account-failure-source.test.ts', sha256: '44cdba1ae5a3f4c731e3b1b5cad2a632be3c1c1f75a89ee375267b705ec7972c', current: 'tests/account-failure-node22.test.mjs', controls: 55 },
]);

export function unitTestPlan(root) {
  return planFromInputs(readdirSync(join(root, 'tests')), name => readFileSync(join(root, name), 'utf8'));
}

export function planFromInputs(names, read) {
  const discovered = [...names]
    .filter(name => /\.test\.(?:ts|mjs)$/.test(name)).sort().map(name => `tests/${name}`);
  for (const entry of replacements) {
    assert.ok(discovered.includes(entry.original), `Missing historical input: ${entry.original}`);
    assert.ok(discovered.includes(entry.current), `Missing replacement: ${entry.current}`);
    const canonical = read(entry.original).replaceAll('\r\n', '\n');
    assert.equal(createHash('sha256').update(canonical).digest('hex'), entry.sha256, `Historical input changed: ${entry.original}`);
  }
  const mapped = new Map(replacements.map(entry => [entry.original, entry.current]));
  const selected = [...new Set(discovered.map(name => mapped.get(name) ?? name))];
  assert.equal(selected.length, discovered.length - replacements.length);
  return { discovered, replacements, selected,
    retainedUnmapped: discovered.filter(name => !mapped.has(name) && !replacements.some(entry => entry.current === name)),
    scope: 'Two explicit Node22 replacements; all other discovered tests retained. Historical 7911/7841/70 result remains; this plan is not a suite pass.' };
}
