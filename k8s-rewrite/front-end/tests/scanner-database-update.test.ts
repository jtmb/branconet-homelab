import { test } from "node:test";
import assert from "node:assert/strict";
const pins = { version: "0.76.1", archiveSHA256: "preserve-reviewed-binary", databaseRepository: "aquasecurity/trivy-db" };
const manifest = () => ({ schemaVersion: 2, layers: [{ digest: "sha256:" + "a".repeat(64), size: 1024, mediaType: "application/vnd.aquasec.trivy.db.layer.v1.tar+gzip" }] });
test("database update proposes only reviewed lock fields and preserves binary pins", async () => {
  const { databaseCandidate } = await import("../scripts/update-scanner-database.mjs");
  const candidate = databaseCandidate(pins, Buffer.from(JSON.stringify(manifest())), new Date("2026-10-25T00:00:00Z"));
  assert.equal(candidate.version, pins.version); assert.equal(candidate.archiveSHA256, pins.archiveSHA256);
  assert.match(candidate.databaseManifest, /^sha256:[a-f0-9]{64}$/); assert.equal(candidate.databaseLayerBytes, 1024);
  assert.equal(Object.hasOwn(pins, "databaseManifest"), false, "proposal must not mutate original lock");
});
test("database update refuses alternate repository, multi-layer, malformed or oversized input", async () => {
  const { databaseCandidate } = await import("../scripts/update-scanner-database.mjs");
  const input = manifest();
  assert.throws(() => databaseCandidate({ ...pins, databaseRepository: "other/private" }, Buffer.from(JSON.stringify(input))));
  input.layers[0].size = 300 * 1024 * 1024; assert.throws(() => databaseCandidate(pins, Buffer.from(JSON.stringify(input))));
  input.layers = []; assert.throws(() => databaseCandidate(pins, Buffer.from(JSON.stringify(input))));
  assert.throws(() => databaseCandidate(pins, Buffer.alloc(65537)));
});
