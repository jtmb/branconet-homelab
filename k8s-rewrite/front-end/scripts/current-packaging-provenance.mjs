import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { currentPackagingSource as fixed, historicalPackagingAuthorities as historical } from './current-packaging-source-manifest.mjs';

// This module has no filesystem, Git, process or historical-helper dependency.
// Every caller supplies a COMPLETE inventory; supplied bytes are never normalized.
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const pins = new Map(fixed.entries.map(row => [row.path, row]));
const callers = new Map(historical.callers.map(row => [row.path, row]));
const representations = new Set(Object.keys(fixed.representations));

function record(value, keys, message) {
  assert.ok(value !== null && typeof value === 'object' && !Array.isArray(value), message);
  assert.ok([Object.prototype, null].includes(Object.getPrototypeOf(value)), message);
  const descriptors = Object.getOwnPropertyDescriptors(value);
  assert.equal(Reflect.ownKeys(descriptors).length, keys.length, message);
  for (const key of keys) {
    const descriptor = descriptors[key];
    assert.ok(descriptor && Object.hasOwn(descriptor, 'value') && descriptor.enumerable, message);
  }
}

function representationPin(row, representation) {
  assert.ok(representations.has(representation), 'Unknown current packaging representation');
  const pin = row[representation];
  return Object.freeze({ mode: row.mode, bytes: pin.bytes, sha256: pin.sha256 });
}

export function assertHistoricalPackagingAuthority(caller, mapIndex, frozen) {
  const owner = callers.get(caller);
  assert.ok(owner && Number.isInteger(mapIndex) && mapIndex >= 0 && mapIndex < owner.maps.length, 'Unknown historical packaging authority');
  const expected = owner.maps[mapIndex];
  assert.ok(frozen !== null && typeof frozen === 'object' && !Array.isArray(frozen), 'Invalid historical packaging map');
  const keys = Reflect.ownKeys(frozen);
  assert.equal(keys.length, expected.count, 'Historical packaging map changed');
  assert.ok(keys.every(key => typeof key === 'string'), 'Historical packaging map changed');
  record(frozen, keys, 'Historical packaging map changed');
  const pairs = keys.map(key => {
    const value = Object.getOwnPropertyDescriptor(frozen, key).value;
    assert.ok(typeof value === 'string' && /^[a-f0-9]{64}$/.test(value), 'Historical packaging map changed');
    return [key, value];
  });
  assert.equal(digest(JSON.stringify(pairs)), expected.entriesSHA256, 'Historical packaging map changed');
  return true;
}

export function currentPackagingInputPin(caller, mapIndex, frozen, name, representation = 'gitRaw') {
  assertHistoricalPackagingAuthority(caller, mapIndex, frozen);
  assert.ok(typeof name === 'string' && Object.hasOwn(frozen, name) && pins.has(name), 'Input outside fixed historical authority');
  return representationPin(pins.get(name), representation);
}

// Resolve a whole preserved caller map after one authority check.
export function currentPackagingInputPins(caller, mapIndex, frozen, representation = 'gitRaw') {
  assertHistoricalPackagingAuthority(caller, mapIndex, frozen);
  assert.ok(representations.has(representation), 'Unknown current packaging representation');
  return Object.freeze(Object.fromEntries(Object.keys(frozen).map(name => {
    assert.ok(pins.has(name), 'Input outside fixed historical authority');
    return [name, representationPin(pins.get(name), representation)];
  })));
}

export function classifyCurrentPackaging(snapshot) {
  record(snapshot, ['publicCommit', 'representation', 'entries'], 'Invalid current packaging snapshot');
  assert.equal(snapshot.publicCommit, fixed.publicCommit, 'Wrong fixed public checkpoint');
  assert.ok(representations.has(snapshot.representation), 'Unknown current packaging representation');
  assert.ok(Array.isArray(snapshot.entries), 'Complete public inventory required');
  assert.equal(snapshot.entries.length, fixed.entries.length, 'Complete public inventory required');
  const seen = new Set();
  for (const input of snapshot.entries) {
    record(input, ['path', 'mode', 'bytes'], 'Invalid current packaging entry');
    assert.ok(typeof input.path === 'string' && pins.has(input.path), 'Input outside fixed public inventory');
    assert.ok(!seen.has(input.path), 'Duplicate public input');
    seen.add(input.path);
    const expected = representationPin(pins.get(input.path), snapshot.representation);
    assert.equal(input.mode, expected.mode, 'Public input mode changed: ' + input.path);
    assert.ok(Buffer.isBuffer(input.bytes), 'Raw Buffer required: ' + input.path);
    assert.equal(input.bytes.length, expected.bytes, 'Public input size changed: ' + input.path);
    assert.equal(digest(input.bytes), expected.sha256, 'Public input bytes changed: ' + input.path);
  }
  assert.equal(seen.size, fixed.entries.length, 'Complete public inventory required');
  return Object.freeze({
    publicCommit: fixed.publicCommit,
    frontendTree: fixed.frontendTree,
    representation: snapshot.representation,
    derivedProjection: snapshot.representation !== 'gitRaw',
    files: seen.size,
    scope: fixed.scope,
  });
}
