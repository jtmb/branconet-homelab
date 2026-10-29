import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { currentPackagingAggregateCompatibility as fixed } from '../scripts/current-packaging-aggregate-compatibility-manifest.mjs';
import { bindCurrentPackagingAggregateCompatibility } from '../scripts/current-packaging-aggregate-compatibility-provenance.mjs';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const fixedCommit = '11c8ad9d7a7d1fd03d4c97a59e6ebafbe635d306';
const prefix = 'k8s-rewrite/front-end/';
const gitDir = process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
assert.ok(gitDir, 'Explicit readonly PUBLIC Git object authority required');
const git = (args, input) => {
  const result = spawnSync('git', ['-c', 'safe.directory=' + gitDir, '--git-dir=' + gitDir, ...args], { input, maxBuffer: 64 * 1024 * 1024 });
  assert.equal(result.status, 0, 'Unable to read actual PUBLIC Git objects');
  return result.stdout;
};
const inventory = git(['ls-tree', '-r', '-z', fixedCommit, '--', prefix]).toString().split('\0').filter(Boolean).map(line => {
  const [meta, path] = line.split('\t'); const [mode, kind, blob] = meta.split(' ');
  assert.equal(kind, 'blob'); return { path: path.slice(prefix.length), mode, blob };
});
const batch = git(['cat-file', '--batch'], inventory.map(row => row.blob).join('\n') + '\n');
let offset = 0;
const actual = new Map(inventory.map(row => {
  const end = batch.indexOf(10, offset); const [blob, kind, size] = batch.subarray(offset, end).toString().split(' ');
  assert.equal(blob, row.blob); assert.equal(kind, 'blob'); offset = end + 1;
  const bytes = Buffer.from(batch.subarray(offset, offset + Number(size)));
  offset += Number(size); assert.equal(batch[offset++], 10); return [row.path, { ...row, bytes }];
}));
assert.equal(offset, batch.length);
const snapshot = () => ({ publicCommit: fixedCommit, representation: 'gitRaw', entries: inventory.map(({ path, mode }) => ({ path, mode, bytes: Buffer.from(actual.get(path).bytes) })) });
const original = actual.get('tests/aggregate-unit-compatibility.test.mjs').bytes.toString();
const callbackLabel = "test('all59 frozen functional projections and complete prior planner/runner raw hashes stay exact',()=>{";
const callbackStart = original.indexOf(callbackLabel);
assert.ok(callbackStart >= 0);
const following = original.indexOf('\ntest(', callbackStart + 1);
const callbackEnd = following < 0 ? original.length : following;
const callback = original.slice(callbackStart, callbackEnd);
const frozenInfo = text => {
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  const ast = ts.createSourceFile('literal.mjs', text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const found = [];
  const visit = node => {
    if (ts.isVariableStatement(node)) {
      const selected = node.declarationList.declarations.filter(d => d.name.getText(ast) === 'frozen');
      if (selected.length) { assert.equal(selected.length, 1); assert.equal(node.declarationList.declarations.length, 1); found.push({ statement: node, declaration: selected[0] }); }
    }
    ts.forEachChild(node, visit);
  };
  visit(ast); assert.equal(found.length, 1);
  const { statement, declaration } = found[0];
  assert.ok(ts.isObjectLiteralExpression(declaration.initializer));
  return { declaration: statement.getText(ast), literal: declaration.initializer.getText(ast), start: statement.getStart(ast), end: statement.end };
};
const originalFrozen = frozenInfo(original);
const frozenDeclaration = originalFrozen.declaration;
const mapLiteral = originalFrozen.literal;
const historical = () => JSON.parse(mapLiteral);
assert.equal(process.versions.node, '22.23.3');
assert.equal(createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT).version, '5.9.3');

// Only exact inert frozen declaration and selected callback projection below; all other initializers and neighbours remain inert.
test('C01 fixed-current projection of exact aggregate compatibility raw packaging callback', () => {
const frozen={
  "scripts/account-store-unit-plan.mjs": "cffab0ea41dd0073907bc073b0269b84fae9ad0122ee46b47f218971661941e3",
  "scripts/ansible-selection-unit-plan.mjs": "78b27e551a3f776763395fbff7b26a055dbf811d427c6af84706acd956839b39",
  "scripts/auth-logout-unit-plan.mjs": "acb6753b126b2f427afb44f42ce6339fc0569044d1e6ebac4c78ad6d88188217",
  "scripts/auth-register-unit-plan.mjs": "dd17a0d508c2486b9d305db110e553f0037a7dcc38208dba9b63241d01e8c794",
  "scripts/auth-session-unit-plan.mjs": "c44098a39572f0fd4655e4556bb85076b058005e8755f5575709dff81d8b8c25",
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
  "scripts/job-id-valid-unit-plan.mjs": "e2f3a8f366aec8b9df5d6c0d94ebf75e96e9a2e1c8ca29c9b81f92a11326bd46",
  "scripts/job-stream-unit-plan.mjs": "e70697ab45a452ef0b9a5d5a77d08852c3fb491e8bb46f30881d2dd50a710184",
  "scripts/kv-audit-route-unit-plan.mjs": "09609f576a8c02d2e128eb2889ff78fc1380e893a7b4c8b49cd8fe17a3017c4e",
  "scripts/kv-automation-route-unit-plan.mjs": "2c2412d35d1160ea1ce89df923bd66c23d5202b62e359467151f8edd7c103456",
  "scripts/kv-config-unit-plan.mjs": "48df76612b49b335a54da989933a339dfd2169eecd4b55102bb50fcded837bb5",
  "scripts/kv-engine-unit-plan.mjs": "c27fa8a34fa4fe28aa08987018d90ba94ed02f66986c5f62dda7e973f6d9b24c",
  "scripts/kv-error-response-unit-plan.mjs": "a864afd8bb4ff24251de4a15931d8f9c98c45608acc702a5a4dbe584ac0a9f59",
  "scripts/kv-field-mapping-unit-plan.mjs": "98c31429cbaf103bff4e843187bbb163eaca1c24db9356cb02b3e865e8e64801",
  "scripts/kv-history-gc-preview-unit-plan.mjs": "ebc616438681be7e37a8cf950bda2e29f267d415525e3b6440e9839491e3f2e5",
  "scripts/kv-history-gc-unit-plan.mjs": "e821c2b5282b144e4fd60d5ad97677110cc8bed0fb42e2e057fe548445af8d6f",
  "scripts/kv-metadata-query-unit-plan.mjs": "23e12d2fb99d22d92b792c0d2c1c9dba0a1998b0563d2164e72bb5ed6ad19124",
  "scripts/kv-parse-actions-unit-plan.mjs": "f7085b693ebb562c7b2c6e533f4bb28c0ffd53b6e851f473dde740c9f9c9950e",
  "scripts/kv-policy-allows-unit-plan.mjs": "d7b8d1a838e28dff4c75c9821ac4a62f72d8ee09edc80a1550c642d7a357b153",
  "scripts/kv-policy-preview-unit-plan.mjs": "45774d348d2fd31d655d691f6ed445ba6013a89dc447704408f64460bda61abf",
  "scripts/kv-registry-unit-plan.mjs": "774cc0653afcfe17eab9d124a9da36bd955cb6026db50e9015f5407e467d9395",
  "scripts/kv-require-guarded-unit-plan.mjs": "bf619b9684bfb9e0cc629c7008f12ac655b854226108b83a7ad1e14f07f48e76",
  "scripts/observe-ansible-process-unit-plan.mjs": "b3acbb6899094564f9e29b8c7531553e928f510aee75bcb908923067b703f58a",
  "scripts/read-job-slice-unit-plan.mjs": "7151dbd883741ad1eb67df3847f375740afdd2d13fcd914e461dbc8840dc4874",
  "scripts/read-job-tail-unit-plan.mjs": "24692079da91bc2d872269d57f898e7355657153238169415c12b3553fe662f7",
  "scripts/require-access-unit-plan.mjs": "8f903b7257cf6f823a8bb92a2bfa44606cb32aab62804f9dad09575204974b76",
  "scripts/require-operator-unit-plan.mjs": "161ff24b74452e20ca3682081599b74aaba809b1d75947855e9e70f0a125bb6f",
  "scripts/require-write-unit-plan.mjs": "820db66b7eb1a4bccc94bf38f20e1961b1dab6608cb9d2f117cd17e46d1680b3",
  "scripts/resource-base-unit-plan.mjs": "faab8458d4d2d50721d42d5378ef1fb94afc80b3bad7c500bde8f8a9697fbf4e",
  "scripts/resource-cache-unit-plan.mjs": "ddc9748128415eed437f494229a5c9e9c869552e0a17b9490d8af3767d3fc24f",
  "scripts/resource-capabilities-unit-plan.mjs": "aac2568f361baf0bcb7fdda51b9a970fbbb81e6102a5cb66f395080bcfdd213a",
  "scripts/resource-private-state-unit-plan.mjs": "72e542eeedd0f962545b9179e6a6bbe7032322525f113dd2fd9f090a66bae3a0",
  "scripts/resource-snapshot-unit-plan.mjs": "b8b6385d5986a5a6d20ae6938efcee65b6b081b73a0f3836b7bd804f72b87bad",
  "scripts/resource-state-unit-plan.mjs": "f6803eb22cbfe4bf8fc79cd70e16054824b98f6d29b8d05a9417092f6d40401a",
  "scripts/run-unit-tests.mjs": "3a25bb752714645c04c7a9f0ab4d20ae5b039d4ad1c39e5d09fab2e61f5349e1",
  "scripts/runtime-capabilities-unit-plan.mjs": "313a17394caa84ccdfd3698bcdbf2056b8c755b473547d65f119864253fec978",
  "scripts/secret-flat-summary-unit-plan.mjs": "c33148f3073ea9617389fde062882b1aca35272e3f8416415cf4f67bceb19740",
  "scripts/settings-mutation-unit-plan.mjs": "66f0313646a3b98ebbe0f44deb19da19f6177e86523ceaf2623255e6c6f7844a",
  "scripts/shared-metadata-query-unit-plan.mjs": "d41c5384c60a7b12ae029161216437f593fb961f819344503a8387a40e88598a",
  "scripts/sign-jwt-unit-plan.mjs": "a41ec4212c86168c92ae2388012fdbf6f07b500c7b5e7f72e0cc565c91f37f2d",
  "scripts/unit-test-plan.mjs": "15f05baa5b9ed524b74425d1724fc2366d21eb6a90353eeb1dddaf2ed49a145b",
  "scripts/verify-jwt-unit-plan.mjs": "547e51c4c4622af60be838cca6c54f0d3e6cef36ac2f7f1cd3e306d60b7be208",
  "scripts/welcome-navigation-unit-plan.mjs": "6fb97e659a9dcbf968981caa114aaed3b9a53239da846ac496dc20e59527eb6b",
  "scripts/worker-reader-unit-plan.mjs": "a3f0160f79b00effede275aab4d6bfbeaa7f7a74ae8633429de82fb45c103598",
  "scripts/yaml-save-unit-plan.mjs": "93bfb5c73189cca9b1b870438a530f685094e142618396734f28e38fd952fe0c",
  "tests/account-error-node22.test.mjs": "028722cd14fb64d534d5da0a76949e07421eb0bf3e41fe891b0e045b4d795a8e",
  "tests/account-failure-node22.test.mjs": "baf655484a1d1810b3738d6262cc249c5058b16528bb465c1f27e5292ba381aa",
  "tests/account-store-constructor-node22.test.mjs": "406855837bc22f41686fa2a2e327c84e1d9e9a89d745d6c9f125aa19135cd3c0",
  "tests/ansible-selection-node22.test.mjs": "c88fd1027f9b9b281347c67bd330ae4730740ee6ba1530e19810dadac660489f",
  "tests/auth-logout-post-node22.test.mjs": "5560c250b261eccca5e10c183406d6a7033edd21c73bd6f45dbdefd5af3334a4",
  "tests/auth-register-post-node22.test.mjs": "f99b0444c2a430300f99bd8727864a378ed9f7faf93ea09f640bd53c438099c0",
  "tests/auth-session-get-node22.test.mjs": "bf99fb2a72be2cebc97cb793353dee976cf7aace3d8b442b0abc4612404589c8",
  "tests/create-job-stream-node22.test.mjs": "d873f9956fd20f177bab16aa08ceefebdf66a83132cec96f83a1ef4e514c86a2",
  "tests/current-account-node22.test.mjs": "565d9f2950caa363009cc1ea5e709458cd4283897fc8669addf7e1e28b7b155f",
  "tests/current-session-node22.test.mjs": "0c4316b29c5f5fe4e67387e7b377a116df7bfa95c29f11f4985e5cd95ba5f640",
  "tests/deploy-history-delete-node22.test.mjs": "b6d79dd1ff603e5450ccb2de667fd1ee013c5e5de98af12666a6d5ace02aecb1",
  "tests/deploy-history-get-node22.test.mjs": "687bb9986921de855908c2c828412e83d74ca63c906aae23cf4bf3abee35fb86",
  "tests/deploy-start-get-node22.test.mjs": "4daa75860c998bf192ed9047b273e4dbda8b02833278a1e3b32f1a35d1a45324",
  "tests/deploy-start-post-node22.test.mjs": "e064c701190e5a456b7651499ac49fe005e740f9506df016acc43665deab2eea",
  "tests/deploy-stop-node22.test.mjs": "0d46811b9f5a5b8af124893fcdaa3e51dae8df2c2e32210cbbec404fd1d53047",
  "tests/deploy-stream-node22.test.mjs": "97a0ce3e5ba330564fe0ec2ce78e21f31a420bf82fdc79b08cb64723c67be179",
  "tests/deployment-pods-node22.test.mjs": "0ad0a4289654ed79e7dd39f3571b3973ceeaebc4b733f1ed5a7970ebf8e9c295",
  "tests/ensure-jwt-secret-node22.test.mjs": "9043a250b21cca62778650bd932f195ab6045b8b8ac585f7b3995a5b61219cca",
  "tests/get-current-role-node22.test.mjs": "365d067db0ecdbe7c31bb82e84d6d4101c63f2862a04f7ea9b95a0772e654b80",
  "tests/get-session-account-from-headers-node22.test.mjs": "600c2c18ba3a5f7b1ef4cd28d638ed0e49a82e63dc68ed01110a6c462640c3f9",
  "tests/get-session-account-node22.test.mjs": "143436eb149b844bc4133a8303a174b037f5f7cbe6cd0bbe1367f2c695030c29",
  "tests/get-session-from-headers-node22.test.mjs": "8a4ee8f2c2ee4ab48343ecc511b1e56142653c0cca07eafceb52f96ce3e4e364",
  "tests/get-session-node22.test.mjs": "820f7a9a06643743e31ad628a9d01a7f36c58d6c2bc357ed931be3124997f548",
  "tests/job-id-valid-node22.test.mjs": "34f5883c515377a42c7a41eb2c32ff14f6c7f1eb9130f73cf426a0d76c4a95a0",
  "tests/kv-audit-route-node22.test.mjs": "edf87c9baa52c309f87d413ae132e626cb3f6ccff2d414ac16bd71f211da3676",
  "tests/kv-automation-route-node22.test.mjs": "07161c1c3cb4abce99f7da32b88dc268dfaf556fce911ce22d8d572259505406",
  "tests/kv-config-node22.test.mjs": "6b34c496b4ef7aa2dba8cd39ec9ce30e252706c31c860bfc27f6b3c1714e9463",
  "tests/kv-engine-node22.test.mjs": "f5f90ae0c949a809ab977d5ae51ede597f896d28ccb95e12877438f1ef3a2d37",
  "tests/kv-error-response-node22.test.mjs": "4cdd347d252c87f82b80de98c76148441bf58cdc222c614425a4cb11584bca2e",
  "tests/kv-field-mapping-node22.test.mjs": "1d22651a04fa73c3aad71d8209f840097ed7e3089c0c85e6848de91b7cce6c65",
  "tests/kv-history-gc-node22.test.mjs": "70d9810e5f0653a3068570b19bd1b4d2e7021776792daba093c5bf484abef285",
  "tests/kv-history-gc-preview-node22.test.mjs": "6d4a0008817e2a7358654877deb8a13b151d1b325a6894f45ecbee04f8da6758",
  "tests/kv-metadata-query-node22.test.mjs": "6c73ff618bad4b81f6bfa883a3e464be27f13b774b6ae9a53680c6f791a6a716",
  "tests/kv-parse-actions-node22.test.mjs": "effdd299075fae6a821911793b3f8cad80b3711b34ab1add163fc5756b195da0",
  "tests/kv-policy-allows-node22.test.mjs": "afcd9917220fab360c914b9ec556a28545c4ef95b8f04c816bfcb9f9cd43d98c",
  "tests/kv-policy-preview-node22.test.mjs": "f8d87143bbb169f76ad1d19843dabac77d73ad9cf9d272cae9b508aeda5beef9",
  "tests/kv-registry-node22.test.mjs": "a11ec744bd9dc14cea881be51d260068096f15d16d82bfcc5722b82cf4190286",
  "tests/kv-require-guarded-node22.test.mjs": "7a2b5e09f9e7f62aa7189385cfe7cfee3b4e43ca2d089b6c882b9730e81a5a78",
  "tests/observe-ansible-process-node22.test.mjs": "e26058396578cd119715c354df2f64ffe44e329dc14cf741709230f53654b05a",
  "tests/read-job-slice-node22.test.mjs": "36bed9bd4a78a43e2a1fc51815467953c7d21085f2e27b00e701ba4dddc5d4fb",
  "tests/read-job-tail-node22.test.mjs": "9569c6b878efbfcef32966bbb4774e9957f70c8118d475500b492d21be5ea05c",
  "tests/require-access-node22.test.mjs": "950f1901035c740ccb6263fb9653feabd67afd4691251de3b1894d03b6e3dab0",
  "tests/require-operator-node22.test.mjs": "a12b33b1ac633347f40f6e8fdac49b0cbb445a20b2dbcb4171f5be15a02a847c",
  "tests/require-write-node22.test.mjs": "088a9b02ca071178793c054e9d6a90e18edaeeb9814c37a70cb22005c2bdf461",
  "tests/resource-base-node22.test.mjs": "f8c48b51d5e90268947b3c83cb0e7b41820559adfa76c572043515d786f3824e",
  "tests/resource-cache-node22.test.mjs": "9ae822802b018aa95351eb855aeed67f9f511c554fc6f8b898e790b5b9a3662b",
  "tests/resource-capabilities-node22.test.mjs": "bdd996bba473db57301ff34c364a4e48ae6ece3e9e28998f1c9cac6c7565a8bc",
  "tests/resource-private-state-node22.test.mjs": "fc4749e658a3658757fc5377d7ca4450294413d17b4c12724147d6fa508822c4",
  "tests/resource-snapshot-node22.test.mjs": "9e3e30a9df1dc4302523e21a4847820ae67ae629cdc1d256a6a2c17341ca23ea",
  "tests/resource-state-node22.test.mjs": "53f65221f2f4aea95ff3a35da0f2456db34c61652a32fb1bbc5a3cf868fc721d",
  "tests/runtime-capabilities-node22.test.mjs": "b8e26a0c149bb2bb3127752101b75d45a069bc8e35f7b3e2143e6d70efeeb38a",
  "tests/secret-flat-summary-node22.test.mjs": "49480b03b1b4a9901f5508584bdde997c719078de57794cba6084d1b15ff0ce9",
  "tests/settings-mutation-node22.test.mjs": "2b93d018ad199191c009efb83a004910d51e86467b920da1fed913604411278d",
  "tests/shared-metadata-query-node22.test.mjs": "fcbe11e5c35ef41e3d4234fb582b762ae15392b31a547028104597e554f76ef1",
  "tests/sign-jwt-node22.test.mjs": "cfd71c159415dd8abb8f89e3f571bfa5b9d9aa905c666c18c314b256bc6c1899",
  "tests/verify-jwt-node22.test.mjs": "0943be8fe065d619a19f6eff5090858dbc60207c38f8e3fe4b3aff54a8e3e343",
  "tests/welcome-navigation-node22.test.mjs": "a4aa1babe5c3a881f2bac6498d570bf9e152f1c5145fe8d7a327ddd1b248d658",
  "tests/worker-reader-node22.test.mjs": "9ef476c4d39a42938181014c5389e8e4513ede38d0c7f96e37b090a14fe0449d",
  "tests/yaml-save-node22.test.mjs": "b572be55ee61c4b328154cfdeb5c5ba8c4a69cd82853647f7843832e0c65b756"
};
 const current = bindCurrentPackagingAggregateCompatibility(snapshot(), frozen);
 for (const [name] of Object.entries(frozen)) {
  const bytes = current.read(name);
  assert.equal(digest(bytes), current.pin(name).sha256, name);
 }
});
