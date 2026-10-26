import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, executionFor, executionBatches, getSessionFromHeadersReplacement as row } from '../scripts/get-session-from-headers-unit-plan.mjs';
import { unitTestPlan as priorPlan, executionFor as priorExecution, executionBatches as priorBatches } from '../scripts/get-session-account-unit-plan.mjs';
import { sessionReplacement } from '../scripts/auth-session-unit-plan.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const read = name => readFileSync(new URL('../' + name, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
const digest = text => createHash('sha256').update(text).digest('hex');
const names = readdirSync(new URL('./', import.meta.url));
const plan = unitTestPlan(root), prior = priorPlan(root);
const ts = createRequire(import.meta.url)('typescript');
const parse = text => ts.createSourceFile('public.ts', text, ts.ScriptTarget.ES2022, true);
const original = read(row.original), projected = read(row.current);
const source = read('src/lib/auth.ts'), ast = parse(source);
const fn = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionFromHeaders');
const normalize = text => {
  const output = ts.transpileModule(text, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  const tree = parse(output); assert.equal(tree.parseDiagnostics.length, 0);
  const transformed = ts.transform(tree, [context => node => {
    const visit = n => {
      if (ts.isIdentifier(n) && n.text === 'control' && ts.isCallExpression(n.parent) && n.parent.expression === n) return ts.factory.createIdentifier('test');
      return ts.visitEachChild(n, visit, context);
    }; return ts.visitNode(node, visit);
  }]);
  try { return ts.createPrinter().printFile(transformed.transformed[0]); } finally { transformed.dispose(); }
};
test('M01 one new immutable mapping extends every prior mapping unchanged', () => {
  assert.equal(plan.replacements.length, prior.replacements.length + 1);
  assert.deepEqual(plan.replacements.slice(0, -1), prior.replacements);
  assert.deepEqual(plan.replacements.at(-1), row); assert.ok(Object.isFrozen(row));
  assert.equal(row.controls, 65); assert.equal(plan.replacements.reduce((n, r) => n + r.controls, 0), 1431);
});
test('M02 exact current discovery and mapping retain every input in order', () => {
  const discovered = names.filter(n => /\.test\.(?:ts|mjs)$/.test(n)).sort().map(n => 'tests/' + n);
  assert.deepEqual(plan.discovered, discovered);
  const mapped = new Map(plan.replacements.map(r => [r.original, r.current]));
  assert.deepEqual(plan.selected, [...new Set(discovered.map(n => mapped.get(n) ?? n))]);
  assert.equal(plan.selected.length, discovered.length - mapped.size);
});
test('M03 exact retained partition is complete disjoint and selected', () => {
  const originals = new Set(plan.replacements.map(r => r.original)), replacements = new Set(plan.replacements.map(r => r.current));
  assert.deepEqual(plan.retainedUnmapped, plan.discovered.filter(n => !originals.has(n) && !replacements.has(n)));
  assert.deepEqual([...plan.selected].sort(), [...plan.retainedUnmapped, ...replacements].sort());
  for (const n of plan.retainedUnmapped) assert.ok(plan.selected.includes(n), n);
});
test('M04 future public TS and MJS remain selected and ordinary without fixture edits', () => {
  const future = ['future-public-CVE.test.ts', 'future-public-CVE.test.mjs'];
  const extended = planFromInputs([...names, ...future], read);
  for (const n of future.map(n => 'tests/' + n)) {
    assert.ok(extended.discovered.includes(n)); assert.ok(extended.selected.includes(n)); assert.ok(extended.retainedUnmapped.includes(n));
    assert.deepEqual(executionBatches(extended.selected).find(b => b.files.includes(n)).flags, []);
  }
});
test('M05 all mapped historical authorities remain required', () => {
  for (const r of plan.replacements) assert.throws(() => planFromInputs(names.filter(n => 'tests/' + n !== r.original), read), /Missing historical input/);
});
test('M06 all replacements and separate session packaging remain required', () => {
  for (const r of plan.replacements) assert.throws(() => planFromInputs(names.filter(n => 'tests/' + n !== r.current), read), /Missing replacement/);
  assert.throws(() => planFromInputs(names.filter(n => 'tests/' + n !== sessionReplacement.metadata), read), /Missing packaging metadata/);
});
test('M07 every historical hash still rejects changed bytes', () => {
  for (const r of plan.replacements) assert.throws(() => planFromInputs(names, n => read(n) + (n === r.original ? '\n// drift' : '')), /Historical input changed/);
});
test('M08 exact CRLF representation preserves canonical inputs', () => {
  assert.deepEqual(planFromInputs(names, n => read(n).replaceAll('\n', '\r\n')), plan);
});
test('M09 metadata and nonmetadata retained sets remain disjoint complete and selected', () => {
  const metadata = plan.retainedUnmapped.filter(n => /unit-plan\.test\.mjs$/.test(n) || n.endsWith('/unit-test-plan.test.mjs') || n.endsWith('/unit-test-loader.test.ts'));
  const other = plan.retainedUnmapped.filter(n => !metadata.includes(n));
  assert.deepEqual([...metadata, ...other].sort(), [...plan.retainedUnmapped].sort());
  assert.equal(metadata.some(n => other.includes(n)), false);
  assert.ok(metadata.includes('tests/get-session-from-headers-unit-plan.test.mjs'));
  for (const n of [...metadata, ...other]) assert.ok(plan.selected.includes(n));
});
test('M10 new group selects only the new65 projection with ordinary flags', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'get-session-from-headers-node22']), [row.current]);
  assert.deepEqual(executionBatches([row.current]), [{ files: [row.current], flags: [] }]);
  assert.equal(plan.selected.includes(row.original), false); assert.equal(plan.selected.filter(n => n === row.current).length, 1);
});
test('M11 every prior group retains exact dispatch and flags', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22', 'deploy-history-delete-node22', 'deploy-history-get-node22', 'deploy-start-get-node22', 'deploy-start-post-node22', 'deploy-stop-node22', 'deploy-stream-node22', 'deployment-pods-node22', 'ensure-jwt-secret-node22', 'get-current-role-node22', 'get-session-account-from-headers-node22', 'get-session-account-node22']) {
    assert.deepEqual(executionFor(plan, ['--group', group]), priorExecution(prior, ['--group', group]));
    assert.deepEqual(executionBatches(executionFor(plan, ['--group', group])), priorBatches(priorExecution(prior, ['--group', group])));
  }
});
test('M12 plan default and malformed argument guards stay intact', () => {
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'get-session-from-headers-node22', 'extra']]) assert.throws(() => executionFor(plan, args));
});
test('M13 batching is the identical previous function with exact selected order', () => {
  assert.equal(executionBatches, priorBatches);
  assert.deepEqual(executionBatches(plan.selected).flatMap(b => b.files), plan.selected);
  assert.deepEqual(executionBatches(plan.selected).filter(b => b.flags.length), [{ files: ['tests/get-session-account-node22.test.mjs'], flags: ['--experimental-vm-modules'] }]);
});
test('M14 runner body is unchanged and only its planner import advances', () => {
  const runner = read('scripts/run-unit-tests.mjs');
  const importPattern = /^import \{ unitTestPlan, executionFor, executionBatches \} from '(\.\/[a-z]+(?:-[a-z]+)*-unit-plan\.mjs)';$/m;
  const binding = runner.match(importPattern); assert.ok(binding);
  const planner = read('scripts/' + binding[1].slice(2));
  for (const name of ['unitTestPlan', 'executionFor', 'executionBatches']) assert.ok(planner.includes(name), name);
  assert.equal(digest(runner.replace(importPattern, "import { unitTestPlan, executionFor, executionBatches } from './get-session-account-unit-plan.mjs';")), '876668b121c21dfb509a406afa8912603080830e161c6b94f1e1f1208e438c98');
  assert.ok(read('scripts/get-session-from-headers-unit-plan.mjs').includes("export { executionBatches } from './get-session-account-unit-plan.mjs';"));
});
test('M15 every frozen prior planner source group metadata helper loader package and config remains exact', () => {
  const frozen = {
    "eslint.config.mjs": "d21103e76c3793d7ce5ce6d6ea982798f219cdd4a61806ecd00b51e7fbc75962",
    "package-lock.json": "f5edc2ed62d8e18350f9fd974fb0ccdf530098fa59340370baa932b73dda5f04",
    "package.json": "81cfc27c470a40b9b15120704b3efc0db2e640e793ad7d0f03ddc43cbf33c55e",
    "scripts/account-store-unit-plan.mjs": "cffab0ea41dd0073907bc073b0269b84fae9ad0122ee46b47f218971661941e3",
    "scripts/ansible-selection-unit-plan.mjs": "78b27e551a3f776763395fbff7b26a055dbf811d427c6af84706acd956839b39",
    "scripts/auth-logout-unit-plan.mjs": "acb6753b126b2f427afb44f42ce6339fc0569044d1e6ebac4c78ad6d88188217",
    "scripts/auth-register-unit-plan.mjs": "dd17a0d508c2486b9d305db110e553f0037a7dcc38208dba9b63241d01e8c794",
    "scripts/auth-session-unit-plan.mjs": "c44098a39572f0fd4655e4556bb85076b058005e8755f5575709dff81d8b8c25",
    "scripts/browser-ci-fixture.mjs": "6090ce1fc3ef020718a16039c7fa68ddf4d538f4a61bef51270863f1115e1b68",
    "scripts/browser-ci-smoke.mjs": "8fc88ea7aefaa790cdca1684b830ccc69ddb8b4a6fcf37075df35a38be8fb8f3",
    "scripts/build-account-worker.mjs": "d3dbd7894f543b6ea9003f91a71c1ea2fbee83a598909ff25efdea3648f4f038",
    "scripts/build-secret-flat-native.mjs": "03778c9e6146d35982766af92c06f9c082d257a176cc138419648fa5d4c97235",
    "scripts/current-account-unit-plan.mjs": "a3f4ffbf1f3398284a0ec438f755a247cdb6fdf9b4c5db9c9fc5e16c992ac29b",
    "scripts/current-session-unit-plan.mjs": "36ebf5c2e9756bfd7aff36f35afc342748ec559192a04cc6f9da467d12e4fd5c",
    "scripts/deploy-history-delete-unit-plan.mjs": "4fed0456e60f4b7f6d649cf2fbe23740378bd2ee8cb8ee43fb6564a4b3de0080",
    "scripts/deploy-history-get-unit-plan.mjs": "5a6428ba37a931180e32424804806f491de58e4846f06225ceeb80d2c2658392",
    "scripts/deploy-start-get-unit-plan.mjs": "f9e7f9427103cacb3c35f0f17f773552788bf8a56e9a26fb667070db3bfa6538",
    "scripts/deploy-start-post-unit-plan.mjs": "cc3762862dcaa77fe2644646408ddcab1113641d79692cb874499939ffa9887e",
    "scripts/deploy-stop-unit-plan.mjs": "3c8ff5a8cb0a4280004cdb3adc0951c126e424aff6ac1e224aa8a3f6b6f3cfa3",
    "scripts/deploy-stream-unit-plan.mjs": "0697f1d6fc85780358bf728c87f0862c69f128998dcf760a762f4e6cf6953739",
    "scripts/deployment-pods-unit-plan.mjs": "e1e5ef45f301e2fb6c43fc7edfd6a7843cb941e201d787001f1134872f19ee48",
    "scripts/ensure-jwt-secret-unit-plan.mjs": "3af722ee05fd620b68ec422a064a6e898cd1ca597cffca3e942a9e89f365fd9c",
    "scripts/get-current-role-unit-plan.mjs": "58261543fa579f529e09500bea3d951af2b1ece00de06a1532ecd68b6ac632d4",
    "scripts/get-session-account-from-headers-unit-plan.mjs": "9d6d366cf3a730bb2e38d92e1dc21c6dfa363d2d33aa2dd6386dd6dbcc284edb",
    "scripts/get-session-account-unit-plan.mjs": "ac76f53a4a42e4b959528ef156963954d809afbb6500442db61b0ff2990afb92",
    "scripts/job-stream-unit-plan.mjs": "e70697ab45a452ef0b9a5d5a77d08852c3fb491e8bb46f30881d2dd50a710184",
    "scripts/package-account-worker.mjs": "1ddcb11c959f7c4e4f6dea7bb1eb21824bd0bf73f849262c31610037e14d583d",
    "scripts/package-secret-flat-native.mjs": "80244d23cbfd9215c012adab33a66c6ff7411b7d8f3de20e128792e9a8881d63",
    "scripts/patch-next-body-finalize.mjs": "251a1c44e1f5986adae4e04143cae8e329b3b21dfc7e9fad41b63e8260c444e3",
    "scripts/regression-sensitivity-db.mjs": "83f5c3df1dddfa47fcfbfe57c71cc1dc263f5f0a08d044204881d6dd8af6b888",
    "scripts/regression-sensitivity-process.mjs": "1b4ec23dddf51035ba8543961a8ebcb2e1b9e9dd366ed6ecd3a7de095b63d9f4",
    "scripts/regression-sensitivity.mjs": "bdce5398b9b8a2a89cc75a03b4640b2d0244189012d92aac7dffa12dbc03dbc5",
    "scripts/unit-test-discovery-contract.mjs": "96510637ed38d729e61a7082b2ffae211ccb40518f29be51b0b5eaf3daa7730a",
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
    "tests/deploy-start-get-node22.test.mjs": "4daa75860c998bf192ed9047b273e4dbda8b02833278a1e3b32f1a35d1a45324",
    "tests/deploy-start-get-unit-plan.test.mjs": "a553f4a56a282c0039fe950cda9c0d38642d5210632715b12e7b0eb3b91db9c2",
    "tests/deploy-start-post-node22.test.mjs": "e064c701190e5a456b7651499ac49fe005e740f9506df016acc43665deab2eea",
    "tests/deploy-start-post-unit-plan.test.mjs": "cdd8799dc01218fda3d7b47fd33bce4ef59f21e940ec958499bbcfa03156c3bc",
    "tests/deploy-stop-node22.test.mjs": "0d46811b9f5a5b8af124893fcdaa3e51dae8df2c2e32210cbbec404fd1d53047",
    "tests/deploy-stop-unit-plan.test.mjs": "37311fa7ce5e3a79228bc0695b5e56cec1eb4fa289d05aea111c6670c9a26266",
    "tests/deploy-stream-node22.test.mjs": "97a0ce3e5ba330564fe0ec2ce78e21f31a420bf82fdc79b08cb64723c67be179",
    "tests/deploy-stream-unit-plan.test.mjs": "caa9bc5899baf1f2de8fea3de5493d9745acb8655e609e98fdd0400e08393284",
    "tests/deployment-pods-node22.test.mjs": "0ad0a4289654ed79e7dd39f3571b3973ceeaebc4b733f1ed5a7970ebf8e9c295",
    "tests/deployment-pods-unit-plan.test.mjs": "2e7507bbc382e6596639342a9bbefa2678f024c12549a94f61841eaaf7470199",
    "tests/ensure-jwt-secret-node22.test.mjs": "9043a250b21cca62778650bd932f195ab6045b8b8ac585f7b3995a5b61219cca",
    "tests/ensure-jwt-secret-unit-plan.test.mjs": "667167f27e33843a3fc7663f24c4a3fe13121b3ed609e449e9063545ca746e1a",
    "tests/flux-zoom.browser.mjs": "c983ef3b86b6b82f251024bb262bad9926f969efe604222c24f5480c6bb98f43",
    "tests/flux.browser.mjs": "c7ef1ecbfc940914a302782d603aa7fcb5f9008dabfc44ca6a17dfd6d5d7673d",
    "tests/get-current-role-node22.test.mjs": "365d067db0ecdbe7c31bb82e84d6d4101c63f2862a04f7ea9b95a0772e654b80",
    "tests/get-current-role-unit-plan.test.mjs": "e11ff4038aa9f5d17e5d036324106d1bb9371cd51fcfbba94a2f9675c7f04092",
    "tests/get-session-account-from-headers-node22.test.mjs": "600c2c18ba3a5f7b1ef4cd28d638ed0e49a82e63dc68ed01110a6c462640c3f9",
    "tests/get-session-account-from-headers-unit-plan.test.mjs": "2a0da18ef8c3cf29db1f7678a3c4e72616812ca413928411d2279f9f10477869",
    "tests/get-session-account-node22.test.mjs": "143436eb149b844bc4133a8303a174b037f5f7cbe6cd0bbe1367f2c695030c29",
    "tests/get-session-account-unit-plan.test.mjs": "9a36e27eaead3bdabfec5041d448ed92c619489593790e852c656cba6a29d808",
    "tests/job-stream-unit-plan.test.mjs": "829585272b526c2997fedf8e96a3a336bce0d1ba03ef8cce4b299645b2b46738",
    "tests/kv-identity.browser.mjs": "b203434167cda1b634d2a04b0e5914f1c13f08ccb74ffb12aaa51eb6ce7c9441",
    "tests/kv-workbench.browser.mjs": "015dfae87926115f16a661346bcd9ab28c2febf83bfb8efeb407741472332b0d",
    "tests/kv-workflows.browser.mjs": "3cc36f81d1ceb4114a95f4c24ca347d644029236dd6b65ac41931d68e23f36f2",
    "tests/optional-code.browser.mjs": "5be30eb4406ad9b350d8764db9de9a5fdcdb02d70066e48612d933da9ed79c16",
    "tests/shared-freshness.browser.mjs": "ef6b4fbad5e922cf477afdeffde9c0fede278d05c1e04c8aa1a12a7d8a9fbdc4",
    "tests/support/node22-source-harness.mjs": "42dc6445ea0fb3f27c76fef3194fe2d1caf949d1030ac5cdf1b131b3ceb72cea",
    "tests/terminal.browser.mjs": "b7fcfa82840c4457df875089b3342ee21cb58ca32d4a3e103b11954e9177ef60",
    "tests/unit-test-loader.test.ts": "131a957bff2ffd4fb7573a38648b71fab0948cd87df6430da0548d32c2f47536",
    "tests/unit-test-plan.test.mjs": "f97b128d6d0b9354a503dfd33bb89d44e71bffe649793df64477c9555564cf95",
    "tests/wide-zoom.browser.mjs": "a64d6cea6cd60c193983087b69139a5c5f78ffb2c64ede1e0e11bd5321f7c514",
    "tests/workbench-lifecycle.browser.mjs": "504cdfaaa3daf716b10fb30678c64590c5168dddbc13029cd0e81e0bea9dcbb5",
    "tsconfig.json": "1a9aeca0dd2e384e0d3341044fab297e730f40ea985c45d3101ec5316e142570"
};
  for (const [name, hash] of Object.entries(frozen)) assert.equal(digest(read(name)), hash, name);
});
test('M16 historical175line authority and failure ordering remain exact', () => {
  assert.equal(digest(original), row.sha256); assert.equal(digest(original.replaceAll('\n', '\r\n')), '56bb60283c4a686a2b2bfa073f3ea45aebfff2c1f56ee9103ced6aa2aea88ff0');
  assert.equal(original.split('\n').length - 1, 175);
  assert.equal(original.split('\n')[11], 'const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);');
  assert.equal(original.split('\n')[12], 'assert.equal(process.version, "v24.18.0");');
  assert.equal(original.includes('Explicit compiler path required'), false);
});
test('M17 exact source declaration one async parameter and seven ordered statements', () => {
  assert.equal(process.version, 'v22.23.3'); assert.equal(ts.version, '5.9.3'); assert.equal(ast.parseDiagnostics.length, 0);
  assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
  assert.equal(digest(fn.getText(ast)), '46335e19c65ac7f64ae3d6bb3854bf373aca39d6c9aeb83833378e0d389c23e9');
  assert.equal(digest(fn.getText(ast).replaceAll('\n', '\r\n')), '6e4c6280328981af61099da030b060887d75c7020221075e83dee27b5b2a26d8');
  assert.deepEqual(fn.modifiers.map(n => n.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
  assert.deepEqual(fn.parameters.map(n => n.getText(ast)), ['cookieHeader: string | null']); assert.equal(fn.body.statements.length, 7);
  assert.deepEqual(fn.body.statements.map(n => n.getText(ast)), ["if (!cookieHeader) return null;", "const match = cookieHeader.match(\n    new RegExp(`(?:^|;\\\\s*)${AUTH_COOKIE}=([^;]*)`)\n  );", "const token = match?.[1];", "if (!token) return null;", "const payload = await verifyJWT(token);", "if (!payload) return null;", "return currentSession(payload);"]);
});
test('M18 all65 helpers callbacks assertions and order are identical after type erasure and bare rename', () => {
  const tail = original.slice(original.indexOf('type Selected ='));
  const current = projected.slice(projected.indexOf('const cookie =')).replace(/assert.equal\(count, 65\);\n$/, '');
  assert.equal(normalize(current), normalize(tail));
  assert.ok(projected.endsWith('assert.equal(count, 65);\n'));
});
test('M19 original non-strict VM expression and all four inert bindings are preserved exactly', () => {
  const oldLoad = parse(original).statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'load');
  const newAst = parse(projected), newLoad = newAst.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'load');
  assert.equal(normalize(oldLoad.getText()), normalize(newLoad.getText()));
  const call = newLoad.body.statements[0].expression;
  assert.equal(call.expression.getText(newAst), 'vm.runInNewContext');
  assert.equal(call.arguments[0].getText(newAst), '"(" + javascript + ")"');
  assert.deepEqual(call.arguments[1].properties.map(n => n.name.text), ['AUTH_COOKIE', 'verifyJWT', 'currentSession', 'RegExp']);
  assert.equal(newLoad.getText().includes('use strict'), false);
});
test('M20 member names are preserved and registration renaming cannot rewrite members', () => {
  const members = text => { const a = parse(text), out = []; const visit = n => { if (ts.isPropertyAccessExpression(n)) out.push(n.name.text); ts.forEachChild(n, visit); }; visit(a); return out; };
  assert.deepEqual(members(projected.slice(projected.indexOf('const cookie =')).replace(/assert.equal\(count, 65\);\n$/, '')), members(original.slice(original.indexOf('type Selected ='))));
  assert.equal(projected.includes('control.afterEach'), false);
});
test('M21 projection selects only the exported function and no real module or initializer', () => {
  const p = parse(projected), vars = p.statements.flatMap(n => ts.isVariableStatement(n) ? [...n.declarationList.declarations] : []);
  assert.equal(vars.find(n => n.name.getText(p) === 'selected').initializer.getText(p), "declaration.replace(/^export\\s+/, '')");
  assert.equal(vars.find(n => n.name.getText(p) === 'compiled').initializer.arguments[0].getText(p), 'selected');
  for (const name of ['directAccountReader.', 'signingKey.', 'import("next/headers")', 'process.env.BORTUS_SOURCE_TYPESCRIPT', 'node:child_process']) assert.equal(projected.includes(name), false);
});
test('M22 original fault identity freshness concurrency and promise adoption assertions remain exact', () => {
  for (const text of ['synchronous verifier fault', 'asynchronous verifier fault', 'synchronous current metadata fault', 'asynchronous current metadata fault', 'current metadata promise is adopted', 'fresh verifier and account decisions', 'simultaneous calls retain their own payload', 'nonthenable payload properties remain opaque']) {
    assert.ok(original.includes(text), text); assert.ok(projected.includes(text), text);
  }
});
test('M23 new mapping affects only its historical original and leaves prior selections intact', () => {
  assert.deepEqual(prior.selected.filter(n => n !== row.original), plan.selected);
  assert.equal(plan.replacements.filter(r => r.original === row.original).length, 1);
  assert.equal(plan.selected.some(n => n.startsWith('--')), false);
});
test('M24 separate packaging control and actual unmapped reader remain selected without executing either', () => {
  assert.equal(sessionReplacement.metadataControls, 1); assert.ok(plan.selected.includes(sessionReplacement.metadata));
  assert.ok(plan.selected.includes('tests/worker-account-reader.test.ts'));
  assert.ok(plan.retainedUnmapped.includes('tests/worker-account-reader.test.ts'));
});