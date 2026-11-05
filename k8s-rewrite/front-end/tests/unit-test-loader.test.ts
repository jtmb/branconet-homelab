import test from 'node:test';
import assert from 'node:assert/strict';

// This new public input proves the runner's Node --import tsx path still
// transforms ordinary .test.ts inputs, including non-erasable TypeScript.
class PublicRunnerInput {
  constructor(readonly marker: number) {}
}
test('unit dispatch transforms a new public TypeScript parameter property on pinned Node22', () => {
  assert.equal(process.version, 'v22.23.3');
  assert.equal(new PublicRunnerInput(2233).marker, 2233);
});
