import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// Two complete reviewed source lineages; mixed or unknown packaging refuses.
// Historical functional inputs keep their literal hashes in each caller.
const localPins = Object.freeze({
  ".dockerignore": "3e50275b9640a6f0ddd40e9b99c44b7af1fe0b136b2ff225f4d5c6956663fb28",
  "Dockerfile": "1aeb71c5b94b51dfffcb5593609194c010bfe353797389291f92076c546550ff",
  "Dockerfile.release": "ce4212677872de2dc354146d4f0a86ca43dac9503d6c2b6d6ca354bb08e6ce98",
  "src/app/(dashboard)/sidebar.tsx": "d219a5eb7e4ec36bc98c370ede03caff3bed7596d4e1eaa1b1d68859cbb2c5bc"
});
const publicPins = Object.freeze({
  ".dockerignore": "91bcd3d5dd7ae0043d81c43fdd4f8a5fde08f424712752288ed32f626940a9ba",
  "Dockerfile": "b442ae369248ecbcbf34b45fa3e05030477bfe03c0efa278028b7819405a3a66",
  "Dockerfile.release": "d2ce23628d68783ccd80de0adcc8ddbe7d26ea11f48b4c8c4d96c7cd9e6df69e",
  "src/app/(dashboard)/sidebar.tsx": "5afdb24bcc80b8bf468287b4aade8e082a2b8dbc1f21cea7603b771de56e072e"
});
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

export function packagingLineage(importer, reader = readFileSync) {
  const observed = Object.fromEntries(Object.keys(localPins).map(name =>
    [name, digest(reader(new URL('../' + name, importer)))]));
  const matches = [['local', localPins], ['public', publicPins]].filter(([, pins]) =>
    Object.keys(pins).every(name => observed[name] === pins[name]));
  assert.equal(matches.length, 1, 'Unknown or mixed packaging source lineage');
  return matches[0][0];
}

export function assertRawPackagingInputs(importer, frozen, reader = readFileSync) {
  const lineage = packagingLineage(importer, reader);
  const pins = lineage === 'public' ? publicPins : localPins;
  for (const [name, hash] of Object.entries(localPins)) {
    assert.equal(frozen[name], hash, 'Historical packaging authority: ' + name);
  }
  for (const [name, hash] of Object.entries(frozen)) {
    const expected = Object.hasOwn(pins, name) ? pins[name] : hash;
    assert.equal(digest(reader(new URL('../' + name, importer))), expected, name);
  }
}
