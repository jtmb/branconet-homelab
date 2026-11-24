import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { currentPackagingDeployStartPost as fixed } from '../scripts/current-packaging-deploy-start-post-manifest.mjs';
import { bindCurrentPackagingDeployStartPost } from '../scripts/current-packaging-deploy-start-post-provenance.mjs';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const fixedCommit = '73c24ffd353524ad2afb37473d265c66aac8f907';
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
const original = actual.get('tests/deploy-start-post-unit-plan.test.mjs').bytes.toString();
const callback = original.slice(original.indexOf("test('M16 "), original.indexOf("\ntest('M17"));
const selectedMapLiteral = text => {
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  const ast = ts.createSourceFile('selected.mjs', text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const calls = ast.statements.filter(n => ts.isExpressionStatement(n) && ts.isCallExpression(n.expression) && n.expression.expression.getText(ast) === 'test');
  assert.equal(calls.length, 1);
  const declarations = calls[0].expression.arguments[1].body.statements.filter(ts.isVariableStatement).flatMap(n => [...n.declarationList.declarations]);
  const frozen = declarations.filter(n => n.name.getText(ast) === 'frozen');
  assert.equal(frozen.length, 1); assert.ok(ts.isObjectLiteralExpression(frozen[0].initializer));
  return frozen[0].initializer.getText(ast);
};
const mapLiteral = selectedMapLiteral(callback);
const historical = () => JSON.parse(mapLiteral);
assert.equal(process.versions.node, '22.23.3');
assert.equal(createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT).version, '5.9.3');

// Only the selected callback is projected below; all neighbours remain inert.
test('C01 fixed-current projection of exact historical deploy-start-post M16 packaging callback', () => {
  const frozen = {
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
  const current = bindCurrentPackagingDeployStartPost(snapshot(), frozen);
  for (const [name] of Object.entries(frozen)) {
    const bytes = current.read(name);
    assert.equal(digest(bytes), current.pin(name).sha256, name);
  }
});
