import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const raw = readFileSync(new URL('./unit-test-discovery-fixtures.json', import.meta.url), 'utf8').replaceAll('\r\n', '\n');
assert.equal(createHash('sha256').update(raw).digest('hex'), '12700826a17856147bf63cf907b3b0c633cd601ab60c322b1b1bb8fa51d6f1f3');
const fixtures = JSON.parse(raw);

export function assertDiscoveryContract(plan, names, planFromInputs, read, historicalKey) {
  const discovered = names.filter(name => /\.test\.(?:ts|mjs)$/.test(name)).sort().map(name => `tests/${name}`);
  assert.deepEqual(plan.discovered, discovered);
  const mapped = new Map(plan.replacements.map(row => [row.original, row.current]));
  const current = new Set(plan.replacements.map(row => row.current));
  const selected = [...new Set(discovered.map(name => mapped.get(name) ?? name))];
  assert.deepEqual(plan.selected, selected);
  assert.deepEqual(plan.retainedUnmapped, discovered.filter(name => !mapped.has(name) && !current.has(name)));
  for (const name of discovered) assert.ok(plan.selected.includes(mapped.get(name) ?? name), name);
  const isMetadata = name => name.endsWith('-unit-plan.test.mjs') || name === 'tests/unit-test-plan.test.mjs' || name === 'tests/unit-test-loader.test.ts';
  const metadata = plan.retainedUnmapped.filter(isMetadata);
  const nonmetadata = plan.retainedUnmapped.filter(name => !isMetadata(name));
  assert.deepEqual([...metadata, ...nonmetadata].sort(), [...plan.retainedUnmapped].sort());
  assert.equal(new Set([...metadata, ...nonmetadata]).size, plan.retainedUnmapped.length);
  for (const name of plan.retainedUnmapped) assert.ok(plan.selected.includes(name), name);
  const fixture = fixtures[historicalKey]; assert.ok(fixture);
  const historical = planFromInputs(fixture.names, read);
  assert.equal(historical.discovered.length, fixture.discovered);
  assert.equal(historical.selected.length, fixture.selected);
  assert.equal(historical.replacements.length, fixture.mappings);
  assert.deepEqual(historical.discovered, fixture.names.map(name => `tests/${name}`));
}
