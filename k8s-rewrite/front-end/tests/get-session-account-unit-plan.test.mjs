import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, getSessionAccountReplacement, executionFor, executionBatches } from '../scripts/get-session-account-unit-plan.mjs';
import { unitTestPlan as historyGetPlan } from '../scripts/deploy-history-get-unit-plan.mjs';
import { unitTestPlan as startGetPlan } from '../scripts/deploy-start-get-unit-plan.mjs';
import { unitTestPlan as startPostPlan } from '../scripts/deploy-start-post-unit-plan.mjs';
import { unitTestPlan as stopPlan } from '../scripts/deploy-stop-unit-plan.mjs';
import { unitTestPlan as streamPlan } from '../scripts/deploy-stream-unit-plan.mjs';
import { unitTestPlan as podsPlan } from '../scripts/deployment-pods-unit-plan.mjs';
import { unitTestPlan as ensurePlan } from '../scripts/ensure-jwt-secret-unit-plan.mjs';
import { unitTestPlan as rolePlan } from '../scripts/get-current-role-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/get-session-account-from-headers-unit-plan.mjs';
import { unitTestPlan as deletePlan } from '../scripts/deploy-history-delete-unit-plan.mjs';
import { unitTestPlan as currentSessionPlan } from '../scripts/current-session-unit-plan.mjs';
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
test('M01 twenty-one mappings retain1366 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 21); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 1366);
  assert.deepEqual(plan.replacements.at(-1), getSessionAccountReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 21);
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
test('M07 all nineteen frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [sessionPlan, 7], [jobPlan, 8], [accountPlan, 9], [currentSessionPlan, 10], [deletePlan, 11], [historyGetPlan, 12], [startGetPlan, 13], [startPostPlan, 14], [stopPlan, 15], [streamPlan, 16], [podsPlan, 17], [ensurePlan, 18], [rolePlan, 19], [previousPlan, 20]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== getSessionAccountReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs', 'current-account-unit-plan.test.mjs', 'current-session-unit-plan.test.mjs', 'deploy-history-delete-unit-plan.test.mjs', 'deploy-history-get-unit-plan.test.mjs', 'deploy-start-get-unit-plan.test.mjs', 'deploy-start-post-unit-plan.test.mjs', 'deploy-stop-unit-plan.test.mjs', 'deploy-stream-unit-plan.test.mjs', 'deployment-pods-unit-plan.test.mjs', 'ensure-jwt-secret-unit-plan.test.mjs', 'get-current-role-unit-plan.test.mjs', 'get-session-account-from-headers-unit-plan.test.mjs', 'get-session-account-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 getSessionAccount group contains only new85; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'get-session-account-node22']), [getSessionAccountReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all nineteen prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22', 'deploy-history-delete-node22', 'deploy-history-get-node22', 'deploy-start-get-node22', 'deploy-start-post-node22', 'deploy-stop-node22', 'deploy-stream-node22', 'deployment-pods-node22', 'ensure-jwt-secret-node22', 'get-current-role-node22', 'get-session-account-from-headers-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'get-session-account-node22', 'extra']])
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
test('M13 original source and selected export retain exact LF and CRLF authority', () => {
  assert.equal(process.version, 'v22.23.3');
  const original = read(getSessionAccountReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), getSessionAccountReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), '9414a6ccdd8fb0e416ea23c4a28e1b4fa375ca799b2eddf76cdada6f31ceeb5e');
  const source = read('src/lib/auth.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), 'f190c4ba27ee2069a799ed9aa5cd37e6a69ebba70bcd05f927c3ad8eeecdc7d8');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-pods.ts', source, ts.ScriptTarget.ES2022, true);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionAccount');
  assert.equal(declarations.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), 'f4aaee30541b78bba1c73a98f2c2f64b1ac3a335955088c69e9a63ebbe888675');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), 'd22f6eec338eb33daed089d05e30e3876e21b2e6e6772d5973117d41077bd258');
  assert.deepEqual(declarations[0].modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
  assert.deepEqual(declarations[0].parameters.map(node => node.getText(ast)), []);
});

test('M14 all85 helpers callbacks assertions order and original VM scaffold remain exact', () => {
  const original = read(getSessionAccountReplacement.original).replaceAll('\r\n', '\n');
  const current = read(getSessionAccountReplacement.current).replaceAll('\r\n', '\n');
  const ts = createRequire(import.meta.url)('typescript');
  const normalize = text => {
    const emitted = ts.transpileModule(text, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
    const sf = ts.createSourceFile('static-controls.js', emitted, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
    assert.equal(sf.parseDiagnostics.length, 0);
    const transformed = ts.transform(sf, [context => node => {
      const visit = n => {
        if (ts.isParenthesizedExpression(n)) return ts.visitNode(n.expression, visit);
        if (ts.isIdentifier(n) && n.text === 'control' && ts.isCallExpression(n.parent) && n.parent.expression === n) return ts.factory.createIdentifier('test');
        return ts.visitEachChild(n, visit, context);
      }; return ts.visitNode(node, visit);
    }]);
    try { return ts.createPrinter().printFile(transformed.transformed[0]); } finally { transformed.dispose(); }
  };
  const tail = original.slice(original.indexOf('type Stub ='));
  const projected = current.slice(current.indexOf('const forbiddenCalls =')).replace(/assert.equal\(count, 85\);\n$/, '');
  assert.equal(normalize(projected), normalize(tail));
  assert.ok(tail.includes('vm.runInContext'));
  assert.ok(tail.includes('test.afterEach'));
  assert.ok(tail.includes('vm.createContext'));
  assert.ok(tail.includes('new vm.SyntheticModule'));
  assert.ok(tail.includes('importModuleDynamically'));
  assert.ok(tail.includes('use strict'));
});

test('M15 focused runner dispatch preserves its normalized planner import and exact isolated batching contract', () => {
  const runner = read('scripts/run-unit-tests.mjs');
  const importPattern = /^import \{ unitTestPlan, executionFor, executionBatches \} from '(\.\/[a-z]+(?:-[a-z]+)*-unit-plan\.mjs)';$/m;
  const binding = runner.match(importPattern); assert.ok(binding);
  const planner = read('scripts/' + binding[1].slice(2));
  for (const name of ['unitTestPlan', 'executionFor', 'executionBatches']) assert.ok(planner.includes(name), name);
  const canonical = runner.replace(importPattern, "import { unitTestPlan, executionFor, executionBatches } from './get-session-account-unit-plan.mjs';");
  assert.equal(canonical, "import assert from 'node:assert/strict';\nimport { spawnSync } from 'node:child_process';\nimport { fileURLToPath } from 'node:url';\nimport { unitTestPlan, executionFor, executionBatches } from './get-session-account-unit-plan.mjs';\n\nconst root = fileURLToPath(new URL('../', import.meta.url));\nconst args = process.argv.slice(2);\nconst plan = unitTestPlan(root);\nconst selected = executionFor(plan, args);\nconsole.log(JSON.stringify({ ...plan, execution: selected }));\nif (args[0] !== '--plan') {\n  const scheduling = args[0] === '--group' ? ['--test-concurrency=1'] : [];\n  let status = 0;\n  for (const batch of executionBatches(selected)) {\n    const result = spawnSync(process.execPath, [...batch.flags, '--import', 'tsx', '--test', ...scheduling, ...batch.files], { cwd: root, stdio: 'inherit' });\n    if (result.error) throw result.error;\n    assert.equal(result.signal, null, `Unit child terminated by ${result.signal}`);\n    status ||= result.status ?? 1;\n  }\n  process.exitCode = status;\n}\n");
});

test('M16 every frozen prior planner safeguard replacement loader and package config retains exact canonical bytes', () => {
  const frozen = {
    "scripts/get-session-account-from-headers-unit-plan.mjs": "9d6d366cf3a730bb2e38d92e1dc21c6dfa363d2d33aa2dd6386dd6dbcc284edb",
    "tests/get-session-account-from-headers-node22.test.mjs": "600c2c18ba3a5f7b1ef4cd28d638ed0e49a82e63dc68ed01110a6c462640c3f9",
    "tests/get-session-account-from-headers-unit-plan.test.mjs": "3dbba102b76543fac0b5bd8cb5bae2189c44b8dea852c08ac31117cc5fb999d3",
    "scripts/get-current-role-unit-plan.mjs": "58261543fa579f529e09500bea3d951af2b1ece00de06a1532ecd68b6ac632d4",
    "tests/get-current-role-node22.test.mjs": "365d067db0ecdbe7c31bb82e84d6d4101c63f2862a04f7ea9b95a0772e654b80",
    "tests/get-current-role-unit-plan.test.mjs": "8b69be983776f371ec34bc90400ca482695557dcd42fb4d3dc2d594cb3efdf3c",
    "scripts/ensure-jwt-secret-unit-plan.mjs": "3af722ee05fd620b68ec422a064a6e898cd1ca597cffca3e942a9e89f365fd9c",
    "tests/ensure-jwt-secret-node22.test.mjs": "9043a250b21cca62778650bd932f195ab6045b8b8ac585f7b3995a5b61219cca",
    "tests/ensure-jwt-secret-unit-plan.test.mjs": "e2818516e6b16879985d7a6af62b8c526219d8d9cd10e42e748e1dbca7256f1c",
    "scripts/deployment-pods-unit-plan.mjs": "e1e5ef45f301e2fb6c43fc7edfd6a7843cb941e201d787001f1134872f19ee48",
    "tests/deployment-pods-node22.test.mjs": "0ad0a4289654ed79e7dd39f3571b3973ceeaebc4b733f1ed5a7970ebf8e9c295",
    "tests/deployment-pods-unit-plan.test.mjs": "b5b2c3a403f20e8abf5e117e4d0d2c25057d4bae40e2616058889778ace66880",

    "scripts/deploy-stream-unit-plan.mjs": "0697f1d6fc85780358bf728c87f0862c69f128998dcf760a762f4e6cf6953739",
    "tests/deploy-stream-node22.test.mjs": "97a0ce3e5ba330564fe0ec2ce78e21f31a420bf82fdc79b08cb64723c67be179",
    "tests/deploy-stream-unit-plan.test.mjs": "e5cdeec9eb7fecc7c7df1cf1a6101349bc93c05c81120d2163c01fa6f15265f0",

    "scripts/deploy-stop-unit-plan.mjs": "3c8ff5a8cb0a4280004cdb3adc0951c126e424aff6ac1e224aa8a3f6b6f3cfa3",
    "tests/deploy-stop-node22.test.mjs": "0d46811b9f5a5b8af124893fcdaa3e51dae8df2c2e32210cbbec404fd1d53047",
    "tests/deploy-stop-unit-plan.test.mjs": "3457ff56b5f0703f38cb0e95d0250b09e3d360de0e97a7fd9dd428c764182550",

    "scripts/deploy-start-post-unit-plan.mjs": "cc3762862dcaa77fe2644646408ddcab1113641d79692cb874499939ffa9887e",
    "tests/deploy-start-post-node22.test.mjs": "e064c701190e5a456b7651499ac49fe005e740f9506df016acc43665deab2eea",
    "tests/deploy-start-post-unit-plan.test.mjs": "fea6840905b0de193a83030715219144d88c78912e767f4387ba7496ab01251a",

    "scripts/deploy-start-get-unit-plan.mjs": "f9e7f9427103cacb3c35f0f17f773552788bf8a56e9a26fb667070db3bfa6538",
    "tests/deploy-start-get-node22.test.mjs": "4daa75860c998bf192ed9047b273e4dbda8b02833278a1e3b32f1a35d1a45324",
    "tests/deploy-start-get-unit-plan.test.mjs": "11d26caf79c6e6a6ce7513a7472bec6d5442df86f2614f42bb17389a35e3d0bb",

    "scripts/account-store-unit-plan.mjs": "cffab0ea41dd0073907bc073b0269b84fae9ad0122ee46b47f218971661941e3",
    "scripts/ansible-selection-unit-plan.mjs": "78b27e551a3f776763395fbff7b26a055dbf811d427c6af84706acd956839b39",
    "scripts/auth-logout-unit-plan.mjs": "acb6753b126b2f427afb44f42ce6339fc0569044d1e6ebac4c78ad6d88188217",
    "scripts/auth-register-unit-plan.mjs": "dd17a0d508c2486b9d305db110e553f0037a7dcc38208dba9b63241d01e8c794",
    "scripts/auth-session-unit-plan.mjs": "c44098a39572f0fd4655e4556bb85076b058005e8755f5575709dff81d8b8c25",
    "scripts/current-account-unit-plan.mjs": "a3f4ffbf1f3398284a0ec438f755a247cdb6fdf9b4c5db9c9fc5e16c992ac29b",
    "scripts/current-session-unit-plan.mjs": "36ebf5c2e9756bfd7aff36f35afc342748ec559192a04cc6f9da467d12e4fd5c",
    "scripts/deploy-history-delete-unit-plan.mjs": "4fed0456e60f4b7f6d649cf2fbe23740378bd2ee8cb8ee43fb6564a4b3de0080",
    "scripts/deploy-history-get-unit-plan.mjs": "5a6428ba37a931180e32424804806f491de58e4846f06225ceeb80d2c2658392",
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
    "tests/current-session-unit-plan.test.mjs": "a17d2740c877dc71acf80b75f5cfdde850cb0c887608209669316d4efdfce892",
    "tests/deploy-history-delete-node22.test.mjs": "b6d79dd1ff603e5450ccb2de667fd1ee013c5e5de98af12666a6d5ace02aecb1",
    "tests/deploy-history-delete-unit-plan.test.mjs": "963ff8cdf55991f00591b726cc2974d34c9390749bccbe623304ea7d6decae45",
    "tests/deploy-history-get-node22.test.mjs": "687bb9986921de855908c2c828412e83d74ca63c906aae23cf4bf3abee35fb86",
    "tests/deploy-history-get-unit-plan.test.mjs": "9f86a4a534bea5f390d16b946015935090c8e1d6cfcfda9e92a03b5c9ead6857",
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


test('M17 original strict context getter and synthetic namespace scaffold stays exact', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const source = text => ts.createSourceFile('scaffold.ts', text, ts.ScriptTarget.ES2022, true);
  const oldAst = source(read(getSessionAccountReplacement.original));
  const newAst = source(read(getSessionAccountReplacement.current));
  const find = ast => ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'load');
  const normalize = text => ts.createPrinter().printFile(source(text));
  const emitted = ts.transpileModule(find(oldAst).getText(oldAst), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  const load = find(newAst);
  assert.equal(normalize(load.getText(newAst)), normalize(emitted));
  assert.equal(load.body.statements[0].declarationList.declarations[0].initializer.getText(newAst), 'vm.createContext({})');
  const define = load.body.statements[1].expression;
  assert.equal(define.expression.getText(newAst), 'Object.defineProperties');
  assert.deepEqual(define.arguments[1].properties.map(node => node.name.text), ['AUTH_COOKIE', 'verifyJWT', 'currentAccount']);
  const run = load.body.statements[2].expression;
  assert.equal(run.expression.getText(newAst), 'vm.runInContext');
  assert.equal(run.arguments[0].getText(newAst), '\'"use strict"; (\' + javascript + \')\'');
  assert.equal(run.arguments[1].getText(newAst), 'context');
  const scaffold = load.getText(newAst);
  for (const text of ['importModuleDynamically', 'new vm.SyntheticModule', 'namespace.link', 'namespace.evaluate', 'return namespace']) assert.ok(scaffold.includes(text), text);
  assert.ok(read(getSessionAccountReplacement.current).endsWith('assert.equal(count, 85);\n'));
});

test('M18 saved compiler require precedes Node24 and VM assertion with no explicit compiler assertion', () => {
  const original = read(getSessionAccountReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(original.split('\n').length - 1, 154);
  assert.equal(original.split('\n')[11], 'const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);');
  assert.equal(original.split('\n')[12], 'assert.equal(process.version, "v24.18.0");');
  assert.equal(original.split('\n')[13], 'assert.ok(process.execArgv.includes("--experimental-vm-modules"));');
  assert.equal(original.includes('assert.ok(compilerPath'), false);
  assert.equal(original.includes('Explicit compiler path required'), false);
  assert.ok(plan.discovered.includes(getSessionAccountReplacement.original));
});

test('M19 exact source retains inner caught import cookie verifier and outside direct account adoption', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const source = read('src/lib/auth.ts').replaceAll('\r\n', '\n');
  const ast = ts.createSourceFile('auth.ts', source, ts.ScriptTarget.ES2022, true);
  const fn = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionAccount');
  assert.equal(fn.parameters.length, 0); assert.equal(fn.body.statements.length, 3);
  const [payload, guarded, result] = fn.body.statements;
  assert.equal(payload.getText(ast), 'let payload;'); assert.ok(ts.isTryStatement(guarded));
  assert.equal(guarded.tryBlock.statements.length, 4);
  assert.equal(guarded.tryBlock.statements[0].getText(ast), 'const { cookies } = await import("next/headers");');
  const token = guarded.tryBlock.statements[1].declarationList.declarations[0].initializer;
  assert.ok(ts.isPropertyAccessExpression(token)); assert.ok(token.questionDotToken); assert.equal(token.name.text, 'value');
  assert.equal(token.expression.getText(ast), '(await cookies()).get(AUTH_COOKIE)');
  assert.equal(guarded.tryBlock.statements[2].getText(ast), 'if (!token) return null;');
  assert.equal(guarded.tryBlock.statements[3].getText(ast), 'payload = await verifyJWT(token);');
  assert.equal(guarded.catchClause.variableDeclaration, undefined);
  assert.equal(guarded.catchClause.block.getText(ast), '{ return null; }');
  assert.equal(guarded.finallyBlock, undefined);
  assert.equal(result.expression.getText(ast), 'payload ? currentAccount(payload) : null');
});

test('M20 bare registration rename preserves every member name and afterEach hook', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const members = text => {
    const ast = ts.createSourceFile('members.ts', text, ts.ScriptTarget.ES2022, true);
    const result = [];
    const visit = node => { if (ts.isPropertyAccessExpression(node)) result.push(node.name.text); ts.forEachChild(node, visit); };
    visit(ast); return result;
  };
  const original = read(getSessionAccountReplacement.original);
  const projected = read(getSessionAccountReplacement.current);
  const tail = original.slice(original.indexOf('type Stub ='));
  const currentTail = projected.slice(projected.indexOf('const forbiddenCalls =')).replace(/assert.equal\(count, 85\);\n$/, '');
  assert.deepEqual(members(currentTail), members(tail));
  assert.equal((currentTail.match(/test\.afterEach\(/g) ?? []).length, 1);
  assert.equal(currentTail.includes('control.afterEach'), false);
  assert.equal(projected.includes('process.env.BORTUS_SOURCE_TYPESCRIPT'), false);
  assert.equal(projected.includes("from '@/"), false);
});

test('M21 exact export only uses ESNext transpilation preserving dynamic import and no neighbours', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const projection = read(getSessionAccountReplacement.current);
  const ast = ts.createSourceFile('selection.js', projection, ts.ScriptTarget.ES2022, true);
  const vars = ast.statements.flatMap(node => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []);
  const compiled = vars.find(node => node.name.getText(ast) === 'compiled').initializer;
  assert.equal(compiled.expression.getText(ast), 'ts.transpileModule');
  assert.equal(compiled.arguments[0].getText(ast), 'selected');
  assert.ok(compiled.arguments[1].getText(ast).includes('module: ts.ModuleKind.ESNext'));
  assert.equal(vars.find(node => node.name.getText(ast) === 'selected').initializer.getText(ast), "declaration.replace(/^export\\s+/, '')");
  assert.equal(vars.find(node => node.name.getText(ast) === 'javascript').initializer.getText(ast), 'compiled.outputText.trim()');
  for (const name of ['signJWT(', 'getSession(', 'getSessionAccountFromHeaders(', 'getSessionFromHeaders(', 'directAccountReader.', 'signingKey.']) assert.equal(projection.includes(name), false);
});

test('M22 current discovery selection is complete without a fixed growing total', () => {
  const discovered = names.filter(name => /\.test\.(?:ts|mjs)$/.test(name)).sort().map(name => `tests/${name}`);
  assert.deepEqual(plan.discovered, discovered);
  const mapped = new Map(plan.replacements.map(row => [row.original, row.current]));
  assert.deepEqual(plan.selected, [...new Set(discovered.map(name => mapped.get(name) ?? name))]);
  for (const name of discovered) assert.ok(plan.selected.includes(mapped.get(name) ?? name), name);
});

test('M23 forbidden dependency guard catch boundaries adoption freshness and concurrency remain exact', () => {
  const original = read(getSessionAccountReplacement.original);
  const projected = read(getSessionAccountReplacement.current);
  for (const text of ['test.afterEach(', 'assert.deepEqual(forbiddenCalls, [])', 'get result itself is not awaited', 'current-account fault propagates outside catch', 'await fence delays later work', 'current-account binding getter fault propagates', 'currentAccount is not defined', 'payload and account properties are not projected or inspected', 'successive calls freshly import read verify', 'concurrent calls retain independent']) {
    assert.ok(original.includes(text), text); assert.ok(projected.includes(text), text);
  }
});

test('M24 exact85 replacement is frozen unique and does not evaluate historical callbacks', () => {
  assert.equal(getSessionAccountReplacement.controls, 85);
  assert.equal(getSessionAccountReplacement.original, 'tests/get-session-account-source.test.ts');
  assert.equal(getSessionAccountReplacement.current, 'tests/get-session-account-node22.test.mjs');
  assert.equal(Object.isFrozen(getSessionAccountReplacement), true);
  assert.equal(plan.replacements.filter(row => row.original === getSessionAccountReplacement.original).length, 1);
  assert.equal(plan.selected.filter(name => name === getSessionAccountReplacement.current).length, 1);
  assert.equal(plan.selected.includes(getSessionAccountReplacement.original), false);
});

test('M25 VM-modules flag is scoped solely to new group with unchanged runner and previous dispatch', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'get-session-account-node22']), [getSessionAccountReplacement.current]);
  assert.equal(plan.selected.some(name => name.startsWith('--')), false);
  assert.deepEqual(executionBatches([getSessionAccountReplacement.current]), [{ files: [getSessionAccountReplacement.current], flags: ['--experimental-vm-modules'] }]);
  const source = read(getSessionAccountReplacement.current);
  assert.ok(source.includes("assert.ok(process.execArgv.includes('--experimental-vm-modules'))"));
  for (const name of ['NODE_OPTIONS', 'node:child_process', 'node:worker_threads', 'setFlagsFromString']) assert.equal(source.includes(name), false);
});
test('M26 default batches preserve exact file order while only selected VM slice receives its flag', () => {
  const batches = executionBatches(plan.selected);
  assert.deepEqual(batches.flatMap(batch => batch.files), plan.selected);
  assert.equal(batches.filter(batch => batch.flags.length).length, 1);
  assert.deepEqual(batches.find(batch => batch.flags.length), { files: [getSessionAccountReplacement.current], flags: ['--experimental-vm-modules'] });
  for (const row of plan.replacements.slice(0, -1)) assert.deepEqual(executionBatches([row.current]), [{ files: [row.current], flags: [] }]);
  assert.deepEqual(executionBatches([]), [{ files: [], flags: [] }]);
  assert.throws(() => executionBatches([getSessionAccountReplacement.current, getSessionAccountReplacement.current]));
});

test('M27 growing public TS and MJS inputs remain in ordinary batches in their discovered order', () => {
  const extended = planFromInputs([...names, 'future-CVE-public.test.ts', 'future-CVE-public.test.mjs'], read);
  const batches = executionBatches(extended.selected);
  assert.deepEqual(batches.flatMap(batch => batch.files), extended.selected);
  for (const suffix of ['ts', 'mjs']) {
    const name = `tests/future-CVE-public.test.${suffix}`;
    assert.ok(extended.selected.includes(name));
    assert.deepEqual(batches.find(batch => batch.files.includes(name)).flags, []);
  }
});

test('M28 runner applies VM flag only to its child retains all ordinary files and preserves nonzero status', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const text = read('scripts/run-unit-tests.mjs');
  const ast = ts.createSourceFile('runner.js', text, ts.ScriptTarget.ES2022, true);
  const body = ast.statements.filter(node => !ts.isImportDeclaration(node)).map(node => node.getText(ast)).join('\n');
  const files = ['tests/PUBLIC_BEFORE.test.ts', getSessionAccountReplacement.current, 'tests/PUBLIC_AFTER.test.mjs'];
  // Replace only import.meta.url syntax with an inert public URL for isolated runner evaluation.
  const evaluateBody = body.replace('import.meta.url', JSON.stringify('file:///PUBLIC/scripts/run-unit-tests.mjs'));
  assert.equal((body.match(/import\.meta\.url/g) ?? []).length, 1);
  const originalRun = vm.runInNewContext;
  // The test uses the already prepared body through a local runner, without replacing global APIs.
  const calls = [], fake = { argv: ['PUBLIC_NODE', 'PUBLIC_RUNNER'], execPath: 'PUBLIC_NODE' };
  let index = 0;
  originalRun('"use strict"; ' + evaluateBody, { assert, process: fake, URL,
    fileURLToPath: value => String(value), console: { log() {} }, unitTestPlan: () => ({ selected: files }),
    executionFor: () => files, executionBatches,
    spawnSync: (node, argv) => { calls.push({ node, argv: [...argv] }); return { signal: null, status: [3, 0, 5][index++] }; },
  });
  assert.equal(calls.length, 3); assert.equal(fake.exitCode, 3);
  assert.deepEqual(calls.map(call => call.node), ['PUBLIC_NODE', 'PUBLIC_NODE', 'PUBLIC_NODE']);
  assert.deepEqual(calls.map(call => call.argv), [
    ['--import', 'tsx', '--test', files[0]],
    ['--experimental-vm-modules', '--import', 'tsx', '--test', files[1]],
    ['--import', 'tsx', '--test', files[2]],
  ]);
});
