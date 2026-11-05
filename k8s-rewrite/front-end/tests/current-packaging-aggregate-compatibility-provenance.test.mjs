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

const oldLabel = "test('all59 frozen functional projections and complete prior planner/runner raw hashes stay exact',()=>{";
const newLabel = "test('C01 fixed-current projection of exact aggregate compatibility raw packaging callback', () => {";
const oldLoop = "for(const [name,hash] of Object.entries(frozen))assert.equal(digest(readFileSync(new URL('../'+name,import.meta.url))),hash,name);";
const newGuard = "const current = bindCurrentPackagingAggregateCompatibility(snapshot(), frozen);\n for (const [name] of Object.entries(frozen)) {\n  const bytes = current.read(name);\n  assert.equal(digest(bytes), current.pin(name).sha256, name);\n }";

const mutate = (path, fn) => { const next = snapshot(); const i = next.entries.findIndex(row => row.path === path); assert.ok(i >= 0); next.entries[i] = fn(next.entries[i]); return next; };
const refuse = (next, map = historical(), expected = /Caller public (?:mode|size|bytes) changed|Invalid caller snapshot record|Raw Buffer required|Complete caller public inventory required|Input outside fixed caller inventory|Duplicate caller public input|Wrong fixed caller public checkpoint|Raw PUBLIC Git representation required/) => assert.throws(() => bindCurrentPackagingAggregateCompatibility(next, map), expected);
test('Q01 fixed identity and independent whole raw Git inventory', () => {
  assert.equal(fixed.publicCommit, fixedCommit); assert.equal(fixed.files, 982); assert.equal(inventory.length, 982);
  assert.equal(fixed.baseFiles, 782); assert.equal(fixed.basePublicCommit, '206e0a5191e3d8edd6856619668e70326aa92fff');
  assert.equal(fixed.frontendTree, git(['rev-parse', fixedCommit + ':' + prefix.slice(0, -1)]).toString().trim());
  assert.equal(fixed.representation, 'gitRaw'); assert.match(fixed.scope, /remain OPEN/);
});
test('Q02 exact selected raw callback and top-level118-key declaration bind independently', () => {
  assert.equal(digest(callback), fixed.callback.sha256); assert.equal(digest(mapLiteral), fixed.callback.mapLiteralSHA256);
  assert.equal(digest(frozenDeclaration), fixed.frozenDeclaration.sha256);
  assert.equal(Object.keys(historical()).length,118); assert.equal(fixed.callback.literalCount,118); assert.equal(fixed.callback.appendCount,0);
  assert.equal(digest(JSON.stringify(Object.entries(historical()))), fixed.callback.orderedMapSHA256);
  assert.equal(Buffer.byteLength(original.slice(0,callbackStart)),fixed.callback.startByte);
  assert.equal(Buffer.byteLength(callback),fixed.callback.endByte-fixed.callback.startByte);
  assert.equal(Buffer.byteLength(original.slice(0,originalFrozen.start)),fixed.frozenDeclaration.startByte);
  assert.equal(Buffer.byteLength(frozenDeclaration),fixed.frozenDeclaration.endByte-fixed.frozenDeclaration.startByte);
  assert.equal(fixed.callback.mapAtModuleScope,true); assert.equal(fixed.callback.trailingLF,0); assert.equal(fixed.callback.originalStatements,1);
});
test('Q03 two hundred later additions have independent raw mode length blob and hash pins', () => {
  assert.equal(fixed.additions.length, 200);
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
test('Q04 independent exact two-part inverse restores declaration callback and whole module', () => {
  const projected = readFileSync(new URL('./aggregate-compatibility-current-packaging.test.mjs', import.meta.url), 'utf8');
  assert.ok(projected.endsWith('\n') && !projected.endsWith('\n\n'));
  const lifted = projected.slice(projected.indexOf(newLabel), -1);
  const newChunk = '\n' + frozenDeclaration + '\n ' + newGuard;
  assert.equal(lifted.split(newChunk).length,2);
  const restored = lifted.replace(newLabel,oldLabel).replace(newChunk,'\n ' + oldLoop);
  assert.equal(restored,callback); assert.equal(digest(restored),fixed.callback.sha256);
  const liftedDeclaration = frozenInfo(lifted);
  assert.equal(liftedDeclaration.declaration,frozenDeclaration); assert.equal(liftedDeclaration.literal,mapLiteral);
  const restoredModule = original.slice(0,originalFrozen.start) + liftedDeclaration.declaration + original.slice(originalFrozen.end,callbackStart) + restored + original.slice(callbackEnd);
  assert.equal(restoredModule,original); assert.equal(digest(restoredModule),digest(actual.get('tests/aggregate-unit-compatibility.test.mjs').bytes));
  assert.equal((lifted.match(/test\('/g)||[]).length,1);
});
test('Q05 AST proves lifted exact declaration and one raw callback with guarded loop', () => {
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  const text = readFileSync(new URL('./aggregate-compatibility-current-packaging.test.mjs', import.meta.url),'utf8');
  const ast = ts.createSourceFile('projection.mjs',text,ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length,0);
  const registrations = ast.statements.filter(n=>ts.isExpressionStatement(n)&&ts.isCallExpression(n.expression)&&n.expression.expression.getText(ast)==='test');
  assert.equal(registrations.length,1);const fn=registrations[0].expression.arguments[1];
  assert.ok(ts.isArrowFunction(fn));assert.equal(fn.body.statements.length,3);
  const originalAst=ts.createSourceFile('callback.mjs',callback,ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);
  assert.equal(originalAst.parseDiagnostics.length,0);const originalFn=originalAst.statements[0].expression.arguments[1];assert.equal(originalFn.body.statements.length,1);
  assert.ok(ts.isForOfStatement(originalFn.body.statements[0]));assert.equal(originalFn.body.statements[0].getText(originalAst),oldLoop);
  assert.equal(fn.body.statements[0].getText(ast),frozenDeclaration);
  const declaration=fn.body.statements[0].declarationList.declarations[0];assert.equal(declaration.name.getText(ast),'frozen');
  assert.ok(ts.isObjectLiteralExpression(declaration.initializer));assert.equal(declaration.initializer.properties.length,118);
  assert.deepEqual(declaration.initializer.properties.map(p=>{assert.ok(ts.isPropertyAssignment(p)&&ts.isStringLiteral(p.name)&&ts.isStringLiteral(p.initializer));return[p.name.text,p.initializer.text];}),Object.entries(historical()));
  assert.equal(fn.body.statements[1].getText(ast),'const current = bindCurrentPackagingAggregateCompatibility(snapshot(), frozen);');
  const loop=fn.body.statements[2];assert.ok(ts.isForOfStatement(loop));assert.equal(loop.expression.getText(ast),'Object.entries(frozen)');
  assert.equal(loop.statement.statements[0].getText(ast),'const bytes = current.read(name);');
  assert.equal(loop.statement.statements[1].getText(ast),'assert.equal(digest(bytes), current.pin(name).sha256, name);');
});
test('Q06 whole118-key consumer bridge resolves every raw pin in exact historical order', () => {
  const view = bindCurrentPackagingAggregateCompatibility(snapshot(), historical()); assert.ok(Object.isFrozen(view)); assert.ok(Object.isFrozen(view.receipt));
  assert.equal(view.receipt.files, 982); assert.equal(view.receipt.historicalKeys, 118);
  for (const name of Object.keys(historical())) {
    const row = actual.get(name); assert.deepEqual(view.read(name), row.bytes);
    assert.deepEqual(view.pin(name), { mode: row.mode, bytes: row.bytes.length, sha256: digest(row.bytes) }); assert.ok(Object.isFrozen(view.pin(name)));
  }
});
test('Q07 complete public inventory can reorder without altering caller order', () => {
  const next = snapshot(); next.entries.reverse(); assert.equal(bindCurrentPackagingAggregateCompatibility(next, historical()).receipt.files, 982);
});
test('R08 historical map failures precede any snapshot access', () => {
  const map = historical(), pairs = Object.entries(map), name = pairs[0][0];
  const variants = [{ ...map, [name]: '0'.repeat(64) }, Object.fromEntries(pairs.slice(1)), { ...map, unknown: '0'.repeat(64) }, Object.fromEntries(pairs.reverse()), null, [], {}];
  const expected = [/Historical packaging order or hash changed/, /Historical packaging map count changed/, /Historical packaging map count changed/, /Historical packaging order or hash changed/, /Invalid historical packaging map/, /Invalid historical packaging map/, /Historical packaging map count changed/];
  for (const [index, bad] of variants.entries()) {
    let reads = 0; const next = { get publicCommit() { reads++; throw new Error('must stay inert'); } };
    assert.throws(() => bindCurrentPackagingAggregateCompatibility(next, bad), expected[index]); assert.equal(reads, 0);
  }
});
test('R09 map accessor inherited symbolic and hidden keys refuse without invoking getters', () => {
  const name = Object.keys(historical())[0]; let reads = 0;
  const accessor = historical(); Object.defineProperty(accessor, name, { enumerable: true, get() { reads++; return '0'.repeat(64); } }); refuse(snapshot(), accessor, /Historical packaging record changed/); assert.equal(reads, 0);
  const inherited = Object.assign(Object.create({ extra: true }), historical()); refuse(snapshot(), inherited, /Invalid historical packaging map/);
  const hidden = historical(); Object.defineProperty(hidden, 'extra', { value: '0'.repeat(64) }); refuse(snapshot(), hidden, /Historical packaging map count changed/);
  const symbol = historical(); symbol[Symbol('extra')] = '0'.repeat(64); refuse(snapshot(), symbol, /Historical packaging map count changed/);
});
test('R10 wrong private base unknown and missing checkpoint refuse', () => {
  for (const publicCommit of ["09daf0e672724aa927f70bd3b7f9a05a5c5fca93", fixed.basePublicCommit, '', undefined]) refuse({ ...snapshot(), publicCommit });
});
test('R11 derived LF and CRLF labels are never raw caller authority', () => {
  for (const representation of ['linuxLFProjection', 'windowsCRLFProjection', 'local', undefined]) refuse({ ...snapshot(), representation });
  const path = 'package.json'; refuse(mutate(path, row => ({ ...row, bytes: Buffer.from(row.bytes.toString().replaceAll('\r\n', '\n').replaceAll('\n', '\r\n')) })));
});
test('R12 missing extra duplicate new-self and unknown paths refuse', () => {
  const next = snapshot(); refuse({ ...next, entries: next.entries.slice(1) });
  refuse({ ...next, entries: [...next.entries, next.entries[0]] });
  refuse({ ...next, entries: [next.entries[0], ...next.entries.slice(0, -1)] });
  for (const path of [...fixed.excludedNewPaths, '../Dockerfile', '/Dockerfile', 'toString']) refuse(mutate('Dockerfile', row => ({ ...row, path })));
});
test('R13 mode symlink and submodule substitutions refuse', () => {
  for (const mode of ['100755', '120000', '160000', 100644, undefined]) refuse(mutate('Dockerfile', row => ({ ...row, mode })));
});
test('R14 string typed-array and accessor bytes refuse without getter execution', () => {
  for (const bytes of ['', new Uint8Array(0), null, undefined]) refuse(mutate('Dockerfile', row => ({ ...row, bytes })));
  let reads = 0; refuse(mutate('Dockerfile', row => ({ path: row.path, mode: row.mode, get bytes() { reads++; return row.bytes; } }))); assert.equal(reads, 0);
  for (const next of [null, [], {}, { ...snapshot(), override: fixed }]) refuse(next);
});
for (const path of ['Dockerfile', 'src/app/api/auth/login/route.ts', 'tests/aggregate-unit-compatibility.test.mjs', ...fixed.additions.map(row => row.path)]) test('R15 same-size byte tamper refuses ' + path, () => {
  refuse(mutate(path, row => { const bytes = Buffer.from(row.bytes); bytes[0] ^= 1; return { ...row, bytes }; }));
});
test('R16 all two hundred later additions required independently of unchanged782 base', () => {
  const next = snapshot(); const additions = new Set(fixed.additions.map(row => row.path));
  refuse({ ...next, entries: next.entries.filter(row => !additions.has(row.path)) });
  for (const path of additions) refuse(mutate(path, row => ({ ...row, bytes: Buffer.concat([row.bytes, Buffer.from('\n')]) })));
});
test('R17 real private Dockerfile substituted into otherwise public inventory refuses', () => {
  const bytes = readFileSync(new URL('../Dockerfile', import.meta.url));
  assert.notEqual(digest(bytes), digest(actual.get('Dockerfile').bytes));
  refuse(mutate('Dockerfile', row => ({ ...row, bytes })));
});
test('Q18 post-validation caller mutation cannot change the qualified view', () => {
  const next = snapshot(), view = bindCurrentPackagingAggregateCompatibility(next, historical()); const name = Object.keys(historical())[0];
  const row = next.entries.find(row => row.path === name); row.bytes[0] ^= 1;
  assert.deepEqual(view.read(name), actual.get(name).bytes);
  const copy = view.read(name); copy[0] ^= 1; assert.deepEqual(view.read(name), actual.get(name).bytes);
});
test('Q19 no current unknown path or unrelated known path gains hash fallback', () => {
  const view = bindCurrentPackagingAggregateCompatibility(snapshot(), historical());
  for (const name of ['unknown', 'toString', '../Dockerfile', fixed.additions[0].path]) {
    assert.throws(() => view.read(name)); assert.throws(() => view.pin(name));
  }
});
test('Q20 fixed data stays immutable and bridge has no original module or byte normalization', () => {
  const visit = value => { if (value && typeof value === 'object') { assert.ok(Object.isFrozen(value)); for (const child of Object.values(value)) visit(child); } }; visit(fixed);
  const source = readFileSync(new URL('../scripts/current-packaging-aggregate-compatibility-provenance.mjs', import.meta.url), 'utf8');
  for (const text of ["from './packaging-provenance.mjs'", 'compatibleInputHash(', 'replaceAll(', 'node:fs', 'node:child_process', 'import(']) assert.equal(source.includes(text), false, text);
  assert.ok(source.indexOf('assertHistoricalPackagingAuthority(fixed.callback.path') < source.indexOf("record(snapshot,"));
});

test('Q21 independently existing fixed historical authority agrees on all118 entries', () => {
  const source = actual.get('scripts/current-packaging-source-manifest.mjs').bytes.toString();
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  const ast = ts.createSourceFile('authority.mjs', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  assert.equal(ast.parseDiagnostics.length, 0);
  const declaration = ast.statements.filter(ts.isVariableStatement).flatMap(s => [...s.declarationList.declarations]).find(d => d.name.getText(ast) === 'historicalPackagingAuthorities');
  assert.ok(declaration && ts.isCallExpression(declaration.initializer));
  const authority = JSON.parse(declaration.initializer.arguments[0].getText(ast));
  const owner = authority.callers.find(row => row.path === 'tests/aggregate-unit-compatibility.test.mjs');
  assert.ok(owner); assert.equal(owner.maps.length, 1); assert.equal(owner.maps[0].count, 118);
  assert.equal(owner.maps[0].entriesSHA256, digest(JSON.stringify(Object.entries(historical()))));
  assert.equal(owner.maps[0].literalSHA256, digest(mapLiteral));
});
