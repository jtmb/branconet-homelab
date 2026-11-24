import { compatibleInputHash } from '../scripts/packaging-provenance.mjs';
import { assertDiscoveryContract } from '../scripts/unit-test-discovery-contract.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, deploymentPodsReplacement, executionFor } from '../scripts/deployment-pods-unit-plan.mjs';
import { unitTestPlan as historyGetPlan } from '../scripts/deploy-history-get-unit-plan.mjs';
import { unitTestPlan as startGetPlan } from '../scripts/deploy-start-get-unit-plan.mjs';
import { unitTestPlan as startPostPlan } from '../scripts/deploy-start-post-unit-plan.mjs';
import { unitTestPlan as stopPlan } from '../scripts/deploy-stop-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/deploy-stream-unit-plan.mjs';
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
test('M01 seventeen mappings retain1071 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 17); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 1071);
  assert.deepEqual(plan.replacements.at(-1), deploymentPodsReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 17);
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
test('M07 all fifteen frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [sessionPlan, 7], [jobPlan, 8], [accountPlan, 9], [currentSessionPlan, 10], [deletePlan, 11], [historyGetPlan, 12], [startGetPlan, 13], [startPostPlan, 14], [stopPlan, 15], [previousPlan, 16]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== deploymentPodsReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs', 'current-account-unit-plan.test.mjs', 'current-session-unit-plan.test.mjs', 'deploy-history-delete-unit-plan.test.mjs', 'deploy-history-get-unit-plan.test.mjs', 'deploy-start-get-unit-plan.test.mjs', 'deploy-start-post-unit-plan.test.mjs', 'deploy-stop-unit-plan.test.mjs', 'deploy-stream-unit-plan.test.mjs', 'deployment-pods-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 deploymentPods group contains only new65; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'deployment-pods-node22']), [deploymentPodsReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all fifteen prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22', 'deploy-history-delete-node22', 'deploy-history-get-node22', 'deploy-start-get-node22', 'deploy-start-post-node22', 'deploy-stop-node22', 'deploy-stream-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'deployment-pods-node22', 'extra']])
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
  const original = read(deploymentPodsReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), deploymentPodsReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), '5d6f093b3fcbde359818b17b93017c9e74ea7ce222af5cd5dba07faa0e9bf141');
  const source = read('src/lib/deployment-state.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), '4cc5bd9d3a53f0777839292504d7be172bac1324ef8c2f1ca16544536407a8a6');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), 'eb25470584dd1c24ebf032bbb75d2d825e5f59b6e77e287eb6ace8e04a7a71f6');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-pods.ts', source, ts.ScriptTarget.ES2022, true);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'deploymentPods');
  assert.equal(declarations.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), '9773c082683d1151eab6a46ff5d715c8774efcc641d16b8f743e99f150b1480a');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), '42dfa81343593eebd903c522a4ba098c96300cde78ec3a23439bea696d7c2bed');
  assert.deepEqual(declarations[0].modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword]);
  assert.deepEqual(declarations[0].parameters.map(node => node.getText(ast)), ['deployment: any', 'pods: any[]', 'replicaSets: any[]']);
});

test('M14 all65 helpers callbacks assertions order and original VM scaffold remain exact', () => {
  const original = read(deploymentPodsReplacement.original).replaceAll('\r\n', '\n');
  const current = read(deploymentPodsReplacement.current).replaceAll('\r\n', '\n');
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
  const tail = original.slice(original.indexOf('type Metadata ='));
  const projected = current.slice(current.indexOf('const select =')).replace(/assert.equal\(count, 65\);\n$/, '');
  assert.equal(normalize(projected), normalize(tail));
  assert.ok(tail.includes('vm.runInNewContext(`${executable}\\ndeploymentPods;`, bindings, { timeout: 1000 })'));
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
    "scripts/deploy-stream-unit-plan.mjs": "0697f1d6fc85780358bf728c87f0862c69f128998dcf760a762f4e6cf6953739",
    "tests/deploy-stream-node22.test.mjs": "97a0ce3e5ba330564fe0ec2ce78e21f31a420bf82fdc79b08cb64723c67be179",
    "tests/deploy-stream-unit-plan.test.mjs": "caa9bc5899baf1f2de8fea3de5493d9745acb8655e609e98fdd0400e08393284",

    "scripts/deploy-stop-unit-plan.mjs": "3c8ff5a8cb0a4280004cdb3adc0951c126e424aff6ac1e224aa8a3f6b6f3cfa3",
    "tests/deploy-stop-node22.test.mjs": "0d46811b9f5a5b8af124893fcdaa3e51dae8df2c2e32210cbbec404fd1d53047",
    "tests/deploy-stop-unit-plan.test.mjs": "37311fa7ce5e3a79228bc0695b5e56cec1eb4fa289d05aea111c6670c9a26266",

    "scripts/deploy-start-post-unit-plan.mjs": "cc3762862dcaa77fe2644646408ddcab1113641d79692cb874499939ffa9887e",
    "tests/deploy-start-post-node22.test.mjs": "e064c701190e5a456b7651499ac49fe005e740f9506df016acc43665deab2eea",
    "tests/deploy-start-post-unit-plan.test.mjs": "cdd8799dc01218fda3d7b47fd33bce4ef59f21e940ec958499bbcfa03156c3bc",

    "scripts/deploy-start-get-unit-plan.mjs": "f9e7f9427103cacb3c35f0f17f773552788bf8a56e9a26fb667070db3bfa6538",
    "tests/deploy-start-get-node22.test.mjs": "4daa75860c998bf192ed9047b273e4dbda8b02833278a1e3b32f1a35d1a45324",
    "tests/deploy-start-get-unit-plan.test.mjs": "a553f4a56a282c0039fe950cda9c0d38642d5210632715b12e7b0eb3b91db9c2",

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
    "tests/current-session-unit-plan.test.mjs": "1ba63a30aac86064602a453e40ef681ebe7a900c945355bcd0c76940997ea673",
    "tests/deploy-history-delete-node22.test.mjs": "b6d79dd1ff603e5450ccb2de667fd1ee013c5e5de98af12666a6d5ace02aecb1",
    "tests/deploy-history-delete-unit-plan.test.mjs": "12b2aa470514a2750b960f14085c609689abcd35be03fafe189fb3d843630139",
    "tests/deploy-history-get-node22.test.mjs": "687bb9986921de855908c2c828412e83d74ca63c906aae23cf4bf3abee35fb86",
    "tests/deploy-history-get-unit-plan.test.mjs": "d306325b23dff07f1b6212f73a48305e2a85b5afa612e0f9a97485b81c07f85e",
    "tests/job-stream-unit-plan.test.mjs": "829585272b526c2997fedf8e96a3a336bce0d1ba03ef8cce4b299645b2b46738",
    "tests/unit-test-loader.test.ts": "131a957bff2ffd4fb7573a38648b71fab0948cd87df6430da0548d32c2f47536",
    "tests/unit-test-plan.test.mjs": "f97b128d6d0b9354a503dfd33bb89d44e71bffe649793df64477c9555564cf95",
    "package.json": "81cfc27c470a40b9b15120704b3efc0db2e640e793ad7d0f03ddc43cbf33c55e",
    "package-lock.json": "f5edc2ed62d8e18350f9fd974fb0ccdf530098fa59340370baa932b73dda5f04",
    "eslint.config.mjs": "d21103e76c3793d7ce5ce6d6ea982798f219cdd4a61806ecd00b51e7fbc75962",
    "tsconfig.json": "1a9aeca0dd2e384e0d3341044fab297e730f40ea985c45d3101ec5316e142570"
};
  for (const [name, sha] of Object.entries(frozen)) assert.equal(digest(read(name).replaceAll('\r\n', '\n')), compatibleInputHash(import.meta.url, name, sha), name);
});

test('M17 original VM bindings parameter default and timeout are preserved', () => {
  const projection = read(deploymentPodsReplacement.current);
  const ts = createRequire(import.meta.url)('typescript');
  const ast = ts.createSourceFile('static-pods.js', projection, ts.ScriptTarget.ES2022, true);
  assert.equal(ast.parseDiagnostics.length, 0);
  const vars = ast.statements.flatMap(node => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []);
  const select = vars.find(node => node.name.getText(ast) === 'select').initializer;
  assert.ok(ts.isArrowFunction(select)); assert.equal(select.parameters.length, 1);
  assert.equal(select.parameters[0].getText(ast), 'bindings = {}');
  assert.equal(select.body.expression.getText(ast), 'vm.runInNewContext');
  assert.deepEqual(select.body.arguments.map(node => node.getText(ast)), ['`${executable}\\ndeploymentPods;`', 'bindings', '{ timeout: 1000 }']);
  assert.ok(projection.endsWith('assert.equal(count, 65);\n'));
});

test('M18 saved packaging failure is missing compiler env require with no compiler or Node assertion', () => {
  const original = read(deploymentPodsReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(original.split('\n').length - 1, 216);
  assert.equal(original.split('\n')[10], "const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!) as typeof import('typescript');");
  assert.equal(original.includes('process.version'), false);
  assert.equal(original.includes('assert.ok(compilerPath'), false);
  assert.equal(original.includes('Explicit compiler path required'), false);
  assert.ok(plan.discovered.includes(deploymentPodsReplacement.original));
  assert.equal(plan.selected.includes(deploymentPodsReplacement.original), false);
  assert.ok(plan.selected.includes(deploymentPodsReplacement.current));
});

test('M19 exact declaration order retains captured metadata early exit Set and Pod filtering', () => {
  const source = read('src/lib/deployment-state.ts').replaceAll('\r\n', '\n');
  const selected = source.slice(0, source.indexOf('\n}\n') + 2);
  const ordered = ['deployment.metadata?.namespace', 'deployment.metadata?.uid', 'if (!uid) return [];', 'new Set(', 'replicaSets.filter(', 'rs.metadata?.uid &&', 'rs.metadata?.namespace === namespace', 'rs.metadata?.ownerReferences?.some(', 'owner.kind === "Deployment"', 'owner.uid === uid', 'owner.controller === true', '.map(rs => rs.metadata.uid)', 'return pods.filter(', 'pod.metadata?.namespace === namespace', 'pod.metadata?.ownerReferences?.some(', 'owner.kind === "ReplicaSet"', 'owner.controller === true', 'owned.has(owner.uid)'];
  let position = -1;
  for (const text of ordered) { const next = selected.indexOf(text, position + 1); assert.ok(next > position, text); position = next; }
  assert.equal(selected.includes('catch'), false);
});

test('M20 bare registration renaming preserves every original member name', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const original = read(deploymentPodsReplacement.original);
  const projected = read(deploymentPodsReplacement.current);
  const members = text => {
    const ast = ts.createSourceFile('members.ts', text, ts.ScriptTarget.ES2022, true);
    const result = [];
    const visit = node => { if (ts.isPropertyAccessExpression(node)) result.push(node.name.text); ts.forEachChild(node, visit); };
    visit(ast); return result;
  };
  const tail = original.slice(original.indexOf('type Metadata ='));
  const currentTail = projected.slice(projected.indexOf('const select =')).replace(/assert.equal\(count, 65\);\n$/, '');
  assert.deepEqual(members(currentTail), members(tail));
  assert.equal(projected.includes('process.env.BORTUS_SOURCE_TYPESCRIPT'), false);
  assert.equal(projected.includes("from '@/"), false);
});

test('M21 only selected function is transpiled with inert module initializers and neighbours', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const projection = read(deploymentPodsReplacement.current);
  const ast = ts.createSourceFile('selection.js', projection, ts.ScriptTarget.ES2022, true);
  const vars = ast.statements.flatMap(node => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []);
  const compiled = vars.find(node => node.name.getText(ast) === 'compiled').initializer;
  assert.equal(compiled.expression.getText(ast), 'ts.transpileModule');
  assert.equal(compiled.arguments[0].getText(ast), 'selected');
  assert.equal(vars.find(node => node.name.getText(ast) === 'selected').initializer.getText(ast), "declaration.replace(/^export\\s+/, '')");
  const source = read('src/lib/deployment-state.ts');
  const originalAst = ts.createSourceFile('original.ts', source, ts.ScriptTarget.ES2022, true);
  const declaration = originalAst.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'deploymentPods').getText(originalAst);
  for (const name of ['count(', 'deploymentState', 'podRestarts', 'import(', 'require(']) assert.equal(declaration.includes(name), false);
});

test('M22 current discovery retains every input with separate historical count fixture', () => {
  assertDiscoveryContract(plan, names, planFromInputs, read, "deployment-pods");
});
