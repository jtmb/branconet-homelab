import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { unitTestPlan } from './unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
assert.ok(args.length === 0 || (args.length === 1 && args[0] === '--plan') ||
  (args.length === 2 && args[0] === '--group' && args[1] === 'account-source-node22'), 'Unknown unit runner arguments');
const plan = unitTestPlan(root);
const selected = args[0] === '--group' ? plan.replacements.map(entry => entry.current) : plan.selected;
console.log(JSON.stringify({ ...plan, execution: args[0] === '--plan' ? [] : selected }));
if (args[0] !== '--plan') {
  const scheduling = args[0] === '--group' ? ['--test-concurrency=1'] : [];
  const result = spawnSync(process.execPath, ['--import', 'tsx', '--test', ...scheduling, ...selected], { cwd: root, stdio: 'inherit' });
  if (result.error) throw result.error;
  assert.equal(result.signal, null, `Unit child terminated by ${result.signal}`);
  process.exitCode = result.status ?? 1;
}
