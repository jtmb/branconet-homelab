import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { unitTestPlan, planFromInputs, deployStopReplacement, executionFor } from '../scripts/deploy-stop-unit-plan.mjs';
import { unitTestPlan as historyGetPlan } from '../scripts/deploy-history-get-unit-plan.mjs';
import { unitTestPlan as startGetPlan } from '../scripts/deploy-start-get-unit-plan.mjs';
import { unitTestPlan as previousPlan, executionFor as previousExecution } from '../scripts/deploy-start-post-unit-plan.mjs';
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
test('M01 fifteen mappings retain936 source controls and separate metadata without duplication', () => {
  assert.equal(plan.replacements.length, 15); assert.equal(plan.replacements.reduce((sum, row) => sum + row.controls, 0), 936);
  assert.deepEqual(plan.replacements.at(-1), deployStopReplacement);
  assert.equal(plan.selected.length, plan.discovered.length - 15);
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
test('M07 all thirteen frozen planner contracts remain intact', () => {
  for (const [fn, count] of [[firstPlan, 2], [constructorPlan, 3], [selectionPlan, 4], [logoutPlan, 5], [registerPlan, 6], [sessionPlan, 7], [jobPlan, 8], [accountPlan, 9], [currentSessionPlan, 10], [deletePlan, 11], [historyGetPlan, 12], [startGetPlan, 13], [previousPlan, 14]]) {
    const prior = fn(root); assert.equal(prior.replacements.length, count);
    assert.deepEqual(plan.replacements.slice(0, count), prior.replacements);
  }
  assert.deepEqual(previousPlan(root).selected.filter(name => name !== deployStopReplacement.original), plan.selected);
});
test('M08 all prior safeguards and loader plus new metadata remain selected', () => {
  for (const name of ['unit-test-plan.test.mjs', 'unit-test-loader.test.ts', 'account-store-unit-plan.test.mjs', 'ansible-selection-unit-plan.test.mjs', 'auth-logout-unit-plan.test.mjs', 'auth-register-unit-plan.test.mjs', 'auth-session-unit-plan.test.mjs', 'job-stream-unit-plan.test.mjs', 'current-account-unit-plan.test.mjs', 'current-session-unit-plan.test.mjs', 'deploy-history-delete-unit-plan.test.mjs', 'deploy-history-get-unit-plan.test.mjs', 'deploy-start-get-unit-plan.test.mjs', 'deploy-start-post-unit-plan.test.mjs', 'deploy-stop-unit-plan.test.mjs'])
    assert.ok(plan.selected.includes(`tests/${name}`));
});
test('M09 stop POST group contains only new63; default and plan dispatch stay exact', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'deploy-stop-node22']), [deployStopReplacement.current]);
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
});
test('M10 all thirteen prior groups keep their exact dispatch', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22', 'deploy-history-delete-node22', 'deploy-history-get-node22', 'deploy-start-get-node22', 'deploy-start-post-node22'])
    assert.deepEqual(executionFor(plan, ['--group', group]), previousExecution(previousPlan(root), ['--group', group]));
});
test('M11 unknown, incomplete and surplus arguments refuse', () => {
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'deploy-stop-node22', 'extra']])
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
test('M13 exact original/source LF and CRLF authority and selected POST remain pinned statically', () => {
  assert.equal(process.version, 'v22.23.3');
  const original = read(deployStopReplacement.original).replaceAll('\r\n', '\n');
  assert.equal(digest(original), deployStopReplacement.sha256);
  assert.equal(digest(original.replaceAll('\n', '\r\n')), 'ed1042bcc4970ebe8ef75cbf31aa5cdf87e567be93a74fe6abf987eee2780953');
  const source = read('src/app/api/deploy/stop/route.ts').replaceAll('\r\n', '\n');
  assert.equal(digest(source), 'd809b978c2575c2036ba80b81ac3e80a5f50776ff8640a0e297cfc13edbbcde1');
  assert.equal(digest(source.replaceAll('\n', '\r\n')), '3cf65f67dee0231d09dfb3cc9a78d644a89c95eb4737d8f58666de3f86f69fc9');
  const ts = createRequire(import.meta.url)('typescript'); assert.equal(ts.version, '5.9.3');
  const ast = ts.createSourceFile('static-post.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
  assert.equal(declarations.length, 1); assert.equal(declarations[0].parameters.length, 1);
  const selected = declarations[0].getText(ast);
  assert.equal(digest(selected), '66cc55810048964b4ac5cd0a4abfb33737e08dfdc14562a4c8cdcb00811c6f91');
  assert.equal(digest(selected.replaceAll('\n', '\r\n')), '399115400d6d3468e2958c2685eeb7d49cd0e13af85247575f585b1a121eb1c4');
  assert.deepEqual(declarations[0].modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
  // Parse/hash only: no original controls or production declaration evaluation.
});

test('M14 all63 helpers callbacks assertions ordering and original function bind scaffold remain exact', () => {
  const original = read(deployStopReplacement.original).replaceAll('\r\n', '\n');
  const current = read(deployStopReplacement.current).replaceAll('\r\n', '\n');
  const ts = createRequire(import.meta.url)('typescript');
  const normalize = text => {
    const emitted = ts.transpileModule(text, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
    const sf = ts.createSourceFile('static-controls.js', emitted, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
    assert.equal(sf.parseDiagnostics.length, 0);
    const transformer = context => node => {
      const visit = n => {
        if (ts.isParenthesizedExpression(n)) return ts.visitNode(n.expression, visit);
        if (ts.isIdentifier(n) && n.text === 'control' && ts.isCallExpression(n.parent) && n.parent.expression === n) return ts.factory.createIdentifier('test');
        return ts.visitEachChild(n, visit, context);
      };
      return ts.visitNode(node, visit);
    };
    const transformed = ts.transform(sf, [transformer]);
    try { return ts.createPrinter().printFile(transformed.transformed[0]); } finally { transformed.dispose(); }
  };
  const tail = original.slice(original.indexOf('type Handler ='));
  const projected = current.slice(current.indexOf('const bind =')).replace(/assert.equal\(count, 63\);\n$/, '');
  assert.equal(normalize(projected), normalize(tail));
  for (const witness of ["new Function('requireOperator', 'NextResponse', 'jobIdValid', 'prisma', 'activeJobs', javascript", 'bind(requireOperator, Response, jobIdValid, prisma, active)', 'Function.prototype[Symbol.hasInstance].call(PublicResponse, value)', 'json.rejection.handler', 'different-returned-id', 'abort return must stay unobserved', 'returned response rejection propagates'])
    assert.ok(tail.includes(witness));
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

test('M17 original five immediate bindings and new Function bind scaffold remain exact and inert', () => {
  const projection = read(deployStopReplacement.current).replaceAll('\r\n', '\n');
  const ts = createRequire(import.meta.url)('typescript');
  const ast = ts.createSourceFile('static-projection.js', projection, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const bindings = ast.statements.flatMap(node => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []);
  const bind = bindings.find(node => node.name.getText(ast) === 'bind'); assert.ok(bind);
  assert.ok(ts.isNewExpression(bind.initializer)); assert.equal(bind.initializer.expression.getText(ast), 'Function');
  const args = bind.initializer.arguments; assert.equal(args.length, 6);
  assert.deepEqual(args.slice(0,5).map(node => node.text), ['requireOperator', 'NextResponse', 'jobIdValid', 'prisma', 'activeJobs']);
  assert.ok(ts.isBinaryExpression(args[5])); assert.equal(args[5].left.getText(ast), 'javascript');
  assert.equal(args[5].right.text, '\\nreturn POST;'.replace('\\n', '\n'));
  assert.equal((projection.match(/\.control\(/g) ?? []).length, 0);
  assert.ok(projection.endsWith('assert.equal(count, 63);\n'));
});

test('M18 historical packaging failure remains explicit compiler assertion before require with no Node version assertion', () => {
  const original = read(deployStopReplacement.original).replaceAll('\r\n', '\n');
  const lines = original.split('\n');
  assert.equal(lines.length - 1, 247);
  assert.equal(lines[7], 'const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;');
  assert.equal(lines[8], "assert.ok(compiler, 'explicit current TypeScript input is required');");
  assert.equal(lines[9], 'const ts = createRequire(import.meta.url)(compiler);');
  assert.equal(original.includes('process.version'), false);
  assert.ok(plan.discovered.includes(deployStopReplacement.original));
  assert.equal(plan.selected.includes(deployStopReplacement.original), false);
  assert.ok(plan.selected.includes(deployStopReplacement.current));
});
test('M19 exact stop source order preserves authorization outside try and nullish-only JSON await', () => {
  const original = read(deployStopReplacement.original).replaceAll('\r\n', '\n');
  const source = read('src/app/api/deploy/stop/route.ts').replaceAll('\r\n', '\n');
  const selected = source.slice(source.indexOf('export async function POST')).trim();
  const ordered = ['await requireOperator()', 'if (auth instanceof NextResponse) return auth;', 'try {', 'request.nextUrl.searchParams.get("jobId") ?? (await request.json().catch(() => ({}))).jobId', 'if (!jobIdValid(jobId))', 'await prisma.job.findUnique({ where: { id: jobId }, select: { id: true, status: true } })', 'if (!job)', 'if (job.status !== "running")', 'activeJobs.get(jobId)', 'if (!controller)', 'controller.abort();', '{ success: true, jobId, stopping: true }', 'catch { return NextResponse.json({ error: "Job cancellation unavailable" }, { status: 503 }); }'];
  let position = -1;
  for (const text of ordered) { const next = selected.indexOf(text); assert.ok(next > position, text); position = next; }
  assert.ok(original.includes('const declaration = source.slice(node.getStart(ast), node.end);'));
});

test('M20 static source and scaffold preserve abort discard and exact status metadata without real dependencies', () => {
  const ts = createRequire(import.meta.url)('typescript');
  const source = read('src/app/api/deploy/stop/route.ts').replaceAll('\r\n', '\n');
  const ast = ts.createSourceFile('static-stop.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const post = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
  const attempt = post.body.statements.find(node => ts.isTryStatement(node)); assert.ok(attempt);
  const abort = attempt.tryBlock.statements.find(node => ts.isExpressionStatement(node) && node.expression.getText(ast) === 'controller.abort()');
  assert.ok(abort); assert.ok(ts.isCallExpression(abort.expression)); assert.equal(abort.expression.arguments.length, 0);
  assert.equal(abort.expression.expression.expression.getText(ast), 'controller');
  const success = attempt.tryBlock.statements.at(-1); assert.ok(ts.isReturnStatement(success));
  assert.ok(ts.isCallExpression(success.expression)); assert.equal(success.expression.expression.getText(ast), 'NextResponse.json');
  assert.equal(success.expression.arguments[1].getText(ast), '{ status: 202 }');
  const projection = read(deployStopReplacement.current);
  assert.equal(projection.includes('process.env.BORTUS_SOURCE_TYPESCRIPT'), false);
  assert.equal(projection.includes("from 'next/server'"), false);
  assert.equal(projection.includes("from '@/"), false);
});
