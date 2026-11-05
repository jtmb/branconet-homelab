import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, accountReplacement, executionFor } from '../scripts/current-account-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/job-stream-unit-plan.mjs';
import { unitTestPlan as sessionPlan, sessionReplacement } from '../scripts/auth-session-unit-plan.mjs';
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
test('M01 nine mappings retain581 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 9); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 581);
  assert.deepEqual(plan.replacements.at(-1), accountReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 9);
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...plan.replacements.map(row => row.current)].sort());
  assert.equal(new Set(plan.selected).size, plan.selected.length);
});
test('M02 future TS and MJS inputs remain selected', () => {
  const extended = planFromInputs([...names, 'future-account.test.ts', 'future-account.test.mjs'], read);
  for (const ext of ['ts', 'mjs']) assert.ok(extended.selected.includes(`tests/future-account.test.${ext}`));
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
test('M07 all seven frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [sessionPlan, 7], [previousPlan, 8]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== accountReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs', 'current-account-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 account group contains only new60; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'current-account-node22']), [accountReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all seven prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'current-account-node22', 'extra']])
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
  const original = read(accountReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), accountReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), '0a1473174bfd401034a41f2436a165675909f5315d80aa7e06010fb3a4714dab');
  const source = read('src/lib/auth.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), 'f190c4ba27ee2069a799ed9aa5cd37e6a69ebba70bcd05f927c3ad8eeecdc7d8');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-current-account.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'currentAccount');
  assert.equal(declarations.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), 'a756ea71920d52efdad8c6ef882e7740545963884eceb9256debfff2410f3ca3');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), 'e66cafee90f0d7376dd0a1816979adb79470262e97f4231e6886375a97304fef');
  // Parse/hash only: no original controls or production declaration evaluation.
});

test('M14 corrected direct-then observer and forbidden afterEach guard remain structurally exact', () => {
  const original = read(accountReplacement.original).replaceAll('\r\n', '\n');
  const current = read(accountReplacement.current).replaceAll('\r\n', '\n');
  const ts = createRequire(import.meta.url)('typescript');
  const normalize = text => {
    const emitted = ts.transpileModule(text, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
    const sf = ts.createSourceFile('static-controls.js', emitted, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
    assert.equal(sf.parseDiagnostics.length, 0);
    const transformer = context => node => {
      const visit = n => {
        if (ts.isParenthesizedExpression(n)) return ts.visitNode(n.expression, visit);
        if (ts.isIdentifier(n) && n.text === 'control') return ts.factory.createIdentifier('test');
        return ts.visitEachChild(n, visit, context);
      };
      return ts.visitNode(node, visit);
    };
    const transformed = ts.transform(sf, [transformer]);
    try { return ts.createPrinter().printFile(transformed.transformed[0]); } finally { transformed.dispose(); }
  };
  const tail = original.slice(original.indexOf('const forbiddenCalls:'));
  const projected = current.slice(current.indexOf('const forbiddenCalls =')).replace(/assert.equal\(count, 60\);\n$/, '');
  assert.equal(normalize(projected), normalize(tail));
  assert.ok(tail.includes('test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });'));
  assert.ok(tail.includes('.then(value => { result = value; });'));
});
