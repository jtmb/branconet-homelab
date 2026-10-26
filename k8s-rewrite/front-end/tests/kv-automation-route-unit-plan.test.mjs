import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { unitTestPlan, planFromInputs, executionFor, executionBatches, kvAutomationRouteReplacement as row } from '../scripts/kv-automation-route-unit-plan.mjs';
import { unitTestPlan as priorPlan, executionFor as priorExecution, executionBatches as priorBatches } from '../scripts/kv-audit-route-unit-plan.mjs';
import { sessionReplacement } from '../scripts/auth-session-unit-plan.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const read = name => readFileSync(new URL('../' + name, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
const digest = text => createHash('sha256').update(text).digest('hex');
const names = readdirSync(new URL('./', import.meta.url));
const plan = unitTestPlan(root), prior = priorPlan(root);
const ts = createRequire(import.meta.url)('typescript');
const parse = text => ts.createSourceFile('public.ts', text, ts.ScriptTarget.ES2022, true);
const original = read(row.original), projected = read(row.current);
const source = read('src/app/api/kv/automation/route.ts'), ast = parse(source);
const fn = ast.statements.find(n=>ts.isFunctionDeclaration(n) && n.name?.text==='POST');
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
  assert.equal(row.controls, 162); assert.equal(plan.replacements.reduce((n, r) => n + r.controls, 0), 1982);
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
  assert.ok(metadata.includes('tests/kv-automation-route-unit-plan.test.mjs'));
  for (const n of [...metadata, ...other]) assert.ok(plan.selected.includes(n));
});
test('M10 new group selects only the new162 projection with ordinary flags', () => {
  assert.deepEqual(executionFor(plan, ['--group', 'kv-automation-route-node22']), [row.current]);
  assert.deepEqual(executionBatches([row.current]), [{ files: [row.current], flags: [] }]);
  assert.equal(plan.selected.includes(row.original), false); assert.equal(plan.selected.filter(n => n === row.current).length, 1);
});
test('M11 every prior group retains exact dispatch and flags', () => {
  for (const group of ['account-source-node22', 'account-store-node22', 'ansible-selection-node22', 'auth-logout-node22', 'auth-register-node22', 'auth-session-node22', 'job-stream-node22', 'current-account-node22', 'current-session-node22', 'deploy-history-delete-node22', 'deploy-history-get-node22', 'deploy-start-get-node22', 'deploy-start-post-node22', 'deploy-stop-node22', 'deploy-stream-node22', 'deployment-pods-node22', 'ensure-jwt-secret-node22', 'get-current-role-node22', 'get-session-account-from-headers-node22', 'get-session-account-node22', 'get-session-from-headers-node22', 'get-session-node22', 'job-id-valid-node22', 'kv-audit-route-node22']) {
    assert.deepEqual(executionFor(plan, ['--group', group]), priorExecution(prior, ['--group', group]));
    assert.deepEqual(executionBatches(executionFor(plan, ['--group', group])), priorBatches(priorExecution(prior, ['--group', group])));
  }
});
test('M12 plan default and malformed argument guards stay intact', () => {
  assert.deepEqual(executionFor(plan, ['--plan']), []); assert.equal(executionFor(plan, []), plan.selected);
  for (const args of [['--group'], ['--group', 'unknown'], ['--plan', 'extra'], ['--unknown'], ['--group', 'kv-automation-route-node22', 'extra']]) assert.throws(() => executionFor(plan, args));
});
test('M13 new layer delegates exact batching including both prior VM children', () => {
  assert.deepEqual(executionBatches(plan.selected), priorBatches(plan.selected));
  assert.deepEqual(executionBatches(plan.selected).flatMap(b => b.files), plan.selected);
  assert.deepEqual(executionBatches(plan.selected).filter(b => b.flags.length), [
    { files: ['tests/get-session-account-node22.test.mjs'], flags: ['--experimental-vm-modules'] },
    { files: ['tests/get-session-node22.test.mjs'], flags: ['--experimental-vm-modules'] },
  ]);
  assert.deepEqual(executionBatches([row.current]), [{files:[row.current],flags:[]}]);
});
test('M14 runner body unchanged under normalized future planner import', () => {
  const runner = read('scripts/run-unit-tests.mjs');
  const pattern = /^import \{ unitTestPlan, executionFor, executionBatches \} from '(\.\/[a-z]+(?:-[a-z]+)*-unit-plan\.mjs)';$/m;
  const binding = runner.match(pattern); assert.ok(binding);
  const planner = read('scripts/' + binding[1].slice(2));
  for (const name of ['unitTestPlan', 'executionFor', 'executionBatches']) assert.ok(planner.includes(name));
  assert.equal(digest(runner.replace(pattern, "import { unitTestPlan, executionFor, executionBatches } from './get-session-from-headers-unit-plan.mjs';")), '0cbaa4ae5f0070867cb08c92efa76e2c5a55725ee92b3e17d32822193fb5435f');
});
test('M15 every frozen prior planner source group metadata helper loader package and config remains exact', () => {
  const frozen = {
    "scripts/job-id-valid-unit-plan.mjs": "e2f3a8f366aec8b9df5d6c0d94ebf75e96e9a2e1c8ca29c9b81f92a11326bd46",
    "tests/job-id-valid-node22.test.mjs": "34f5883c515377a42c7a41eb2c32ff14f6c7f1eb9130f73cf426a0d76c4a95a0",
    "tests/job-id-valid-unit-plan.test.mjs": "e0cc32a143f3f355800a3aaa7502db54635c779d893802db973494edfbf73d8d",
    "eslint.config.mjs": "d21103e76c3793d7ce5ce6d6ea982798f219cdd4a61806ecd00b51e7fbc75962",
    "next.config.ts": "9f5766020decf8e0c7b83ac9ad739da5ac8566ce4f5eaee4e56ba5f16cd4cb9e",
    "package-lock.json": "f5edc2ed62d8e18350f9fd974fb0ccdf530098fa59340370baa932b73dda5f04",
    "package.json": "81cfc27c470a40b9b15120704b3efc0db2e640e793ad7d0f03ddc43cbf33c55e",
    "scripts/account-store-unit-plan.mjs": "cffab0ea41dd0073907bc073b0269b84fae9ad0122ee46b47f218971661941e3",
    "scripts/ansible-selection-unit-plan.mjs": "78b27e551a3f776763395fbff7b26a055dbf811d427c6af84706acd956839b39",
    "scripts/auth-logout-unit-plan.mjs": "acb6753b126b2f427afb44f42ce6339fc0569044d1e6ebac4c78ad6d88188217",
    "scripts/auth-register-unit-plan.mjs": "dd17a0d508c2486b9d305db110e553f0037a7dcc38208dba9b63241d01e8c794",
    "scripts/auth-session-unit-plan.mjs": "c44098a39572f0fd4655e4556bb85076b058005e8755f5575709dff81d8b8c25",
    "scripts/browser-ci-fixture.mjs": "6090ce1fc3ef020718a16039c7fa68ddf4d538f4a61bef51270863f1115e1b68",
    "scripts/browser-ci-smoke.mjs": "8fc88ea7aefaa790cdca1684b830ccc69ddb8b4a6fcf37075df35a38be8fb8f3",
    "scripts/browser-ci-smoke.sh": "b07097c9e8e9232e00d920a407e88534eaacf4b2da0c3ed3604bab8d391ef768",
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
    "scripts/get-session-from-headers-unit-plan.mjs": "7914f7205d3f1951fc23782cc2f160088977975de11b0983ebfbcfbe655a609d",
    "scripts/get-session-unit-plan.mjs": "f049f5398b908d46cc0865a9e6c6324fdfa9b231591bfd0c1aebc291b1e7984f",
    "scripts/job-stream-unit-plan.mjs": "e70697ab45a452ef0b9a5d5a77d08852c3fb491e8bb46f30881d2dd50a710184",
    "scripts/package-account-worker.mjs": "1ddcb11c959f7c4e4f6dea7bb1eb21824bd0bf73f849262c31610037e14d583d",
    "scripts/package-secret-flat-native.mjs": "80244d23cbfd9215c012adab33a66c6ff7411b7d8f3de20e128792e9a8881d63",
    "scripts/patch-next-body-finalize.mjs": "251a1c44e1f5986adae4e04143cae8e329b3b21dfc7e9fad41b63e8260c444e3",
    "scripts/regression-sensitivity-db.json": "e4450949abc11c3c74cce2cada3089fe4188f5f236e1e3c1c206358eeba54f59",
    "scripts/regression-sensitivity-db.mjs": "83f5c3df1dddfa47fcfbfe57c71cc1dc263f5f0a08d044204881d6dd8af6b888",
    "scripts/regression-sensitivity-process.json": "38f4e78e65c705d523139285949a8eab78508597084cdf81e9a94d85e3ec386d",
    "scripts/regression-sensitivity-process.mjs": "1b4ec23dddf51035ba8543961a8ebcb2e1b9e9dd366ed6ecd3a7de095b63d9f4",
    "scripts/regression-sensitivity.json": "e9331ac66c8840a35f304d04f9d1135daaeaa53549df4b6e87478a7c5c9bd32b",
    "scripts/regression-sensitivity.mjs": "bdce5398b9b8a2a89cc75a03b4640b2d0244189012d92aac7dffa12dbc03dbc5",
    "scripts/unit-test-discovery-contract.mjs": "96510637ed38d729e61a7082b2ffae211ccb40518f29be51b0b5eaf3daa7730a",
    "scripts/unit-test-discovery-fixtures.json": "12700826a17856147bf63cf907b3b0c633cd601ab60c322b1b1bb8fa51d6f1f3",
    "scripts/unit-test-plan.mjs": "15f05baa5b9ed524b74425d1724fc2366d21eb6a90353eeb1dddaf2ed49a145b",
    "tests/account-error-node22.test.mjs": "028722cd14fb64d534d5da0a76949e07421eb0bf3e41fe891b0e045b4d795a8e",
    "tests/account-error-source.test.ts": "541890b9f39ba952cc22800248d9b889ee19d0e7cc51ebb3894c38afdf5ae3ce",
    "tests/account-failure-node22.test.mjs": "baf655484a1d1810b3738d6262cc249c5058b16528bb465c1f27e5292ba381aa",
    "tests/account-failure-source.test.ts": "44cdba1ae5a3f4c731e3b1b5cad2a632be3c1c1f75a89ee375267b705ec7972c",
    "tests/account-process.test.ts": "71d1d0c3cb2f8139ad733b72f302bf131cf52f924dc74fa49377d1982a943d04",
    "tests/account-queue.test.ts": "a87a0e5fcd49250b9c8699c4f2f381bd7c4cff1f148afc5d8a2786aa5842fb59",
    "tests/account-registration.test.ts": "a7ff15a27fb9525a66d96029f842513cb61d30747c4643350001e2023226928e",
    "tests/account-store-constructor-node22.test.mjs": "406855837bc22f41686fa2a2e327c84e1d9e9a89d745d6c9f125aa19135cd3c0",
    "tests/account-store-constructor-source.test.ts": "1e7d4bbb71ff6f2a8e5aa38c021ec00997af12ee8cd49bd65d634c20084367c7",
    "tests/account-store-unit-plan.test.mjs": "db91826541638f7830e5482651f3dd120d30ddf43ad8478e8b0b88e0224c8b73",
    "tests/accounts.test.ts": "31e14ae21ece84431076a83f24c2fbe9567ab382dd5b4c702e760890cbd8f01e",
    "tests/alias-page.test.ts": "4ae777cbe92d67201ff503f7f2d641b3e796656ea0ce83959903a18700ecc3a0",
    "tests/ansible-progress.test.ts": "a3a46fdc51f30fef04f7f3809d3ce5e003e9414f87f4f819b4f4fd27e250bb67",
    "tests/ansible-selection-node22.test.mjs": "c88fd1027f9b9b281347c67bd330ae4730740ee6ba1530e19810dadac660489f",
    "tests/ansible-selection-source.test.ts": "004d6609a3840974ca6c119ab48b3b604b5713cdea6536e0be5881c20eba60bb",
    "tests/ansible-selection-unit-plan.test.mjs": "d6c3ff8b710a7f30db9aa21ae66ed9ff1542e8d60ec7843a4f294ff740bce21f",
    "tests/ansible.integration.ts": "b093a43fdfd6fb3242b40d99cd47e6a066640780a79e9ef617542ae446c1313f",
    "tests/auth-login-post-source.test.ts": "892f245cdea69d2349970f3219a941fe4223ba12fbede9330fb7859a01ad5062",
    "tests/auth-logout-post-node22.test.mjs": "5560c250b261eccca5e10c183406d6a7033edd21c73bd6f45dbdefd5af3334a4",
    "tests/auth-logout-post-source.test.ts": "2871f65f8fe1074c69eac9b7b364effd4a1be6134e6e5ea258ed3b690ad1f7bd",
    "tests/auth-logout-unit-plan.test.mjs": "5dd34eb70835eae6e937775ce7c6d8b426ec7e2e80d873c704697b7d82cdd438",
    "tests/auth-register-post-node22.test.mjs": "f99b0444c2a430300f99bd8727864a378ed9f7faf93ea09f640bd53c438099c0",
    "tests/auth-register-post-source.test.ts": "c9d6fc744d812617bfe1aa47bec83f1e0abfd9fbbb37d902a273571639ee2d7d",
    "tests/auth-register-unit-plan.test.mjs": "90ea6c3ce775d39bf45fd05c474343ff20608abab35f9cddf87eec9b6bc109c5",
    "tests/auth-session-get-node22.test.mjs": "bf99fb2a72be2cebc97cb793353dee976cf7aace3d8b442b0abc4612404589c8",
    "tests/auth-session-get-source.test.ts": "5059b57ea27bc9f8c365af970792fbcbc9a343cc0441847853e9d41fd5efb7a7",
    "tests/auth-session-unit-plan.test.mjs": "5614901d17bfc37f4daff8d9d654a106b6620646f1881a32c89e8ef99e1fe926",
    "tests/cluster-overview-health.test.ts": "a52d6cea3fabb930203db4286730294e2118438931404bcfe58a3dc5dc5ebbf0",
    "tests/create-job-stream-node22.test.mjs": "d873f9956fd20f177bab16aa08ceefebdf66a83132cec96f83a1ef4e514c86a2",
    "tests/create-job-stream-source.test.ts": "eb8cef4ae17c68c0a63744396097744fae9845c7e6c1cd7ea1494c28c84ef4e0",
    "tests/current-account-node22.test.mjs": "565d9f2950caa363009cc1ea5e709458cd4283897fc8669addf7e1e28b7b155f",
    "tests/current-account-source.test.ts": "ba41a60bef22e448d10f50879c2f9558286033bb996499aa6ee19cc5a5b57677",
    "tests/current-account-unit-plan.test.mjs": "00692a71f4c475ccaab7269588aa2729e12425662156f1f41a09f4b16f555ba8",
    "tests/current-session-node22.test.mjs": "0c4316b29c5f5fe4e67387e7b377a116df7bfa95c29f11f4985e5cd95ba5f640",
    "tests/current-session-source.test.ts": "73bab43f307539469588f486e61c7b38e522efdf5765a7ab923aa419ba39f234",
    "tests/current-session-unit-plan.test.mjs": "a17d2740c877dc71acf80b75f5cfdde850cb0c887608209669316d4efdfce892",
    "tests/deploy-history-delete-node22.test.mjs": "b6d79dd1ff603e5450ccb2de667fd1ee013c5e5de98af12666a6d5ace02aecb1",
    "tests/deploy-history-delete-source.test.ts": "b5ed24de4d1567767d2116b0bb0b0877202ec945d3ae1c4728e154ea007494af",
    "tests/deploy-history-delete-unit-plan.test.mjs": "963ff8cdf55991f00591b726cc2974d34c9390749bccbe623304ea7d6decae45",
    "tests/deploy-history-get-node22.test.mjs": "687bb9986921de855908c2c828412e83d74ca63c906aae23cf4bf3abee35fb86",
    "tests/deploy-history-get-source.test.ts": "da376ebcd64edbbcb2ef2ba26ac4953e445167e28dcf79e440b9cac5706a1925",
    "tests/deploy-history-get-unit-plan.test.mjs": "9f86a4a534bea5f390d16b946015935090c8e1d6cfcfda9e92a03b5c9ead6857",
    "tests/deploy-start-get-node22.test.mjs": "4daa75860c998bf192ed9047b273e4dbda8b02833278a1e3b32f1a35d1a45324",
    "tests/deploy-start-get-source.test.ts": "af3a5712cce8229cebea2f45d962bb6b78c0fd0c327c29bac7cbcc9f448743f0",
    "tests/deploy-start-get-unit-plan.test.mjs": "11d26caf79c6e6a6ce7513a7472bec6d5442df86f2614f42bb17389a35e3d0bb",
    "tests/deploy-start-post-node22.test.mjs": "e064c701190e5a456b7651499ac49fe005e740f9506df016acc43665deab2eea",
    "tests/deploy-start-post-source.test.ts": "7815acec7dff6456440b18d775135088ae93e3830561075916b13fb42f3330d3",
    "tests/deploy-start-post-unit-plan.test.mjs": "fea6840905b0de193a83030715219144d88c78912e767f4387ba7496ab01251a",
    "tests/deploy-stop-node22.test.mjs": "0d46811b9f5a5b8af124893fcdaa3e51dae8df2c2e32210cbbec404fd1d53047",
    "tests/deploy-stop-source.test.ts": "0753ed4eb95ab0f0ed4978b675aa67082b03d8be3bfc35d0e805529789db2bfe",
    "tests/deploy-stop-unit-plan.test.mjs": "3457ff56b5f0703f38cb0e95d0250b09e3d360de0e97a7fd9dd428c764182550",
    "tests/deploy-stream-node22.test.mjs": "97a0ce3e5ba330564fe0ec2ce78e21f31a420bf82fdc79b08cb64723c67be179",
    "tests/deploy-stream-source.test.ts": "c0b62ec6abbfb32d793c72a3ce915b109659432c9fc12bdaecdec649b86b88c0",
    "tests/deploy-stream-unit-plan.test.mjs": "e5cdeec9eb7fecc7c7df1cf1a6101349bc93c05c81120d2163c01fa6f15265f0",
    "tests/deployment-action.test.ts": "092286657848a3a48145b13153d022f03cc33908d8105ff30d800dcac6160377",
    "tests/deployment-pods-node22.test.mjs": "0ad0a4289654ed79e7dd39f3571b3973ceeaebc4b733f1ed5a7970ebf8e9c295",
    "tests/deployment-pods-source.test.ts": "cd8cd8b9aba6010c6c12a3b70a48cc2203bf388ee9f72a56c1769a516b7266c5",
    "tests/deployment-pods-unit-plan.test.mjs": "b5b2c3a403f20e8abf5e117e4d0d2c25057d4bae40e2616058889778ace66880",
    "tests/deployment-state-rolling.test.ts": "d3d8e6663a3312595ac5f547c26d0cfdd6114f361becf0d1a551f5f94b6329d0",
    "tests/deployment-state-source.test.ts": "5fe287db3c2ce490f4511364c7634330919a06a2b1c3cb368451b72406207d9f",
    "tests/direct-account-cost.ts": "075379ec7920df2669a276bd37c2e078854fb6ddac6ead418484e6afdf38119a",
    "tests/direct-account-reader.test.ts": "fe8f3ccc5d69ef1e47c9f85529730c5c3bb78f409571ddcbb5541725a8558944",
    "tests/ensure-jwt-secret-node22.test.mjs": "9043a250b21cca62778650bd932f195ab6045b8b8ac585f7b3995a5b61219cca",
    "tests/ensure-jwt-secret-source.test.ts": "78a6feb55fffcd5bc0ec40a3cb3e179bd40d30178edb9dcb5fad1c554c0ef623",
    "tests/ensure-jwt-secret-unit-plan.test.mjs": "e2818516e6b16879985d7a6af62b8c526219d8d9cd10e42e748e1dbca7256f1c",
    "tests/fixtures/account-lock-participant.cjs": "fa1b0ed2aac52ee61407be2f5cfdbd547bf9a0724beb7c920873ca7e158e55a8",
    "tests/fixtures/account-lock.sensitivity.ts": "84da386e66745ecafd8eeb8d4e74f9c6f9e4ce31d3edd1b8541448c0dff8dfc5",
    "tests/fixtures/account-process.cjs": "6360b1d14fb0f708f889d471b8aec9a756f935adf4e69c91f3cb29ee34b22dc2",
    "tests/fixtures/direct-account-writer.cjs": "fbcdcf4fbc546e72ec8e9d77f0d8ee300b71def7ca7bd0cd5e69254a9d107d61",
    "tests/flux-credentials.test.ts": "e4fc1e2d066300a26ad60837f7747e1a8d903f868df76eec25c8e25d365fea87",
    "tests/flux-list-completeness.test.ts": "96f681d2614b4ab1eeee1abe0e56f49a2c8bef4ac95762478bd2e13fc16181f6",
    "tests/flux-zoom.browser.mjs": "c983ef3b86b6b82f251024bb262bad9926f969efe604222c24f5480c6bb98f43",
    "tests/flux.browser.mjs": "c7ef1ecbfc940914a302782d603aa7fcb5f9008dabfc44ca6a17dfd6d5d7673d",
    "tests/get-current-role-node22.test.mjs": "365d067db0ecdbe7c31bb82e84d6d4101c63f2862a04f7ea9b95a0772e654b80",
    "tests/get-current-role-source.test.ts": "41ab545f2a3cee61d0fa3f9ea1a3c1e2f0eed0d7fa885777c5127407865e66fb",
    "tests/get-current-role-unit-plan.test.mjs": "8b69be983776f371ec34bc90400ca482695557dcd42fb4d3dc2d594cb3efdf3c",
    "tests/get-operator-role-source.test.ts": "dfcc6bf78372a3ac407813bfd2f0f6e3aa5161862e455961d7f29446f5a47d94",
    "tests/get-session-account-from-headers-node22.test.mjs": "600c2c18ba3a5f7b1ef4cd28d638ed0e49a82e63dc68ed01110a6c462640c3f9",
    "tests/get-session-account-from-headers-source.test.ts": "a1bf65233e37237b792bc804c77dd27d2baef0875c0fa172e9b892b79d3e1db6",
    "tests/get-session-account-from-headers-unit-plan.test.mjs": "3dbba102b76543fac0b5bd8cb5bae2189c44b8dea852c08ac31117cc5fb999d3",
    "tests/get-session-account-node22.test.mjs": "143436eb149b844bc4133a8303a174b037f5f7cbe6cd0bbe1367f2c695030c29",
    "tests/get-session-account-source.test.ts": "9fda23b9802cbfb77e5acde63b3901cbf69f5ec496d09f0f14d421c8f81da901",
    "tests/get-session-account-unit-plan.test.mjs": "a668575ebd10cbb669eaa2019ad2ae3a39fdbf9744fb56b5781b01bc9bd4082e",
    "tests/get-session-from-headers-node22.test.mjs": "8a4ee8f2c2ee4ab48343ecc511b1e56142653c0cca07eafceb52f96ce3e4e364",
    "tests/get-session-from-headers-source.test.ts": "b05c1e4d38a738b53fadfc0fe7c761b0e33f9ca76011caea5c0d957ca9794ee0",
    "tests/get-session-from-headers-unit-plan.test.mjs": "6df3199ad1a4c83bd580bb51317688a605db2a566a31bbf81134ef6b006452a8",
    "tests/get-session-node22.test.mjs": "820f7a9a06643743e31ad628a9d01a7f36c58d6c2bc357ed931be3124997f548",
    "tests/get-session-source.test.ts": "4d2cb1295ccee7691ffd796cb2fae60c212907165a77e34e701c383573f2fb13",
    "tests/get-session-unit-plan.test.mjs": "f85b6a254f795708164848801f4eee3675cdc26801706e828caa0dd3a23c1afb",
    "tests/helpers/fake-ansible.ts": "526356c948fbb3553f74e836610b13b4f18d314f90ea7e39f21d3019fd26c6f1",
    "tests/helpers/fake-kubectl.ts": "1bc214f11df16d955598e1dc8e390528eaec2b9c34d81f33edd982580599bee4",
    "tests/helpers/idle-child.cjs": "39e790e91b2a48a420b215a7ed08da9165e6eaea0af06db980e3f21b9aeacae9",
    "tests/helpers/kv-administration-cleanup-fault.ts": "5157a8c34b061b9b6ff99dc214a6a022cfa25cae42aadb04ca1b9e0e84b3095b",
    "tests/helpers/kv-administration-fixture.ts": "d7ec8ce5e70fb1d0eb5dcb2e33a3c659110a00787144f1ab060a9fa4a283ce55",
    "tests/helpers/native-load-probe.cjs": "a670ff7b7ca605c74c27c41891b15edff628e74cdb9ab9dc33ba9897865b7bc6",
    "tests/helpers/native-tls.ts": "d00a12a8f25aa4a4d4d29ae220bd2f8264f6a4945f9bc939bd1c3cbfe69104f7",
    "tests/helpers/next-finalize-probe.ts": "d138ac3478053799d97325da419319d73289ea9466a8205822b070fa70a7284c",
    "tests/http.integration.ts": "160f9014d5f113ce34b7931650d8a92769503c5a496ee549c7a2353af988971d",
    "tests/is-operator-from-headers-source.test.ts": "fbaa1c37428bad94685cebb365df4994ca4f65af3b4b519005e6143d90760fa8",
    "tests/job-id-valid-source.test.ts": "338a222b5773549674b4619b71c1e9f111cb80fccbab682616084f407b698a7d",
    "tests/job-output.test.ts": "bd03f3984eb60addd6eaad6810a824a3dec66bfeffbe8818017454edf6e0d6ec",
    "tests/job-stream-unit-plan.test.mjs": "829585272b526c2997fedf8e96a3a336bce0d1ba03ef8cce4b299645b2b46738",
    "tests/job-stream.test.ts": "159895bb6de7fd4acb6f668adb4b8e5c6ec09745a62aab4c5caadbb3e017ce46",
    "tests/jwt-key.test.ts": "ec942eb2f1f057d1a3a3237e78a2a12e518f53d88714418623f8e6e23f4b5f33",
    "tests/kubectl-error-identity.test.ts": "c44c76b03e7652547f887f3d0f1d1836517ff8be4874b0a965fee028eba1729f",
    "tests/kubectl.test.ts": "42780a9e8aaaeed6083de4a8afceed39f4680cd709f9ed2a91ffd87a6b650d05",
    "tests/kv-admin-metadata-source.test.ts": "a15f14b18a84d2a40504fc70feb7a4e83948af0e326331c06fcc46bdc90ac5f0",
    "tests/kv-administration-cleanup-fault.ts": "6dfbda5a80b9db99d21f4b7365f90967254a1e4c97c03adc977357f1aaae85f0",
    "tests/kv-administration-ui-fixture.ts": "e6e784e22f5df7aef8c9861e07e717dfca092053ad74c9cbb0d607087a7d9b20",
    "tests/kv-administration.integration.ts": "dbad62082e87f3717fc84ca8cadd7e35c07b34501c0c162d96cc5ef0857953eb",
    "tests/kv-administration.test.ts": "55eb9595d12076002eb027af8dab86c4d806e4a1f3901a25a832384cdb198fe5",
    "tests/kv-adopt-route-source.test.ts": "4dd0cff7e7a910a3ff2907ec18c3329665a4d4d411e83f6b863adeb6b1c2dbca",
    "tests/kv-audit-route-source.test.ts": "ec963055e432d131cccd98c60ef28266fb2615a8246d8cac7aa215b1b0777309",
    "tests/kv-audit-withdrawal.test.ts": "49e93240ffdbeb8194826b56d0f6261146f766c22cbe7587df68567155ff401e",
    "tests/kv-authenticate-current.test.ts": "5a49af6b400efd0220c2a0b0cd16edb8b31f3e51a835a50f8bce1bacf2260826",
    "tests/kv-automation-dispatcher.test.ts": "6b47c5814b3086d1d6eb8ba50d30214ac4edf45ff598d7dcb561ff1cca741b5e",
    "tests/kv-automation-entry.test.ts": "8da103a729cb73dda75967a2b3d986089d838e37ce542568922cc50608144494",
    "tests/kv-automation-route-source.test.ts": "8f02dae166eee6438024fb67ff5eea2a73d4f2734b0c43d0bad7c40eecfd7426",
    "tests/kv-body-source.test.ts": "f7fc56fa34b3f960b75da593824da4f533c2e5c2c4140ea027954996bd952fe2",
    "tests/kv-capability-freshness.test.ts": "db28c0a0b5f4209209ef8ce8b73cffef0fe40f7c2ca22c1bf1b92f37817fb55c",
    "tests/kv-cleanup-status.test.ts": "b74e6d00b6fff9ea3749862e79b6e2524760e5658250a1b8424d1348c0947ad3",
    "tests/kv-config-source.test.ts": "29aa7a762abbe829fe5e2bee9753731928b9ced998e2b96d2a419d166a16fc0d",
    "tests/kv-create-route-source.test.ts": "f590f6ba82ae2d2307e94c6dbc8f0646d6c1d67d10412e4db2d6be19f320c362",
    "tests/kv-current-expiry.test.ts": "9109a492e507688704dfc4625363bf28b393d9bd6d5e868e7275908ca7d59b55",
    "tests/kv-current-value-delete-route-source.test.ts": "6ff01f6216f2d89625ce4b6a733cf696a3206343e4f1a107ffde8ee3d8453f62",
    "tests/kv-current-value-get-route-source.test.ts": "bea1517e6eaebc47e0ccf2ec2a96529d40327aba2a432247b269c8b764f5967a",
    "tests/kv-current-value-write-route-source.test.ts": "d69bf1c767ddba2c139e7ad541c92f05fc8fe3881264a8a65be7dcde7636efd6",
    "tests/kv-delete-mount-route-source.test.ts": "25619c28b1bb5c74acd2fcda8e10934f802114127b378e52ac3494c950beccfb",
    "tests/kv-destroy-route-source.test.ts": "ac5da9fbc951f4bcffcb21a9ac1cc646e1ce71d9298e97bb4becd0497f78799d",
    "tests/kv-empty-mappings.test.ts": "bc70ba0d1917fa8ee3ffdf8bb008f3a48d0234247f835d29094c007c2b136e21",
    "tests/kv-engine-source.test.ts": "372ba0fe32c03c4eb92e42da47f3b07df494fc6b40254aad3042923f9aa93d0e",
    "tests/kv-error-response-source.test.ts": "2023db9fc8be1e1972580debf261933bc9f936db84637413e53d2cbecdc0a2b5",
    "tests/kv-export-route-source.test.ts": "28d55f2de3a7f685af0386da312a11849cb735fe57312c4cdf6d7b75f052b92c",
    "tests/kv-field-mapping-source.test.ts": "be59aef8c54e17a63744ef41a24b5785e7801b496887b801d33b03a20f9fc97e",
    "tests/kv-foundation.test.ts": "517015e6301d4b3151a499cd35ecf5eb1471dbeef30102cb5c4e976e5b7452d6",
    "tests/kv-gc-routes-source.test.ts": "3d166d1a7a96e32f685efa7bef5a7bd242a7e574515512e6a653547947bb1cdc",
    "tests/kv-history-gc-preview-route-source.test.ts": "2a6468e72de5b9987263a26484c3e0883a9d6694ddc6bdfceb8237fe634d8695",
    "tests/kv-history-gc-route-source.test.ts": "fad69dd1903e62646a95316eecc4d9e4ff5d7b5188d9d3b4bf3df33c2b94e9a9",
    "tests/kv-history-route-source.test.ts": "0766a70886db15a1a612041849386825c4c0083e0612d2fc47caa891f356b73b",
    "tests/kv-http.integration.ts": "73051405274f000bdc931c8be8a57d7e55e4ba1a83b403d19238367a7e2c293d",
    "tests/kv-human-source.test.ts": "4610a110c93ad58a9609836b1c3b7964fb54381e7db8bb3d3c23023e19a4db2a",
    "tests/kv-identity-create-route-source.test.ts": "6d45fd0350c4ac98a430f01249fb1d7a16adaab0555f744e3848d01fb583c8a1",
    "tests/kv-identity-delete-cas.test.ts": "0ceec563cfeaa5f40c241f04b7177ed9e1d0cc51a29db6336f2036e62bc5f3f7",
    "tests/kv-identity-list-freshness.test.ts": "4f32df957f74d061aaf3008df8ebbd83c4c006f26ef1d88cb1cac2ef6ace3308",
    "tests/kv-identity-list-route-source.test.ts": "e6311bc754fc73971a2ea41f7f075c0948aef73f93495fae37d23a9d0b61792e",
    "tests/kv-identity-revoke-route-source.test.ts": "67d174a24225ee35f52bbb8c06fb476e53f10af7fee8785427623c9d52305382",
    "tests/kv-identity-withdrawal.test.ts": "99d4e9624191c12533bc35e4d136f11172f78b08cc83ff2e3a5c3389e3cc5eeb",
    "tests/kv-identity.browser.mjs": "b203434167cda1b634d2a04b0e5914f1c13f08ccb74ffb12aaa51eb6ce7c9441",
    "tests/kv-import-preview-route-source.test.ts": "5012947c0a4621ae322f19c3195616d3a3cf85c89ff126c40b1b7bb5a28b3986",
    "tests/kv-import-route-source.test.ts": "a0ed9d398cde670b21adef3499549ccb216a2f808f68b109f050ef0dcf8de3ed",
    "tests/kv-legacy-access.test.ts": "a373785fcd3663cc9a33476e6dec85b023a63b7362e9af971f941224755ab8c4",
    "tests/kv-legacy-grant-list-route-source.test.ts": "413caa4a83bc337197e67916bee6c1b481434e610b304050717df9a0b109f53c",
    "tests/kv-legacy-grant-revoke-route-source.test.ts": "793a75315243289ccc89835aa70c7228ca277374a7a4d819439412ee44776e74",
    "tests/kv-legacy-grant-route-source.test.ts": "bd3bc38e49198847622b765947560948a763249b3224bc05e4b8d7b25a62e722",
    "tests/kv-legacy-preview-route-source.test.ts": "0057d1137c4148f7be974e4c9201ca1072a9413ddf6a14b40a0d2a6cbdd36e46",
    "tests/kv-legacy-principal-get-route-source.test.ts": "d699ebc4ea60cb8aa49a0e287dd37aa1b03f427cac2b03bce3475b7a3133df58",
    "tests/kv-legacy-principal-patch-route-source.test.ts": "404cd6fa25e345e17ffed7f6e281630bb1ec159239d63d86eb136e997e292d56",
    "tests/kv-legacy-withdrawal.test.ts": "534d63fa880bd0a72bfca4112d747d43c7cfe87d5011756c35ba80fa4748db63",
    "tests/kv-list-route-source.test.ts": "d7904187ad310f207158740b3c6a95bd8bb4ac0f885b406e785aff4734832bdb",
    "tests/kv-logical-path-source.test.ts": "2943100e1d7b3554340df610bac78a408fe5277f551153407ca0dc913a162fdf",
    "tests/kv-metadata-announcements.test.ts": "69ba3ea1bfcbe4f81be378c8e32659cfdf0eed66060c18a62ae593a2a5c90c4d",
    "tests/kv-metadata-body.test.ts": "b12fa87d59993ff815383156489c8f1f7b5d957e2119582b2451541f3097b26d",
    "tests/kv-metadata-form-presentation.test.ts": "7840d80486cefc019efed69afa0fb298b3692d3095ea55ab08cb0ca8b62312e1",
    "tests/kv-metadata-freshness.test.ts": "92a2a50af77af35aa13d2592164e91695034b0eda3904be6d6c812d62c2bde62",
    "tests/kv-metadata-input-presentation.test.ts": "6aec4ef515cb0e847d890a9f8ef68dfc336363a872e950d5e83c817b2d135e58",
    "tests/kv-metadata-mapping-focus.test.ts": "83bcb807a54350e3e01a7847b058a450139cfbd577d8adf74c93606d322dc61d",
    "tests/kv-metadata-mapping-identity.test.ts": "2cf62ad7d9cd730604fcfbb1bff69785ba65fc86a9c270c797df35c35b68c5b6",
    "tests/kv-metadata-mapping.test.ts": "c8464a1e951efe2a6c8f80f52554bb4798b2970eeda07647ac6ee6d806e5a6b9",
    "tests/kv-metadata-query-source.test.ts": "3a8b707e72c8c2a0e1af265bb15260b8a56742a28fdd6af4afe746c8e79a2b06",
    "tests/kv-metadata-query.test.ts": "87b6ae3f1a68260006c270c7f9d5c78735867f4dc57cfc8547f1bafdbc6a7b17",
    "tests/kv-metadata-refresh.test.ts": "ee45cebf77423d2f2275306948b348f89d47f58366216e2fbf44075ff38436b1",
    "tests/kv-metadata-revision-source.test.ts": "861fa170db45e27f6555d2bf6595772fd3493433f1403618364bfe7df41058c0",
    "tests/kv-metadata-route-source.test.ts": "b22fc8380fcc9ecb2272d2b054eaf5e41f8e971e9f9d271bc219adb6e34c5df3",
    "tests/kv-metadata-success.test.ts": "6a8a0b5e106112cb2287b6658da0237f94ca6c9ad1dbb047a05ac62bd69c5288",
    "tests/kv-mount-edit-snapshot.test.ts": "fd405adfc4c6fce4e79c3f539a41c840318bd80ed383d6514b0aeb20f5291cea",
    "tests/kv-mount-list-freshness.test.ts": "ab3cd1c0e891223a5d99473e68499f3fe97e1d4be8b6d34d4cfe42913459b6c1",
    "tests/kv-mount-save-guidance.test.ts": "dd0a6ca2b260b447206efc03aa30fafe107aa98a574116715b339e9f61d76996",
    "tests/kv-native-request.test.ts": "ff9ab117260018282445c5d025ef52fd8a753927102c150d2162884fbb8df877",
    "tests/kv-native.test.ts": "917c12e4ab3a05cc0e88b09c58f0e3fb31f4a92e7601ba7e5e0358564497b482",
    "tests/kv-operation-route-source.test.ts": "5ae2af4d76dc64016cc52c13287a851c21fbcefce68ed28bb7f8d2ac693f4097",
    "tests/kv-parameter-source.test.ts": "f92ba3d91a4b45f2b8cfa2f7bedfc917e5b6a2fd9ed1434e330687318fb9bb22",
    "tests/kv-parse-actions-source.test.ts": "25c5d8312fecc0ac21a529bb44a772988c8a154ec3323cb0d0f4516b99e5a74a",
    "tests/kv-path-capabilities-route-source.test.ts": "2dbfaa90beda02567d688fb3f021f79674e58697bfe7f34b094fc5fcf459389b",
    "tests/kv-path-list-freshness.test.ts": "00cddbcd678052237cf24efb07fc3d86e52b6332fe37ff6b0569be912c7cab38",
    "tests/kv-path-status-route-source.test.ts": "629da54410026b64b90c6a7dabae0843f76f73c8c192614457c7d373458e216e",
    "tests/kv-policy-allows-source.test.ts": "8c03b92c5488d2646ab2107965767b0a8105a3636d2a712f30065764c33857f2",
    "tests/kv-policy-create-route-source.test.ts": "4cc03c74c13445ac3b293710f8b7ec68760c94df20fd4ffcaaf47986e73822db",
    "tests/kv-policy-delete-route-source.test.ts": "33a4e09a2086627a742c3c782251c7d008e4f8547d81b46bfa24f6085062a32a",
    "tests/kv-policy-list-freshness.test.ts": "615aed6927bdea63282d3b7fcbe147200657da9dbe47ef7669eadfc831d7d91f",
    "tests/kv-policy-list-route-source.test.ts": "9947277c8042a59720e58bd7fe02792a19c85fc40589ea9e4690fac1a2bbf1f1",
    "tests/kv-policy-preview-route-source.test.ts": "5f35001e1d8ed7692c650cd5721fb21e290f17f9238dfacf4b0c133f980a30a3",
    "tests/kv-policy-update-route-source.test.ts": "edb2206c43140ee925fc2e617c1e5649abe311956726d9bde22e24646556c63d",
    "tests/kv-policy-withdrawal.test.ts": "186821c103ab74dbacaeb6666d9a905bbfa9851f962d880552b68fb1cd5dc717",
    "tests/kv-prefix-matches-source.test.ts": "446015417745eb4bdf96f3220025679dee34d2c5aa79c1da7775164fb2a9232b",
    "tests/kv-reconcile-route-source.test.ts": "56d4f3fa5fe4ebf9bda8af4648643d3a883a225bec132febf74cb4a450f3a38e",
    "tests/kv-registration-mapping-guidance.test.ts": "fe230b86036f680889aa8a701a1d29ffd09b07e99076b90cd4c24cc32ec51786",
    "tests/kv-registration-name-guidance.test.ts": "3c816dd1b28b7865511831fd2960db7bee51a6dd259b78464b74a00fd8ce5fd4",
    "tests/kv-registration-namespace.test.ts": "6d475f73d13de3660bca3621d1a8fe8c8c941eab8867af34159e651e3fcc9b99",
    "tests/kv-registration-path-guidance.test.ts": "131fcbdcfd3367b30fd483f1a52ae433f7693ad997abda8d882e38380145cd5f",
    "tests/kv-registration-retention-guidance.test.ts": "25be2bda779879ba4d982d1da4ed23fa033e07b92039e8d14ff665aa2d3b8b8f",
    "tests/kv-registration-snapshot.test.ts": "c57092583397810fa5364cbb8dc0750d90e2d6cac5ebf395fbce03819b2dee28",
    "tests/kv-registry-source.test.ts": "bd04d7004422aa9f972ddbbf6238a9c86af3cba31e68a3982b83b4e1e82e8661",
    "tests/kv-require-guarded-source.test.ts": "4197d98b525d3ca6fb78f0f007dc3f039609e6d77160375c6c15d01b767c8a11",
    "tests/kv-retention-editability.test.ts": "ff529faaacc369199c901612fa226d9a19ac06373136f561b0d6b8f54fa2f163",
    "tests/kv-retention-presentation.test.ts": "a58251cae8aecab19568bf36a781560f3823c60a5cd0f26fe39225473dbe40ed",
    "tests/kv-retention-save-guidance.test.ts": "5bbea93fd8a6f3dc39ab24566d59f33e65f26797fbb3eb154758012ead387d03",
    "tests/kv-retention-snapshot-guidance.test.ts": "5b63d09fdf341e5516ed485fac184415503d960ec20248397c92063c28aa4ddf",
    "tests/kv-retention-withdrawal.test.ts": "4f2e44062813a52b5f2387349a47e0561e922fdeec6cfc35f30100dfbeffb14d",
    "tests/kv-rollback-route-source.test.ts": "76c2e63192d4c247d35aa4c864d1e0a66cf4d89f2934fd0397d8f04e58223a89",
    "tests/kv-rotation-action-route-source.test.ts": "fe2d9da6bcddb4dae09996b5a1fe0741d3fcab0b5c89db614986492391c3f34e",
    "tests/kv-rotation-consumer-preview-route-source.test.ts": "e0097645645eda2ca4c1790697207df8c5e66079b978565505d7f01ec66687c1",
    "tests/kv-rotation-consumer-reload-route-source.test.ts": "d6c04abef45af9b87ede30994a01849d88c9e2de0d11a874b979fc8c03029d4a",
    "tests/kv-rotation-consumer.test.ts": "26a081079951c63c61681a856f5820e509798fc5ca395dc9cac4dc35c8d09ead",
    "tests/kv-rotation-declaration-withdrawal.test.ts": "eed4ca17ab019bef226eac24b4cfb4fc50fdf32d4418013b9d2b07a44e2ed930",
    "tests/kv-rotation-list-route-source.test.ts": "cde110da64801c6b7d19e2f26bd708cf1a85970c380fd85f6b8c2837334884e8",
    "tests/kv-rotation-prepare-route-source.test.ts": "1027f83bbe6c7eabc2a3d8aba594c4a3280b8ff98f6050a4dc648a09f9627a2e",
    "tests/kv-selected-path-account-identity-snapshot.test.ts": "a2d010298091a4001f25a9e34ad0c879799c1fe7a05ea6543d449640d84d238f",
    "tests/kv-selected-path-capabilities.test.ts": "6c288e2c995818fa842756cbbc6b961b6006201482c6958a7452e6b746a9dca8",
    "tests/kv-selected-path-freshness.test.ts": "f5a0f164b0af35572c3196c95a12c3f849a5ba548d00ef9fe49c755cb45e435d",
    "tests/kv-selected-path-owner-policy.test.ts": "aeffb4e0018099f253c5a7966224c48b6047e8ab563041b02f53f52d947a42d2",
    "tests/kv-selected-path-policy-snapshot.test.ts": "9f27a6a4aa86636a0da68c96d39478ff4c6934659fd51ab5449dd33ec7f4e25a",
    "tests/kv-selected-path-presentation.test.ts": "19c958f12c63ccc4a5de4feb2077576dff4b456e71a65ba91694f002635cbec4",
    "tests/kv-selected-path-sql-transport.integration.ts": "5e475f1e63d50bc324563ead10e6bd4b914b7a97bc1dd97dbd9079b0482d4a5a",
    "tests/kv-update-route-source.test.ts": "174f19ac63ec93ac7e5f0447540f20dc3bc6b2d2f21e10312aa828ed0495a41d",
    "tests/kv-workbench-browser-entry.tsx": "685157c6300578bbdc05a2e3c7ebbe3aac87a58cbab89498bc29556aad0c8c47",
    "tests/kv-workbench.browser.mjs": "015dfae87926115f16a661346bcd9ab28c2febf83bfb8efeb407741472332b0d",
    "tests/kv-workbench.test.ts": "83d7af8cbae1dd8253f41e24c0fb83f7065efe5994b5f761e1abcdaf14963b20",
    "tests/kv-workflows.browser.mjs": "3cc36f81d1ceb4114a95f4c24ca347d644029236dd6b65ac41931d68e23f36f2",
    "tests/label-predicate-source.test.ts": "1d8e56c15cf6282bd2aa4c631819e702773b0a1cbebff0bc217d5332f1ef9441",
    "tests/legacy-cluster-sort.test.ts": "fd59aa05d84bcbcd98187b8ba8aed823cc48fa24de0f6bf40b632fdafabad90a",
    "tests/legacy-node-permissions.test.ts": "bb9d9c9c27b4a8b365580022c683c390ca9e76767b221a33ae2c2c909346de9f",
    "tests/login-submit.test.ts": "5dd0bb56f370a3630763352c2689e33ed1169f2015d6fb7f1ff7618578fbcef3",
    "tests/measure-bundles.ts": "fd17fe9da8498ff24c20df1280e6a392ab6a462162ed4e838210ebe7b1fa36c9",
    "tests/metadata-bounds.test.ts": "67715389152f47c6acc2ae26c51031ad1739e2ddfdee7f2f4c9a6b67ee65cf5d",
    "tests/metadata-query.test.ts": "644c4e7c2cd0255c6bee4675c0f36ef09b0442af1c7bba11c9c406e58d40eb08",
    "tests/mutation-task.test.ts": "6a02430fce00e78476a2e93875cef2c99a0626b3e7b81dab9093e8d12bf093a2",
    "tests/native-ascii-span.test.ts": "d9f17831fa7788618e831fd023c301dd6d66b672379e55a6e15a4c3374a58f34",
    "tests/native-auth-snapshot.test.ts": "d373f81de92db371e5485e9da00f0e884e3cec36847cf02c0309ef5700ccaa9d",
    "tests/native-flat-compiled.integration.ts": "84a8c626867e97b8aa7866244aa0375e19074c6d0fbcdcfc7fbcaba8a2b67270",
    "tests/native-flat-page-limit.test.ts": "226fb724683d5b7439e9863d580aebfdfbc83d13d02c41ab890c41c0cb70918f",
    "tests/native-list-concurrency.test.ts": "3cd8b4388f459fddb7e423304cff329145e34c32058d78aa7725f7414819e915",
    "tests/native-list-prefix.test.ts": "d163150666926cd60fad3bf461fd030d98a0a47c02031a2f809b51d3ecbe54b9",
    "tests/native-list-window.test.ts": "e83a21f5cc4f4ea47a61b99dc4b1aac0683e7bdfd7bb73086ff639d25644b3e9",
    "tests/native-secrets.test.ts": "e1a8ab4658af10ed19547a51363ed0d396fc59c8a7ed61ab1000ff40e5c8aea1",
    "tests/native-summary-fields.test.ts": "24d6b2536455c3b0ff0aaa32e4ac21b2584282997dbc9d1570ab17e1aa8dffaa",
    "tests/native-summary-json.test.ts": "dca132b31f8628a1e4df8bf68dc0853f3ec14a1cd7f0ca8a4e0fe11f28f49927",
    "tests/next-body-finalize.test.ts": "19928d75d7fce66d5765577d3e14287c0037c8cf9e02be83362da8b7106f6971",
    "tests/observe-ansible-process-source.test.ts": "bb2012be6a4f89559dcc0a188b7cf4a818a81212d4164a93f7e2363a1eb44376",
    "tests/operator-command.test.ts": "deb0fc99b009e79de0c6fa8c5d3ef5141cf6d48881109c1e5731adb94d4429a1",
    "tests/operator-process.integration.ts": "6d819a0b9106265a909ebcf26dd06ae6d699722844b0f4994df7a90ae455867d",
    "tests/optional-code.browser.mjs": "5be30eb4406ad9b350d8764db9de9a5fdcdb02d70066e48612d933da9ed79c16",
    "tests/pod-coalesced-demand.test.ts": "5093920d09287a238eccd7d65f397b9bb2426094a7eef413050d5d5114bbee94",
    "tests/pod-copy-views.test.ts": "7ce38f717a3f430eb95b14967f78605368f4cb78e77f4f398e4be6bd84665c0d",
    "tests/pod-demand-body.test.ts": "6cc4bb0b1bb19943708373742a785e5718d0e8282a63e0291171f953d9662296",
    "tests/pod-filter-source.test.ts": "b4d89c2f914f1451580452fef494bdf5e781dd1ad55645e073869d7e432e3e4f",
    "tests/pod-list-capacity.test.ts": "7dfbd9be65859ebdd37b1bde6771b67ff92472d820f619229898b0ce99bc6b12",
    "tests/pod-metadata-response.test.ts": "1c6ed44e63d130437dc543c4dbed8b88e051aa12499c9419ae1b26c746949eb3",
    "tests/pod-prefix-retention.test.ts": "25a958afd19f08b57350b2a8b1446c5e88c1d23f4b152c13a90c72f1d72d611d",
    "tests/pod-restarts-source.test.ts": "83a0f89f669c77b1484358b66eb31570950f03a66911029a770a3d4bab89540a",
    "tests/pod-small-demand.test.ts": "afc187e76ddd546924804702326bffdc9ce5786c24893bdec670bfe1dbc33450",
    "tests/pod-summary-source.test.ts": "cbdfccc010d355c94572fc9b32bb036acd8d5ccbc9ce58508d7005d432a09641",
    "tests/prisma-config.test.ts": "c2cc39cc566ecf639caf983cfb34002d1c01f2c009d10a5f1f36448dd7fb59f7",
    "tests/provisioning-output-cursor.test.ts": "653dab3c7f60b416d3a7bf03e9b2397bd36ba999d0500848db8a9a6ca4670501",
    "tests/qualify-ansible-callback.py": "682f3c4906b804b9f4410410e58ff35e895f0fbf16633199b3a7759a51837ca5",
    "tests/qualify-secret-capacity.ts": "72ea1efd96027d567610b008536920566b5fe387e45b1d1d9e2d68ff129e9aea",
    "tests/query-freshness.test.ts": "b724dfabd4f086238e146549aebd222fea8963f18dfe580a7b0f3c69f18b3866",
    "tests/query-owner-notification.test.ts": "a4b9c9535bada78d2a54b6a28c08d31d645712b271b83effce6a8177890e35d2",
    "tests/query-store.test.ts": "ca257224ce61d5d979081aab02309338534ae1d315da445f530d8c773fe0b5cf",
    "tests/read-job-slice-source.test.ts": "fe2dc6b1d61db7bd077501cb9e99d3dba02645ef401067f2d40b954fdb065cfb",
    "tests/read-job-tail-source.test.ts": "a400345f4f2368896e41fd31547115e72b9e1c38062eb58f8b5ca8da1b0b6da4",
    "tests/registration-availability.test.ts": "4a92818ff0c1215a31d01e0a23368517e639601d88123fb290ba775858bd9ab3",
    "tests/registration-open-source.test.ts": "ae3937e6c8f7572e8a019b8b8fad22a7781c2c1e54c1ae6b3a06a3b1f25162ef",
    "tests/request-json-denial-order.test.ts": "5052aee93585cf5387dfabf3fa6598e7f7bbc1dc1dd56bedcb6b459a6693cd70",
    "tests/request-json-response.test.ts": "20e4d736eea3d3ea37b42fe533752a77f0a451c0c7d695ae876910fc5ab02dc8",
    "tests/require-access-source.test.ts": "73c3ca806eac05d1c85fd16f2315adaaf1421ee9aa4a60f687a9ce3249a4de6f",
    "tests/require-operator-source.test.ts": "1f574f1b22dfcd919c381fd1fe18bb5235f13c6ba1c456e143a001eafd534c4b",
    "tests/require-write-source.test.ts": "d16a3ada69bcbea8635cca88d9f21b74d9c6b50f1ddf124efe43e2769e99ecc8",
    "tests/resource-base-source.test.ts": "83c0ec033db879cfd323769c8d84023734044dc640e45e2ed3222ecfb21335a4",
    "tests/resource-cache.test.ts": "f902727351220a707f482e66750ce864f3316d95d89b347b1995c6c6be2b4de8",
    "tests/resource-capabilities.test.ts": "7c2b2ef737b10b10902dd99a7a8f52b907293097b321b2b87e611b1a9a3a4de9",
    "tests/resource-private-state.test.ts": "9bf13ea7bcd68aa572cd639cc27ddce123f92acdb151ef9a89262251cc4a9291",
    "tests/resource-snapshot.test.ts": "9df7b088164b3c9fba4075c486ed59b17f4e28c16141086db7a4ffa1a952c824",
    "tests/resource-state.test.ts": "d726354abef5c08210aa8dd311691e24a4b29f1efa9aa895d8997b505050b68c",
    "tests/runtime-capabilities-source.test.ts": "879b4f7f82bf1c5b820c9245ec85508c8a4a6394a58f8ea4ef1aa1ffed781253",
    "tests/secret-capacity.test.ts": "e9b64b210969cea115d9ff3440aaa6364c601e069be9d3b6522ba21ad6f50a85",
    "tests/secret-flat-page-limit.test.ts": "4235ddb16861022f993f7d9620869560362a96382d8c2e57570c2ef07eff64a3",
    "tests/secret-flat-summary.test.ts": "c74aef3eadce175d03a6e944f0f82f89279ee5ffaf1b7fbd71a2df60c2832a40",
    "tests/settings-mutation-lifecycle.test.ts": "4808d5b1b2ae1b198bf65e6f60cca6ef6acab6e5cc6a3707a705e9ec726922e4",
    "tests/shared-freshness.browser.mjs": "ef6b4fbad5e922cf477afdeffde9c0fede278d05c1e04c8aa1a12a7d8a9fbdc4",
    "tests/shared-metadata-query-source.test.ts": "7f676dd2020191dc9b95e92dae0688257ea3c49154c1c3d5ac08e04d5edbfc3c",
    "tests/sign-jwt-source.test.ts": "b4ddbf6140908fe34fd967350334e0a36bef7dfa86abbd55ef7a6d38c6e5792d",
    "tests/support/node22-source-harness.mjs": "42dc6445ea0fb3f27c76fef3194fe2d1caf949d1030ac5cdf1b131b3ceb72cea",
    "tests/terminal.browser.mjs": "b7fcfa82840c4457df875089b3342ee21cb58ca32d4a3e103b11954e9177ef60",
    "tests/transport.test.ts": "c747ca2cff7ea1992fb498da88e36501221c63278b6c4a03a60a5d6fc9af7c12",
    "tests/ui-fixture.ts": "cfe0385d8ec14e09162dbecb95ee8a654fc2cd1595a6aa85c3d35a0ccd2fc022",
    "tests/unit-test-loader.test.ts": "131a957bff2ffd4fb7573a38648b71fab0948cd87df6430da0548d32c2f47536",
    "tests/unit-test-plan.test.mjs": "f97b128d6d0b9354a503dfd33bb89d44e71bffe649793df64477c9555564cf95",
    "tests/verify-jwt-source.test.ts": "c0b259937cc338b4bb312df039f7c76d0216a94238390a47add2adc347f8d67a",
    "tests/welcome-navigation.test.ts": "d4da2e926a62bc3c1c224fe7b98d6f8e0ef35ce476abb3a034bebfdff31f7fe5",
    "tests/wide-zoom.browser.mjs": "a64d6cea6cd60c193983087b69139a5c5f78ffb2c64ede1e0e11bd5321f7c514",
    "tests/workbench-lifecycle.browser.mjs": "504cdfaaa3daf716b10fb30678c64590c5168dddbc13029cd0e81e0bea9dcbb5",
    "tests/worker-account-probe.cjs": "ee08ea1290d5d9aa9ce137398e081b73386c19ddeed63214b31801ebd1a23c91",
    "tests/worker-account-reader.test.ts": "2ebf5aa1fdad91cad92ffc63596121b7c281a84c997c1138397dcfcd192bd168",
    "tests/yaml-save-lifecycle.test.ts": "94e8f570f728292bfcfb57fac2f849f48222ecfeddb34292ceb2748359fbbed0",
    "tsconfig.json": "1a9aeca0dd2e384e0d3341044fab297e730f40ea985c45d3101ec5316e142570",
    "scripts/kv-audit-route-unit-plan.mjs": "09609f576a8c02d2e128eb2889ff78fc1380e893a7b4c8b49cd8fe17a3017c4e",
    "tests/kv-audit-route-node22.test.mjs": "edf87c9baa52c309f87d413ae132e626cb3f6ccff2d414ac16bd71f211da3676",
    "tests/kv-audit-route-unit-plan.test.mjs": "eeedfecd6f43e6a33079af2accb1dee5315e4d7c33034438bd0bf90cc9500dae"
};
  for (const [name, hash] of Object.entries(frozen)) assert.equal(digest(read(name)), hash, name);
});
test('M16 complete201line historical input and missing explicit compiler binding remain frozen', () => {
  assert.equal(digest(original),row.sha256);
  assert.equal(digest(original.replaceAll('\n','\r\n')),'730f0a65efaa1405aa1db2b7e0b5fcd776e4ff243a503d0a0942a98a388f4fed');
  assert.equal(original.split('\n').length-1,201);
  assert.ok(original.includes('require(process.env.BORTUS_SOURCE_TYPESCRIPT!)'));
  assert.equal(original.includes('assert.ok(process.env.BORTUS_SOURCE_TYPESCRIPT'),false);
  assert.equal(original.includes('process.version'),false);
});
test('M17 exact10line source selects only exported async one parameter POST declaration', () => {
  assert.equal(process.version,'v22.23.3');assert.equal(ts.version,'5.9.3');assert.equal(ast.parseDiagnostics.length,0);
  assert.equal(source.split('\n').length-1,10);
  assert.equal(digest(source),'7e8d91cbc6f27704ea76b1929043ea540024e4552a90a871788ca1c091a81fff');
  assert.equal(digest(source.replaceAll('\n','\r\n')),'372f5762b6fd7a9191691bdf0edccaa677c258683d9cdf9bb76d3a2b33f7d504');
  assert.ok(ts.isFunctionDeclaration(fn));assert.deepEqual(fn.parameters.map(n=>n.getText(ast)),['request: Request']);
  assert.deepEqual(fn.modifiers.map(n=>n.kind),[ts.SyntaxKind.ExportKeyword,ts.SyntaxKind.AsyncKeyword]);
  assert.equal(digest(fn.getText(ast)),'efd927b989fdf7589b949dfa663935adf8af3ffd13affa26ba5bf3f6bab48e2f');
  assert.equal(digest(fn.getText(ast).replaceAll('\n','\r\n')),'852fa407addcbcc82f82f5560718626a9ec5e791a401e7103f0a68733fb4772f');
});
const historicalTail=original.slice(original.indexOf('type Call ='));
const currentTail=projected.slice(projected.indexOf('const names =')).replace(/assert.equal\(count, 1\);\n$/,'');
test('M18 ALL162 helpers callbacks assertions and order equal after erasure and bare rename only', () => {
  assert.equal(normalize(currentTail),normalize(historicalTail));assert.ok(projected.endsWith('assert.equal(count, 1);\n'));
});
test('M19 original strict selectable binding new Function harness is exact', () => {
  const old=parse(original).statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='select');
  const tree=parse(projected),current=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='select');
  assert.equal(normalize(current.getText(tree)),normalize(old.getText()));
  assert.ok(current.getText(tree).includes('new Function(...names, \'"use strict";\\n\' + js'));
  assert.ok(current.getText(tree).includes('default:throw Error(\'unknown binding\')'));
});
test('M20 all full member expressions and t.test registrations retain spelling and order', () => {
  const members=text=>{const a=parse(normalize(text)),out=[];const visit=n=>{if(ts.isPropertyAccessExpression(n))out.push(n.getText(a));ts.forEachChild(n,visit);};visit(a);return out;};
  assert.deepEqual(members(currentTail),members(historicalTail));assert.equal(projected.includes('t.control'),false);
  const registrations=text=>{const a=parse(text),out=[];const visit=n=>{if(ts.isCallExpression(n)&&ts.isPropertyAccessExpression(n.expression)&&n.expression.expression.getText(a)==='t')out.push(n.expression.name.text);ts.forEachChild(n,visit);};visit(a);return out;};
  assert.deepEqual(registrations(currentTail),registrations(historicalTail));assert.equal(registrations(currentTail).length,15);
});
test('M21 original AST selection and exact selected executable compiler options remain', () => {
  const a=original.slice(original.indexOf('const source ='),original.indexOf('const js ='));
  const b=projected.slice(projected.indexOf('const source ='),projected.indexOf("assert.equal(process.version,"));assert.equal(normalize(b),normalize(a));
  const declaration=text=>{const a=parse(text);return a.statements.filter(n=>n.declarationList).flatMap(n=>n.declarationList.declarations).find(n=>n.name.getText(a)==='js').getText(a);};
  assert.equal(normalize('const '+declaration(projected)+';'),normalize('const '+declaration(original)+';'));
  for(const text of ['import("../src','require("../src','process.env.BORTUS_SOURCE_TYPESCRIPT','node:child_process'])assert.equal(projected.includes(text),false,text);
});
test('M22 all opaque adoption refusal capture interleaving and reentrancy authorities preserved', () => {
  for(const text of ['exact receivers arguments and opaque','adoption and await fence','caught once','catches exact identity and stops suffix','distinguishes return from await','preserves argument evaluation and refusal','property lookup and receiver','exact receiver and refusal suffix','catches after method capture','captured before','engine precedes fresh body and schema selection','body pending retains original engine actor and captured callees','fresh selection and repeated calls never reuse registry or actor','reentrancy keeps call-local bindings']){assert.ok(original.includes(text),text);assert.ok(projected.includes(text),text);}
});
test('M23 only new mapped original leaves prior exact selected order otherwise intact', () => {
  assert.deepEqual(prior.selected.filter(n=>n!==row.original),plan.selected);assert.equal(plan.replacements.filter(r=>r.original===row.original).length,1);assert.equal(plan.selected.some(n=>n.startsWith('--')),false);
});
test('M24 packaging metadata and actual SQL reader remain selected but unevaluated', () => {
  assert.equal(sessionReplacement.metadataControls,1);assert.ok(plan.selected.includes(sessionReplacement.metadata));
  assert.ok(plan.selected.includes('tests/worker-account-reader.test.ts'));assert.ok(plan.retainedUnmapped.includes('tests/worker-account-reader.test.ts'));
});
test('M25 authentication then captured response and automation retain engine body and return semantics', () => {
  assert.equal(fn.body.statements.length,1);const block=fn.body.statements[0];assert.ok(ts.isTryStatement(block));const statements=block.tryBlock.statements;assert.equal(statements.length,2);
  const ds=statements[0].declarationList.declarations;assert.equal(ds.length,2);assert.equal(ds[0].getText(ast),'registry = kvRegistry()');assert.equal(ds[1].getText(ast),'actor = await registry.authenticateIdentity(request.headers.get("authorization"))');
  const ret=statements[1];assert.ok(ts.isReturnStatement(ret));assert.equal(ret.expression.expression.getText(ast),'secretResponse');assert.equal(ret.expression.arguments.length,1);
  const awaited=ret.expression.arguments[0];assert.ok(ts.isAwaitExpression(awaited));const run=awaited.expression;assert.equal(run.expression.getText(ast),'runAutomation');
  assert.deepEqual(run.arguments.map(n=>n.getText(ast)),['kvEngine(registry)','actor','await kvBody(request, automationRequest)']);assert.equal(block.catchClause.getText(ast),'catch (error) { return kvErrorResponse(error); }');
});
test('M26 ordinary new child preserves exact batches around both prior VM children', () => {
  const a='tests/get-session-account-node22.test.mjs',b='tests/get-session-node22.test.mjs';
  for(const files of [[],[row.current],[row.current,'a',a,'b',b],['a',a,row.current,'b',b],['a',a,'b',b,row.current]]){
    assert.deepEqual(executionBatches(files),priorBatches(files));assert.deepEqual(executionBatches(files).flatMap(batch=>batch.files),files);
    for(const file of files)assert.deepEqual(executionBatches(files).find(batch=>batch.files.includes(file)).flags,[a,b].includes(file)?['--experimental-vm-modules']:[]);
  }
});
