import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, streamReplacement, executionFor } from '../scripts/job-stream-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution, sessionReplacement } from '../scripts/auth-session-unit-plan.mjs';
import { unitTestPlan as registerPlan } from '../scripts/auth-register-unit-plan.mjs';
import { unitTestPlan as logoutPlan } from '../scripts/auth-logout-unit-plan.mjs';
import { unitTestPlan as selectionPlan } from '../scripts/ansible-selection-unit-plan.mjs';
import { unitTestPlan as constructorPlan } from '../scripts/account-store-unit-plan.mjs';
import { unitTestPlan as firstPlan } from '../scripts/unit-test-plan.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const names = readdirSync(new URL('./', import.meta.url));
const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const digest = value => createHash('sha256').update(value).digest('hex');
const plan = unitTestPlan(root);
test('M01 eight mappings retain521 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 8); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 521);
  assert.deepEqual(plan.replacements.at(-1), streamReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 8);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 future TS and MJS inputs remain selected', () => {
  const extended = planFromInputs([...names, 'future-stream.test.ts', 'future-stream.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-stream.test.${ext}`));
});
test('M03 missing replacement or separate packaging metadata refuses', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.current), read), /Missing replacement/);
  assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== sessionReplacement.metadata), read), /Missing packaging metadata/);
});
test('M04 missing historical authority refuses for every mapping', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names.filter(name => `tests/${name}` !== row.original), read), /Missing historical input/);
});
test('M05 every original hash rejects byte drift including separate packaging suffix', () => {
  for (const row of plan.replacements)
    assert.throws(() => planFromInputs(names, name => read(name) + (name === row.original ? '\n// drift' : '')), /Historical input changed/);
});
test('M06 exact CRLF representation preserves canonical authority', () => {
  assert.deepEqual(planFromInputs(names, name => read(name).replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')), plan);
});
test('M07 all six frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [previousPlan, 7]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== streamReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 stream group contains only new92; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'job-stream-node22']), [streamReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all six prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'job-stream-node22', 'extra']])
    assert.throws(() => executionFor(plan, args));
});
test('M12 separate session packaging authority remains selected and immutable without executing it', () => {
  assert.equal(sessionReplacement.metadataControls, 1); assert.ok(plan.selected.includes(sessionReplacement.metadata));
  const current = Buffer.from(read(sessionReplacement.original).replaceAll('\r\n', '\n'));
  assert.equal(digest(current), '5059b57ea27bc9f8c365af970792fbcbc9a343cc0441847853e9d41fd5efb7a7');
  const marker = Buffer.from('// NEW packaging inverse metadata control; original86 remain frozen.\n');
  const start = current.indexOf(marker); assert.ok(start > 0); assert.equal(current.indexOf(marker, start + marker.length), -1);
  assert.equal(digest(Buffer.concat([current.subarray(0, start), Buffer.from('\n')])), '47598230a7b7fc6ce3a71ee7f660b14d77947e95fb121141418bff9a236f24f2');
});
test('M13 both exact original/source EOL authorities and selected declaration stay pinned statically', () => {
  assert.equal(process.version, 'v22.23.3');
  const original = read(streamReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), streamReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), '6bcb3a935ccc9294e3f65c53028453e723cc8143537de42ceface20e5609169d');
  const source = read('src/lib/job-stream.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), 'c57778b4c9cae363e351cefe1c3bbeeffc4714968470a3ec2aaea2b8d8a4b639');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), '427d60d39324d16f74cdd446de7133b2711b3885da3925b486c6b9e5de76b633');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-job-stream.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'createJobStream');
  assert.equal(declarations.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), '734a582a35eb8b8691cf5810af950fa3185a763120e62884596da2a3641ebe83');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), 'e56cae9b565f53f8c93399cfa44b604e23490daaedf3c4509793c9b6b3b8b14e');
  // Parse/hash only: no original controls or production declaration evaluation.
});
