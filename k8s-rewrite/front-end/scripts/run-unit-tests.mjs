import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, executionFor, executionBatches } from './require-write-unit-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
const plan = unitTestPlan(root);
const selected = executionFor(plan, args);
console.log(JSON.stringify({ ...plan, execution: selected }));
if (args[0] !== '--plan') {
  const scheduling = args[0] === '--group' ? ['--test-concurrency=1'] : [];
  let status = 0;
  for (const batch of executionBatches(selected)) {
    const result = spawnSync(process.execPath, [...batch.flags, '--import', 'tsx', '--test', ...scheduling, ...batch.files], { cwd: root, stdio: 'inherit' });
    if (result.error) throw result.error;
    assert.equal(result.signal, null, `Unit child terminated by ${result.signal}`);
    status ||= result.status ?? 1;
  }
  process.exitCode = status;
}
