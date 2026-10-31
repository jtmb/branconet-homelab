import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { currentPackagingWrite as fixed } from '../scripts/current-packaging-write-manifest.mjs';
import { bindCurrentPackagingWrite } from '../scripts/current-packaging-write-provenance.mjs';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const fixedCommit = 'c70f9d719d7fd19ea7928deae95fe0bbe37474a8';
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
const original = actual.get('tests/require-write-unit-plan.test.mjs').bytes.toString();
const callback = original.slice(original.indexOf("test('M15 "), original.indexOf("\ntest('M16"));
const mapLiteral = callback.match(/const frozen\s*=\s*(\{[^;]*\});/s)[1];
const historical = () => JSON.parse(mapLiteral);
assert.equal(process.versions.node, '22.23.3');
assert.equal(createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT).version, '5.9.3');

const oldLabel = "test('M15 all677 prior nonrunner raw inputs and all39 completed layers remain frozen',()=>{";
const newLabel = "test('C01 fixed-current projection of exact historical require-write M15 packaging callback', () => {";
const newTail = "  const current = bindCurrentPackagingWrite(snapshot(), frozen);\n  for (const [name] of Object.entries(frozen)) {\n    const bytes = current.read(name);\n    assert.equal(digest(bytes), current.pin(name).sha256, name);\n  }\n});";

const mutate = (path, fn) => { const next = snapshot(); const i = next.entries.findIndex(row => row.path === path); assert.ok(i >= 0); next.entries[i] = fn(next.entries[i]); return next; };
const refuse = (next, map = historical()) => assert.throws(() => bindCurrentPackagingWrite(next, map));
test('Q01 fixed identity and independent whole raw Git inventory', () => {
  assert.equal(fixed.publicCommit, fixedCommit); assert.equal(fixed.files, 842); assert.equal(inventory.length, 842);
  assert.equal(fixed.baseFiles, 782); assert.equal(fixed.basePublicCommit, '206e0a5191e3d8edd6856619668e70326aa92fff');
  assert.equal(fixed.frontendTree, git(['rev-parse', fixedCommit + ':' + prefix.slice(0, -1)]).toString().trim());
  assert.equal(fixed.representation, 'gitRaw'); assert.match(fixed.scope, /remain OPEN/);
});
test('Q02 exact selected callback and whole677-key historical map bind independently', () => {
  assert.equal(digest(callback), fixed.callback.sha256); assert.equal(digest(mapLiteral), fixed.callback.mapLiteralSHA256);
  assert.equal(Object.keys(historical()).length, 677); assert.equal(digest(JSON.stringify(Object.entries(historical()))), fixed.callback.orderedMapSHA256);
  assert.equal(Buffer.byteLength(original.slice(0, original.indexOf("test('M15 "))), fixed.callback.startByte);
  assert.equal(fixed.callback.endByte - fixed.callback.startByte, Buffer.byteLength(callback));
});
test('Q03 sixty later additions have independent raw mode length blob and hash pins', () => {
  assert.equal(fixed.additions.length, 60);
  for (const pin of fixed.additions) {
    const row = actual.get(pin.path); assert.equal(row.blob, pin.blob); assert.equal(row.mode, pin.mode);
    assert.equal(row.bytes.length, pin.bytes); assert.equal(digest(row.bytes), pin.sha256);
  }
  const baseInventory = git(['ls-tree', '-r', '-z', fixed.basePublicCommit, '--', prefix]).toString().split('\0').filter(Boolean);
  assert.equal(baseInventory.length, 782);
  for (const line of baseInventory) {
    const [meta, path] = line.split('\t'); const [mode, kind, blob] = meta.split(' '); assert.equal(kind, 'blob');
    const row = actual.get(path.slice(prefix.length)); assert.equal(row.mode, mode); assert.equal(row.blob, blob);
  }
});
test('Q04 independent exact byte inverse restores only original selected callback', () => {
  const projected = readFileSync(new URL('./require-write-current-packaging.test.mjs', import.meta.url), 'utf8');
  const lifted = projected.slice(projected.indexOf(newLabel)).trimEnd();
  assert.equal(lifted.split(newTail).length, 2);
  const oldTail = callback.slice(callback.indexOf(' const publicLineage='));
  const restored = lifted.replace(newLabel, oldLabel).replace(newTail, oldTail);
  assert.equal(restored, callback); assert.equal(digest(restored), fixed.callback.sha256);
  assert.equal(lifted.match(/const frozen\s*=\s*(\{[^;]*\});/s)[1], mapLiteral);
  assert.equal((lifted.match(/test\('/g) || []).length, 1);
});
test('Q05 AST proves single lifted registration and only the guarded raw-byte loop changes', () => {
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  const text = readFileSync(new URL('./require-write-current-packaging.test.mjs', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('projection.mjs', text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const registrations = ast.statements.filter(n => ts.isExpressionStatement(n) && ts.isCallExpression(n.expression) && n.expression.expression.getText(ast) === 'test');
  assert.equal(registrations.length, 1); const fn = registrations[0].expression.arguments[1];
  assert.ok(ts.isArrowFunction(fn)); assert.equal(fn.body.statements.length, 4);
  const originalAst = ts.createSourceFile('original.mjs', callback, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(originalAst.parseDiagnostics.length, 0);
  const originalFn = originalAst.statements[0].expression.arguments[1];
  assert.deepEqual(fn.body.statements.slice(0, 2).map(n => n.getText(ast)), originalFn.body.statements.slice(0, 2).map(n => n.getText(originalAst)));
  assert.equal(fn.body.statements[1].declarationList.declarations[0].name.getText(ast), 'publicPins');
  const loop = fn.body.statements[3]; assert.ok(ts.isForOfStatement(loop));
  assert.equal(loop.expression.getText(ast), 'Object.entries(frozen)');
  assert.equal(loop.statement.statements[0].getText(ast), 'const bytes = current.read(name);');
  assert.equal(loop.statement.statements[1].getText(ast), 'assert.equal(digest(bytes), current.pin(name).sha256, name);');
});
test('Q06 whole677-key consumer bridge resolves every raw pin in exact historical order', () => {
  const view = bindCurrentPackagingWrite(snapshot(), historical()); assert.ok(Object.isFrozen(view)); assert.ok(Object.isFrozen(view.receipt));
  assert.equal(view.receipt.files, 842); assert.equal(view.receipt.historicalKeys, 677);
  for (const name of Object.keys(historical())) {
    const row = actual.get(name); assert.deepEqual(view.read(name), row.bytes);
    assert.deepEqual(view.pin(name), { mode: row.mode, bytes: row.bytes.length, sha256: digest(row.bytes) }); assert.ok(Object.isFrozen(view.pin(name)));
  }
});
test('Q07 complete public inventory can reorder without altering caller order', () => {
  const next = snapshot(); next.entries.reverse(); assert.equal(bindCurrentPackagingWrite(next, historical()).receipt.files, 842);
});
test('Q08 historical map failures precede any snapshot access', () => {
  const map = historical(), pairs = Object.entries(map), name = pairs[0][0];
  const variants = [{ ...map, [name]: '0'.repeat(64) }, Object.fromEntries(pairs.slice(1)), { ...map, unknown: '0'.repeat(64) }, Object.fromEntries(pairs.reverse()), null, [], {}];
  for (const bad of variants) {
    let reads = 0; const next = { get publicCommit() { reads++; throw new Error('must stay inert'); } };
    assert.throws(() => bindCurrentPackagingWrite(next, bad), /Historical|historical/); assert.equal(reads, 0);
  }
});
test('Q09 map accessor inherited symbolic and hidden keys refuse without invoking getters', () => {
  const name = Object.keys(historical())[0]; let reads = 0;
  const accessor = historical(); Object.defineProperty(accessor, name, { enumerable: true, get() { reads++; return '0'.repeat(64); } }); refuse(snapshot(), accessor); assert.equal(reads, 0);
  const inherited = Object.assign(Object.create({ extra: true }), historical()); refuse(snapshot(), inherited);
  const hidden = historical(); Object.defineProperty(hidden, 'extra', { value: '0'.repeat(64) }); refuse(snapshot(), hidden);
  const symbol = historical(); symbol[Symbol('extra')] = '0'.repeat(64); refuse(snapshot(), symbol);
});
test('Q10 wrong private base unknown and missing checkpoint refuse', () => {
  for (const publicCommit of ['3768ac839ce083714a6beb769bf295429be0589c', fixed.basePublicCommit, '', undefined]) refuse({ ...snapshot(), publicCommit });
});
test('Q11 derived LF and CRLF labels are never raw caller authority', () => {
  for (const representation of ['linuxLFProjection', 'windowsCRLFProjection', 'local', undefined]) refuse({ ...snapshot(), representation });
  const path = 'package.json'; refuse(mutate(path, row => ({ ...row, bytes: Buffer.from(row.bytes.toString().replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')) })));
});
test('Q12 missing extra duplicate new-self and unknown paths refuse', () => {
  const next = snapshot(); refuse({ ...next, entries: next.entries.slice(1) });
  refuse({ ...next, entries: [...next.entries, next.entries[0]] });
  refuse({ ...next, entries: [next.entries[0], ...next.entries.slice(0, -1)] });
  for (const path of [...fixed.excludedNewPaths, '../Dockerfile', '/Dockerfile', 'toString']) refuse(mutate('Dockerfile', row => ({ ...row, path })));
});
test('Q13 mode symlink and submodule substitutions refuse', () => {
  for (const mode of ['100755', '120000', '160000', 100644, undefined]) refuse(mutate('Dockerfile', row => ({ ...row, mode })));
});
test('Q14 string typed-array and accessor bytes refuse without getter execution', () => {
  for (const bytes of ['', new Uint8Array(0), null, undefined]) refuse(mutate('Dockerfile', row => ({ ...row, bytes })));
  let reads = 0; refuse(mutate('Dockerfile', row => ({ path: row.path, mode: row.mode, get bytes() { reads++; return row.bytes; } }))); assert.equal(reads, 0);
  for (const next of [null, [], {}, { ...snapshot(), override: fixed }]) refuse(next);
});
for (const path of ['Dockerfile', 'src/app/api/auth/login/route.ts', 'tests/require-write-unit-plan.test.mjs', ...fixed.additions.map(row => row.path)]) test('Q15 same-size byte tamper refuses ' + path, () => {
  refuse(mutate(path, row => { const bytes = Buffer.from(row.bytes); bytes[0] ^= 1; return { ...row, bytes }; }));
});
test('Q16 all sixty later additions required independently of unchanged782 base', () => {
  const next = snapshot(); const additions = new Set(fixed.additions.map(row => row.path));
  refuse({ ...next, entries: next.entries.filter(row => !additions.has(row.path)) });
  for (const path of additions) refuse(mutate(path, row => ({ ...row, bytes: Buffer.concat([row.bytes, Buffer.from('\n')]) })));
});
test('Q17 real private Dockerfile substituted into otherwise public inventory refuses', () => {
  const bytes = readFileSync(new URL('../Dockerfile', import.meta.url));
  assert.notEqual(digest(bytes), digest(actual.get('Dockerfile').bytes));
  refuse(mutate('Dockerfile', row => ({ ...row, bytes })));
});
test('Q18 post-validation caller mutation cannot change the qualified view', () => {
  const next = snapshot(), view = bindCurrentPackagingWrite(next, historical()); const name = Object.keys(historical())[0];
  const row = next.entries.find(row => row.path === name); row.bytes[0] ^= 1;
  assert.deepEqual(view.read(name), actual.get(name).bytes);
  const copy = view.read(name); copy[0] ^= 1; assert.deepEqual(view.read(name), actual.get(name).bytes);
});
test('Q19 no current unknown path or unrelated known path gains hash fallback', () => {
  const view = bindCurrentPackagingWrite(snapshot(), historical());
  for (const name of ['unknown', 'toString', '../Dockerfile', fixed.additions[0].path]) {
    assert.throws(() => view.read(name)); assert.throws(() => view.pin(name));
  }
});
test('Q20 fixed data stays immutable and bridge has no original module or byte normalization', () => {
  const visit = value => { if (value && typeof value === 'object') { assert.ok(Object.isFrozen(value)); for (const child of Object.values(value)) visit(child); } }; visit(fixed);
  const source = readFileSync(new URL('../scripts/current-packaging-write-provenance.mjs', import.meta.url), 'utf8');
  for (const text of ["from './packaging-provenance.mjs'", 'compatibleInputHash(', 'replaceAll(', 'node:fs', 'node:child_process', 'import(']) assert.equal(source.includes(text), false, text);
  assert.ok(source.indexOf('assertHistoricalPackagingAuthority(fixed.callback.path') < source.indexOf("record(snapshot,"));
});
