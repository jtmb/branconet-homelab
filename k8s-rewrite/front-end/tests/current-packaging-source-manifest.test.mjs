import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { currentPackagingSource as fixed, historicalPackagingAuthorities as historical } from '../scripts/current-packaging-source-manifest.mjs';

const fixedCommit = '206e0a5191e3d8edd6856619668e70326aa92fff';
const prefix = 'k8s-rewrite/front-end/';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const compact = value => JSON.stringify(value);
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

test('S01 actual pinned runtime and independent compiler are genuine', () => {
  assert.equal(process.versions.node, '22.23.3');
  const ts = createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
  assert.equal(ts.version, '5.9.3');
});
test('S02 fixed PUBLIC identity and entire frozen manifest fingerprint', () => {
  assert.equal(fixed.publicCommit, fixedCommit);
  assert.equal(fixed.frontendTree, 'a2c4a6eff4e7a8b4e58320b261ca8597f7a15a63');
  assert.equal(fixed.entries.length, 782);
  assert.equal(sha(compact(fixed)), '0260ecdd5b0401a7acb1f069c178c1e8d25371fe126e35efb7774b21a7482e0f');
  assert.equal(sha(compact(historical)), '280afd67696417216d9535a670f173b9ea7164bb033befdfda2f44358d8eee80');
});
test('S03 complete independent actual PUBLIC names, modes and blob IDs match', () => {
  assert.deepEqual(fixed.entries.map(({ path, mode, blob }) => ({ path, mode, blob })), inventory);
  assert.equal(new Set(inventory.map(row => row.path)).size, 782);
  assert.equal(inventory.some(row => row.mode === '120000' || row.mode === '160000'), false);
});
test('S04 all782 PUBLIC raw-byte hashes and lengths match actual Git blobs', () => {
  let total = 0;
  for (const row of fixed.entries) {
    const bytes = actual.get(row.path).bytes;
    assert.equal(sha(bytes), row.gitRaw.sha256, row.path);
    assert.equal(bytes.length, row.gitRaw.bytes, row.path); total += bytes.length;
  }
  assert.equal(total, 10396615);
});
test('S05 both explicit derived representations independently bind each PUBLIC blob', () => {
  for (const row of fixed.entries) for (const representation of ['linuxLFProjection', 'windowsCRLFProjection']) {
    const projected = project(actual.get(row.path).bytes, representation);
    assert.equal(sha(projected), row[representation].sha256, row.path);
    assert.equal(projected.length, row[representation].bytes, row.path);
  }
  assert.match(fixed.representations.windowsCRLFProjection, /not an observed Windows/);
  assert.match(fixed.representations.linuxLFProjection, /not an observed Linux/);
});
test('S06 complete original helper and all five historical maps remain fixed data', () => {
  const original = actual.get('scripts/packaging-provenance.mjs').bytes;
  assert.equal(sha(original), historical.helperSHA256);
  const maps = [...original.toString().matchAll(/const (\w+Pins) = Object.freeze\((\{.*?\})\);/gs)];
  assert.equal(maps.length, 5);
  for (const [, name, literal] of maps) {
    const value = JSON.parse(literal);
    assert.deepEqual(historical.helperMaps[name].entries, value);
    assert.equal(sha(compact(value)), historical.helperMaps[name].sha256);
  }
});
test('S07 all50 actual original helper callers and51 literal authorities bind independently', () => {
  const callers = [...actual].filter(([path, row]) => path.startsWith('tests/') && path.endsWith('.mjs') && row.bytes.toString().includes("from '../scripts/packaging-provenance.mjs'")).map(([path]) => path).sort();
  assert.deepEqual(historical.callers.map(row => row.path), callers); assert.equal(callers.length, 50);
  let count = 0;
  for (const caller of historical.callers) {
    assert.equal(sha(actual.get(caller.path).bytes), caller.gitRawSHA256);
    const maps = frozenMaps(caller.path);
    assert.equal(maps.length, caller.maps.length); count += maps.length;
    for (const [index, map] of maps.entries()) {
      assert.equal(sha(map.literal), caller.maps[index].literalSHA256);
      assert.equal(sha(compact(Object.entries(map.value))), caller.maps[index].entriesSHA256);
      assert.equal(Object.keys(map.value).length, caller.maps[index].count);
      for (const path of Object.keys(map.value)) assert.ok(actual.has(path), path);
    }
  }
  assert.equal(count, 51);
});
test('S08 changed packaging, lock, source, runner and original/current fixtures have independent fixed pins', () => {
  const critical = {"Dockerfile":"2deb0552529cf69876a70e90c5b67f43b7c28eed498664ed954e1dbca27246ca","Dockerfile.release":"d2ce23628d68783ccd80de0adcc8ddbe7d26ea11f48b4c8c4d96c7cd9e6df69e","package-lock.json":"5c9baf955f5412825c6ea391078d99b1f36acb2df832034ba2e684ce2d512775","package.json":"9af95ba24f041cab39ad5686b1ab010316038cadf4a3ab658334ca261d08d342","scripts/run-compatible-unit-tests.mjs":"7b0bfc65544df736741df84785c347bbf678926ddc5ba3db4c0d329fd5960ad9","src/app/api/auth/login/route.ts":"c42dfb02eb45e5c2627b4b3428ba09f392b580bfca0e89144c03612f1b4098af","src/app/api/auth/register/route.ts":"601f87718aa72a21682b2a896e13a2cb49da1baa1f7ad1f35b09174413378acd","tests/auth-login-current-unit-plan.test.mjs":"929c448d836dbfe3e586ccc167e5cac2160a69e34a7272395b081e90fe6d1d6c","tests/auth-register-post-node22.test.mjs":"f99b0444c2a430300f99bd8727864a378ed9f7faf93ea09f640bd53c438099c0","tests/auth-register-post-source.test.ts":"c9d6fc744d812617bfe1aa47bec83f1e0abfd9fbbb37d902a273571639ee2d7d"};
  for (const [path, pin] of Object.entries(critical)) assert.equal(sha(actual.get(path).bytes), pin, path);
});
test('S09 complete public-only SystemReport inputs and mixed-EOL witness stay present', () => {
  for (const path of ['.gitignore', 'scripts/provision-scanner.mjs', 'src/lib/system-report.ts', 'tests/system-report.test.ts', 'tests/scanner-database-update.test.ts']) assert.ok(actual.has(path));
  const mixed = actual.get('tests/kv-parse-actions-node22.test.mjs').bytes;
  assert.ok(mixed.includes(Buffer.from('\r\n'))); assert.ok(mixed.toString().replaceAll('\r\n', '').includes('\n'));
  assert.notEqual(sha(mixed), sha(project(mixed, 'linuxLFProjection')));
});
test('S10 all fixed data including nested entries and historical maps are immutable', () => {
  const visit = value => { if (value && typeof value === 'object') { assert.ok(Object.isFrozen(value)); for (const child of Object.values(value)) visit(child); } };
  visit(fixed); visit(historical);
  assert.throws(() => { fixed.entries[0].gitRaw.sha256 = '0'.repeat(64); }, TypeError);
  assert.throws(() => { historical.callers[0].maps[0].count++; }, TypeError);
});
test('S11 the four new files are explicit extensions outside the fixed base snapshot', () => {
  assert.deepEqual(fixed.excludedAuthorityPaths, ['scripts/current-packaging-source-manifest.mjs', 'scripts/current-packaging-provenance.mjs', 'tests/current-packaging-source-manifest.test.mjs', 'tests/current-packaging-provenance.test.mjs']);
  for (const path of fixed.excludedAuthorityPaths) assert.equal(actual.has(path), false);
  const discovered = inventory.filter(row => /^tests\/[^/]+\.test\.(ts|mjs)$/.test(row.path));
  assert.equal(discovered.length, 354);
  assert.equal(discovered.length + fixed.excludedAuthorityPaths.filter(path => path.startsWith('tests/')).length, 356);
});
test('S12 actual owner helper, all50 callers and planners remain byte-bound without execution', () => {
  const paths = ['scripts/packaging-provenance.mjs', ...historical.callers.map(row => row.path), ...inventory.filter(row => /^scripts\/.*unit-plan\.mjs$/.test(row.path)).map(row => row.path), 'scripts/run-compatible-unit-tests.mjs', 'tests/auth-register-post-source.test.ts', 'tests/auth-register-post-node22.test.mjs', 'tests/auth-register-post-current-source.test.mjs', 'tests/auth-login-post-source.test.ts', 'tests/auth-login-post-current-source.test.mjs'];
  for (const path of new Set(paths)) {
    const owner = readFileSync(new URL('../' + path, import.meta.url));
    const publicBytes = actual.get(path).bytes;
    assert.equal(sha(owner.toString().replaceAll('\r\n', '\n')), sha(publicBytes.toString().replaceAll('\r\n', '\n')), path);
  }
});
