import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { currentPackagingSource as fixed, historicalPackagingAuthorities as historical } from '../scripts/current-packaging-source-manifest.mjs';
import { classifyCurrentPackaging, assertHistoricalPackagingAuthority, currentPackagingInputPin, currentPackagingInputPins } from '../scripts/current-packaging-provenance.mjs';

const fixedCommit = '206e0a5191e3d8edd6856619668e70326aa92fff';
const prefix = 'k8s-rewrite/front-end/';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const gitDir = process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
assert.ok(gitDir, 'Explicit readonly PUBLIC Git object authority required');
const git = (args, input) => {
  const result = spawnSync('git', ['-c', 'safe.directory=' + gitDir, '--git-dir=' + gitDir, ...args], {
    input, maxBuffer: 64 * 1024 * 1024,
  });
  assert.equal(result.status, 0, 'Unable to read fixed PUBLIC Git objects');
  return result.stdout;
};
const inventory = git(['ls-tree', '-r', '-z', fixedCommit, '--', prefix]).toString('utf8').split('\0').filter(Boolean).map(line => {
  const [meta, path] = line.split('\t');
  const [mode, kind, blob] = meta.split(' ');
  assert.equal(kind, 'blob');
  return { path: path.slice(prefix.length), mode, blob };
});
const batch = git(['cat-file', '--batch'], inventory.map(row => row.blob).join('\n') + '\n');
let offset = 0;
const actual = new Map(inventory.map(row => {
  const end = batch.indexOf(10, offset);
  const [blob, kind, size] = batch.subarray(offset, end).toString().split(' ');
  assert.equal(blob, row.blob); assert.equal(kind, 'blob');
  offset = end + 1;
  const bytes = batch.subarray(offset, offset + Number(size));
  offset += Number(size); assert.equal(batch[offset++], 10);
  return [row.path, { ...row, bytes }];
}));
assert.equal(offset, batch.length);
const project = (bytes, representation) => {
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); } catch { return bytes; }
  if (text.includes('\0') || text.replaceAll('\r\n', '').includes('\r')) return bytes;
  if (representation === 'gitRaw') return bytes;
  const lf = text.replaceAll('\r\n', '\n');
  return Buffer.from(representation === 'linuxLFProjection' ? lf : lf.replaceAll('\n', '\r\n'));
};
const frozenMaps = caller => [...actual.get(caller).bytes.toString('utf8').matchAll(/const frozen\s*=\s*(\{[^;]*\});/gs)].map(match => ({
  literal: match[1], value: JSON.parse(match[1]),
}));

const snapshot = (representation = 'gitRaw') => ({
  publicCommit: fixedCommit, representation,
  entries: inventory.map(({ path, mode }) => ({ path, mode, bytes: project(actual.get(path).bytes, representation) })),
});
const change = (path, mutate) => {
  const next = snapshot(); const index = next.entries.findIndex(row => row.path === path);
  assert.ok(index >= 0); next.entries[index] = mutate(next.entries[index]); return next;
};
const firstCaller = historical.callers[0].path;
const firstMap = () => frozenMaps(firstCaller)[0].value;
const refuse = value => assert.throws(() => classifyCurrentPackaging(value));
test('P01 full actual PUBLIC Git snapshot qualifies once as raw metadata', () => {
  assert.equal(process.versions.node, '22.23.3');
  assert.equal(createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT).version, '5.9.3');
  const result = classifyCurrentPackaging(snapshot());
  assert.deepEqual(result, { publicCommit: fixedCommit, frontendTree: fixed.frontendTree, representation: 'gitRaw', derivedProjection: false, files: 782, scope: fixed.scope });
  assert.ok(Object.isFrozen(result)); assert.match(result.scope, /No caller, aggregate, CI, image or production acceptance/);
});
for (const representation of ['linuxLFProjection', 'windowsCRLFProjection']) test('P02 explicit whole derived profile ' + representation, () => {
  const result = classifyCurrentPackaging(snapshot(representation));
  assert.equal(result.representation, representation); assert.equal(result.derivedProjection, true);
});
test('P03 inventory order is irrelevant but all inputs are still required', () => {
  const next = snapshot(); next.entries.reverse();
  assert.equal(classifyCurrentPackaging(next).files, 782);
});
test('P04 wrong current/public/private checkpoint refuses before bytes', () => {
  for (const publicCommit of ['8dd988c8d1d0a606dce2f52bbfa549a0db2c5458', '02a9e1fc6f4cb8ba50f6ee7f6d36ac15a3aecde6', '', undefined]) refuse({ ...snapshot(), publicCommit });
});
test('P05 unknown representation and falsely labelled projected bytes refuse', () => {
  for (const representation of ['local', 'public', 'canonical', 'windows', '', undefined]) refuse({ ...snapshot(), representation });
  for (const representation of ['linuxLFProjection', 'windowsCRLFProjection']) refuse({ ...snapshot(representation), representation: 'gitRaw' });
});
test('P06 incomplete, extra, duplicate and authority-self inventory refuse', () => {
  const next = snapshot();
  refuse({ ...next, entries: next.entries.slice(1) });
  refuse({ ...next, entries: [...next.entries, { path: 'unknown', mode: '100644', bytes: Buffer.alloc(0) }] });
  refuse({ ...next, entries: [next.entries[0], ...next.entries.slice(0, -1)] });
  refuse({ ...next, entries: [{ path: fixed.excludedAuthorityPaths[0], mode: '100644', bytes: Buffer.alloc(0) }, ...next.entries.slice(1)] });
});
test('P07 unsafe paths and Git mode/link/submodule changes refuse', () => {
  for (const path of ['../Dockerfile', '/Dockerfile', 'scripts\\test.mjs', 'Dockerfile\0', 'toString']) refuse(change('Dockerfile', row => ({ ...row, path })));
  for (const mode of ['100755', '120000', '160000', 100644, undefined]) refuse(change('Dockerfile', row => ({ ...row, mode })));
});
test('P08 string, typed array, malformed entry and accessor inputs refuse without getter execution', () => {
  for (const bytes of ['', new Uint8Array(0), null, undefined]) refuse(change('Dockerfile', row => ({ ...row, bytes })));
  for (const entries of [null, {}, 'all']) refuse({ ...snapshot(), entries });
  let touched = 0;
  const entry = { path: 'Dockerfile', mode: '100644', get bytes() { touched++; return actual.get('Dockerfile').bytes; } };
  refuse(change('Dockerfile', () => entry)); assert.equal(touched, 0);
  for (const value of [null, undefined, [], {}, { ...snapshot(), overrideManifest: fixed }]) refuse(value);
});
for (const path of ['Dockerfile', 'Dockerfile.release', 'package.json', 'package-lock.json', 'src/app/api/auth/login/route.ts', 'src/app/api/auth/register/route.ts', 'tests/auth-register-post-current-source.test.mjs', 'tests/kv-parse-actions-node22.test.mjs', 'docs/screenshots/system-report-desktop.jpg']) test('P09 same-size one-byte tamper refuses ' + path, () => {
  const next = change(path, row => { const bytes = Buffer.from(row.bytes); bytes[0] ^= 1; return { ...row, bytes }; });
  assert.throws(() => classifyCurrentPackaging(next), /Public input bytes changed/);
});
test('P10 mixed raw/CRLF profiles refuse and inputs remain unmodified', () => {
  const next = change('package.json', row => ({ ...row, bytes: project(row.bytes, 'windowsCRLFProjection') }));
  const before = sha(next.entries.find(row => row.path === 'package.json').bytes);
  refuse(next); assert.equal(sha(next.entries.find(row => row.path === 'package.json').bytes), before);
});
test('P11 private packaging and old auth import source cannot substitute for PUBLIC', () => {
  const privateDocker = readFileSync(new URL('../Dockerfile', import.meta.url));
  if (sha(privateDocker) !== sha(actual.get('Dockerfile').bytes)) {
    refuse(change('Dockerfile', row => ({ ...row, bytes: privateDocker })));
  }
  for (const path of ['src/app/api/auth/login/route.ts', 'src/app/api/auth/register/route.ts']) {
    const bytes = Buffer.from(actual.get(path).bytes.toString().replace('from "zod/v3";', 'from "zod";'));
    assert.notEqual(sha(bytes), sha(actual.get(path).bytes));
    refuse(change(path, row => ({ ...row, bytes })));
  }
});
test('P12 every original map qualifies by its exact independent ordered authority', () => {
  let count = 0;
  for (const caller of historical.callers) for (const [index, map] of frozenMaps(caller.path).entries()) {
    assert.equal(assertHistoricalPackagingAuthority(caller.path, index, map.value), true); count++;
  }
  assert.equal(count, 51);
});
test('P13 every fixed caller key maps to current PUBLIC raw and both derived pins', () => {
  let count = 0;
  const independent = new Map(inventory.map(row => [row.path, Object.fromEntries(['gitRaw', 'linuxLFProjection', 'windowsCRLFProjection'].map(representation => {
    const bytes = project(actual.get(row.path).bytes, representation);
    return [representation, { mode: row.mode, bytes: bytes.length, sha256: sha(bytes) }];
  }))]));
  for (const caller of historical.callers) for (const [index, map] of frozenMaps(caller.path).entries()) {
    for (const representation of ['gitRaw', 'linuxLFProjection', 'windowsCRLFProjection']) {
      const resolved = currentPackagingInputPins(caller.path, index, map.value, representation);
      assert.ok(Object.isFrozen(resolved)); assert.deepEqual(Object.keys(resolved), Object.keys(map.value));
      for (const [name, pin] of Object.entries(resolved)) {
        assert.deepEqual(pin, independent.get(name)[representation]); assert.ok(Object.isFrozen(pin));
      }
    }
    count += Object.keys(map.value).length;
  }
  assert.equal(count, 24415);
});
test('P14 altered historical value, missing/extra/reordered keys refuse', () => {
  const original = firstMap(); const entries = Object.entries(original); const [name] = entries[0];
  for (const next of [{ ...original, [name]: '0'.repeat(64) }, Object.fromEntries(entries.slice(1)), { ...original, unknown: '0'.repeat(64) }, Object.fromEntries([...entries].reverse())]) assert.throws(() => assertHistoricalPackagingAuthority(firstCaller, 0, next), /Historical packaging map changed/);
});
test('P15 unknown caller/index and arbitrary path never gain hash fallback', () => {
  for (const [caller, index] of [['unknown', 0], [firstCaller, -1], [firstCaller, 1.5], [firstCaller, 999], [firstCaller, '0']]) assert.throws(() => assertHistoricalPackagingAuthority(caller, index, firstMap()), /Unknown historical/);
  for (const path of ['unknown', '../Dockerfile', 'toString', fixed.excludedAuthorityPaths[0]]) assert.throws(() => currentPackagingInputPin(firstCaller, 0, firstMap(), path), /outside fixed historical/);
  assert.throws(() => currentPackagingInputPin(firstCaller, 0, firstMap(), Object.keys(firstMap())[0], 'unknown'), /Unknown current packaging representation/);
});
test('P16 inherited, symbolic, nonenumerable and accessor authority refuse without reads', () => {
  const original = firstMap(), name = Object.keys(original)[0]; let touched = 0;
  const getter = { ...original }; Object.defineProperty(getter, name, { enumerable: true, get() { touched++; return original[name]; } });
  const hidden = { ...original }; Object.defineProperty(hidden, name, { value: original[name], enumerable: false });
  const symbolic = { ...original, [Symbol('unknown')]: '0'.repeat(64) };
  const inherited = Object.assign(Object.create({ inherited: true }), original);
  for (const next of [getter, hidden, symbolic, inherited, null, []]) assert.throws(() => assertHistoricalPackagingAuthority(firstCaller, 0, next));
  assert.equal(touched, 0);
});
test('P17 frozen historical packaging pins stay historical while current pins are distinct', () => {
  const caller = 'tests/kv-config-unit-plan.test.mjs', original = frozenMaps(caller)[0].value;
  assert.equal(original.Dockerfile, '1aeb71c5b94b51dfffcb5593609194c010bfe353797389291f92076c546550ff');
  assert.equal(currentPackagingInputPin(caller, 0, original, 'Dockerfile').sha256, '2deb0552529cf69876a70e90c5b67f43b7c28eed498664ed954e1dbca27246ca');
  assert.notEqual(original.Dockerfile, currentPackagingInputPin(caller, 0, original, 'Dockerfile').sha256);
});
test('P18 classifier source has no old-helper execution or byte normalization fallback', () => {
  const source = readFileSync(new URL('../scripts/current-packaging-provenance.mjs', import.meta.url), 'utf8');
  assert.deepEqual([...source.matchAll(/from '([^']+)'/g)].map(match => match[1]), ['node:assert/strict', 'node:crypto', './current-packaging-source-manifest.mjs']);
  for (const token of ['replaceAll(', 'readFileSync', 'child_process', 'process.env', 'packagingLineage(', 'compatibilityRevision(']) assert.equal(source.includes(token), false, token);
});
