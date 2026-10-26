import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, deployHistoryDeleteReplacement, executionFor } from '../scripts/deploy-history-delete-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/current-session-unit-plan.mjs';
import { unitTestPlan as accountPlan } from '../scripts/current-account-unit-plan.mjs';
import { unitTestPlan as jobPlan } from '../scripts/job-stream-unit-plan.mjs';
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
test('M01 eleven mappings retain704 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 11); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 704);
  assert.deepEqual(plan.replacements.at(-1), deployHistoryDeleteReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 11);
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
test('M07 all nine frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [sessionPlan, 7], [jobPlan, 8], [accountPlan, 9], [previousPlan, 10]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== deployHistoryDeleteReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs', 'current-account-unit-plan.test.mjs', 'current-session-unit-plan.test.mjs', 'deploy-history-delete-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 DELETE group contains only new66; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'deploy-history-delete-node22']), [deployHistoryDeleteReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all nine prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'deploy-history-delete-node22', 'extra']])
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
test('M13 exact original/source LF and CRLF authority and selected DELETE remain pinned statically', () => {
  assert.equal(process.version, 'v22.23.3');
  const original = read(deployHistoryDeleteReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), deployHistoryDeleteReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), '3e41a7a655744cb22fd57c5106f267c541f0c204d979377f86ab1bd94de16a4b');
  const source = read('src/app/api/deploy/history/route.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), 'f0e082a86d2fa535ca8a7913899592f6f0227bbbaacc9facc6c9c77184996c09');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), '57536eb39d49b4427a05dabcc72c0a39a78bcce4b021a5b1ab57cfe0395cbf16');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-delete.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'DELETE');
  assert.equal(declarations.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), '2804717d06d00415b14294161101665c441702614fefbaf17c8fc93ace274851');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), '68ee1555655a5b9868cee4e36918f4dbc2c75013b9c7f7c94bf9b54afb9aa75b');
  assert.deepEqual(declarations[0].modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
  // Parse/hash only: no original controls or production declaration evaluation.
});

test('M14 all66 helpers callbacks assertions and ordering retain corrected existence Proxy then exception', () => {
  const original = read(deployHistoryDeleteReplacement.original).replaceAll('\r\n', '\n');
  const current = read(deployHistoryDeleteReplacement.current).replaceAll('\r\n', '\n');
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
  const tail = original.slice(original.indexOf('class PublicResponse {'));
  const projected = current.slice(current.indexOf('class PublicResponse {')).replace(/assert.equal\(count, 66\);\n$/, '');
  assert.equal(normalize(projected), normalize(tail));
  assert.ok(tail.includes("if (key === 'then') return undefined;"));
  for (const witness of ['auth.call', 'removed.count', 'response promise rejection propagates without catch retry', 'unawaited response promise adopts exact fulfilled identity'])
    assert.ok(tail.includes(witness));
});

test('M15 focused runner dispatch preserves its normalized planner import and exact isolated batching contract', () => {
  const runner = read('scripts/run-unit-tests.mjs').replaceAll('\r\n', '\n');
  const importPattern = /^import \{ unitTestPlan, executionFor, executionBatches \} from '(\.\/[a-z]+(?:-[a-z]+)*-unit-plan\.mjs)';$/m;
  const binding = runner.match(importPattern); assert.ok(binding);
  const planner = read('scripts/' + binding[1].slice(2));
  for (const name of ['unitTestPlan', 'executionFor', 'executionBatches']) assert.ok(planner.includes(name), name);
  const canonical = runner.replace(importPattern, "import { unitTestPlan, executionFor, executionBatches } from './get-session-account-unit-plan.mjs';");
  assert.equal(canonical, "import assert from 'node:assert/strict';\nimport { spawnSync } from 'node:child_process';\nimport { fileURLToPath } from 'node:url';\nimport { unitTestPlan, executionFor, executionBatches } from './get-session-account-unit-plan.mjs';\n\nconst root = fileURLToPath(new URL('../', import.meta.url));\nconst args = process.argv.slice(2);\nconst plan = unitTestPlan(root);\nconst selected = executionFor(plan, args);\nconsole.log(JSON.stringify({ ...plan, execution: selected }));\nif (args[0] !== '--plan') {\n  const scheduling = args[0] === '--group' ? ['--test-concurrency=1'] : [];\n  let status = 0;\n  for (const batch of executionBatches(selected)) {\n    const result = spawnSync(process.execPath, [...batch.flags, '--import', 'tsx', '--test', ...scheduling, ...batch.files], { cwd: root, stdio: 'inherit' });\n    if (result.error) throw result.error;\n    assert.equal(result.signal, null, `Unit child terminated by ${result.signal}`);\n    status ||= result.status ?? 1;\n  }\n  process.exitCode = status;\n}\n");
});

test('M16 every frozen prior planner safeguard replacement loader and package config retains exact canonical bytes', () => {
  const frozen = {
    "scripts/account-store-unit-plan.mjs": "cffab0ea41dd0073907bc073b0269b84fae9ad0122ee46b47f218971661941e3",
    "scripts/ansible-selection-unit-plan.mjs": "78b27e551a3f776763395fbff7b26a055dbf811d427c6af84706acd956839b39",
    "scripts/auth-logout-unit-plan.mjs": "acb6753b126b2f427afb44f42ce6339fc0569044d1e6ebac4c78ad6d88188217",
    "scripts/auth-register-unit-plan.mjs": "dd17a0d508c2486b9d305db110e553f0037a7dcc38208dba9b63241d01e8c794",
    "scripts/auth-session-unit-plan.mjs": "c44098a39572f0fd4655e4556bb85076b058005e8755f5575709dff81d8b8c25",
    "scripts/current-account-unit-plan.mjs": "a3f4ffbf1f3398284a0ec438f755a247cdb6fdf9b4c5db9c9fc5e16c992ac29b",
    "scripts/current-session-unit-plan.mjs": "36ebf5c2e9756bfd7aff36f35afc342748ec559192a04cc6f9da467d12e4fd5c",
    "scripts/job-stream-unit-plan.mjs": "e70697ab45a452ef0b9a5d5a77d08852c3fb491e8bb46f30881d2dd50a710184",
    "scripts/unit-test-plan.mjs": "15f05baa5b9ed524b74425d1724fc2366d21eb6a90353eeb1dddaf2ed49a145b",
    "tests/account-error-node22.test.mjs": "028722cd14fb64d534d5da0a76949e07421eb0bf3e41fe891b0e045b4d795a8e",
    "tests/account-failure-node22.test.mjs": "baf655484a1d1810b3738d6262cc249c5058b16528bb465c1f27e5292ba381aa",
    "tests/account-store-constructor-node22.test.mjs": "406855837bc22f41686fa2a2e327c84e1d9e9a89d745d6c9f125aa19135cd3c0",
    "tests/account-store-unit-plan.test.mjs": "db91826541638f7830e5482651f3dd120d30ddf43ad8478e8b0b88e0224c8b73",
    "tests/ansible-selection-node22.test.mjs": "c88fd1027f9b9b281347c67bd330ae4730740ee6ba1530e19810dadac660489f",
    "tests/ansible-selection-unit-plan.test.mjs": "d6c3ff8b710a7f30db9aa21ae66ed9ff1542e8d60ec7843a4f294ff740bce21f",
    "tests/auth-logout-post-node22.test.mjs": "5560c250b261eccca5e10c183406d6a7033edd21c73bd6f45dbdefd5af3334a4",
    "tests/auth-logout-unit-plan.test.mjs": "5dd34eb70835eae6e937775ce7c6d8b426ec7e2e80d873c704697b7d82cdd438",
    "tests/auth-register-post-node22.test.mjs": "f99b0444c2a430300f99bd8727864a378ed9f7faf93ea09f640bd53c438099c0",
    "tests/auth-register-unit-plan.test.mjs": "90ea6c3ce775d39bf45fd05c474343ff20608abab35f9cddf87eec9b6bc109c5",
    "tests/auth-session-get-node22.test.mjs": "bf99fb2a72be2cebc97cb793353dee976cf7aace3d8b442b0abc4612404589c8",
    "tests/auth-session-unit-plan.test.mjs": "5614901d17bfc37f4daff8d9d654a106b6620646f1881a32c89e8ef99e1fe926",
    "tests/create-job-stream-node22.test.mjs": "d873f9956fd20f177bab16aa08ceefebdf66a83132cec96f83a1ef4e514c86a2",
    "tests/current-account-node22.test.mjs": "565d9f2950caa363009cc1ea5e709458cd4283897fc8669addf7e1e28b7b155f",
    "tests/current-account-unit-plan.test.mjs": "00692a71f4c475ccaab7269588aa2729e12425662156f1f41a09f4b16f555ba8",
    "tests/current-session-node22.test.mjs": "0c4316b29c5f5fe4e67387e7b377a116df7bfa95c29f11f4985e5cd95ba5f640",
    "tests/current-session-unit-plan.test.mjs": "1ba63a30aac86064602a453e40ef681ebe7a900c945355bcd0c76940997ea673",
    "tests/job-stream-unit-plan.test.mjs": "829585272b526c2997fedf8e96a3a336bce0d1ba03ef8cce4b299645b2b46738",
    "tests/unit-test-loader.test.ts": "131a957bff2ffd4fb7573a38648b71fab0948cd87df6430da0548d32c2f47536",
    "tests/unit-test-plan.test.mjs": "f97b128d6d0b9354a503dfd33bb89d44e71bffe649793df64477c9555564cf95",
    "package.json": "81cfc27c470a40b9b15120704b3efc0db2e640e793ad7d0f03ddc43cbf33c55e",
    "package-lock.json": "f5edc2ed62d8e18350f9fd974fb0ccdf530098fa59340370baa932b73dda5f04",
    "eslint.config.mjs": "d21103e76c3793d7ce5ce6d6ea982798f219cdd4a61806ecd00b51e7fbc75962",
    "tsconfig.json": "1a9aeca0dd2e384e0d3341044fab297e730f40ea985c45d3101ec5316e142570"
};
  for (const [name, sha] of Object.entries(frozen)) assert.equal(digest(read(name).replaceAll('\r\n', '\n')), sha, name);
});
