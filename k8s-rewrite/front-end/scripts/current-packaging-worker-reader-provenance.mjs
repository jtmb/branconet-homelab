import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { currentPackagingWorkerReader as fixed } from './current-packaging-worker-reader-manifest.mjs';
import { currentPackagingSource as base } from './current-packaging-source-manifest.mjs';
import { assertHistoricalPackagingAuthority, classifyCurrentPackaging } from './current-packaging-provenance.mjs';

// No filesystem, Git, original helper or callback execution. Trust the fixed
// manifest and independently complete reader. Copy raw bytes before validation
// so a subsequent caller mutation cannot change this qualified consumer view.
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const pins = new Map([
  ...base.entries.map(row => [row.path, { mode: row.mode, ...row.gitRaw }]),
  ...fixed.additions.map(row => [row.path, { mode: row.mode, bytes: row.bytes, sha256: row.sha256 }]),
]);
const baseNames = new Set(base.entries.map(row => row.path));
function record(value, keys) {
  assert.ok(value && typeof value === 'object' && !Array.isArray(value), 'Invalid caller snapshot record');
  assert.ok([Object.prototype, null].includes(Object.getPrototypeOf(value)), 'Invalid caller snapshot record');
  const descriptors = Object.getOwnPropertyDescriptors(value);
  assert.equal(Reflect.ownKeys(descriptors).length, keys.length, 'Invalid caller snapshot record');
  for (const key of keys) {
    const descriptor = descriptors[key];
    assert.ok(descriptor && Object.hasOwn(descriptor, 'value') && descriptor.enumerable, 'Invalid caller snapshot record');
  }
}
function assertWholeHistoricalPackagingAuthority(historicalMap) {
  assert.ok(historicalMap && typeof historicalMap === 'object' && !Array.isArray(historicalMap) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(historicalMap)), 'Invalid historical packaging map');
  const keys = Reflect.ownKeys(historicalMap);
  assert.equal(keys.length, fixed.callback.mapCount, 'Historical packaging map count changed');
  assert.ok(keys.every(key => typeof key === 'string'), 'Historical packaging record changed');
  const descriptors = Object.getOwnPropertyDescriptors(historicalMap);
  const pairs = keys.map(key => {
    const descriptor = descriptors[key];
    assert.ok(descriptor && Object.hasOwn(descriptor, 'value') && descriptor.enumerable &&
      typeof descriptor.value === 'string' && /^[a-f0-9]{64}$/.test(descriptor.value), 'Historical packaging record changed');
    return [key, descriptor.value];
  });
  assert.equal(digest(JSON.stringify(pairs)), fixed.callback.orderedMapSHA256, 'Historical packaging order or hash changed');
  // Independent fixed authority contains the same complete713 literal entries.
  assertHistoricalPackagingAuthority(fixed.callback.path, 0, historicalMap);
}
export function bindCurrentPackagingWorkerReader(snapshot, historicalMap) {
  // Whole ordered historical authority MUST precede snapshot access/current pins.
  assertWholeHistoricalPackagingAuthority(historicalMap);
  record(snapshot, ['publicCommit', 'representation', 'entries']);
  assert.equal(snapshot.publicCommit, fixed.publicCommit, 'Wrong fixed caller public checkpoint');
  assert.equal(snapshot.representation, 'gitRaw', 'Raw PUBLIC Git representation required');
  assert.ok(Array.isArray(snapshot.entries) && snapshot.entries.length === fixed.files, 'Complete caller public inventory required');
  const inputs = new Map();
  for (const entry of snapshot.entries) {
    record(entry, ['path', 'mode', 'bytes']);
    assert.ok(typeof entry.path === 'string' && pins.has(entry.path), 'Input outside fixed caller inventory');
    assert.ok(!inputs.has(entry.path), 'Duplicate caller public input');
    assert.ok(Buffer.isBuffer(entry.bytes), 'Raw Buffer required');
    const bytes = Buffer.from(entry.bytes), pin = pins.get(entry.path);
    assert.equal(entry.mode, pin.mode, 'Caller public mode changed: ' + entry.path);
    assert.equal(bytes.length, pin.bytes, 'Caller public size changed: ' + entry.path);
    assert.equal(digest(bytes), pin.sha256, 'Caller public bytes changed: ' + entry.path);
    inputs.set(entry.path, { path: entry.path, mode: entry.mode, bytes });
  }
  // Bind206 ONLY to its unchanged782 inputs, never relabel the one hundred eight later additions.
  const baseResult = classifyCurrentPackaging({
    publicCommit: fixed.basePublicCommit, representation: 'gitRaw',
    entries: [...inputs.values()].filter(row => baseNames.has(row.path)),
  });
  assert.equal(baseResult.files, fixed.baseFiles);
  const allowed = new Set(Object.keys(historicalMap));
  const check = name => assert.ok(typeof name === 'string' && allowed.has(name) && inputs.has(name), 'Input outside exact historical caller authority');
  return Object.freeze({
    receipt: Object.freeze({ publicCommit: fixed.publicCommit, representation: 'gitRaw', files: inputs.size, historicalKeys: allowed.size, scope: fixed.scope }),
    read(name) { check(name); return Buffer.from(inputs.get(name).bytes); },
    pin(name) { check(name); return Object.freeze({ ...pins.get(name) }); },
  });
}
