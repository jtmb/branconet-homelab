import test from "node:test";
import assert from "node:assert/strict";
import { isKvMetadataQuery } from "../src/lib/kv-metadata-query";
const path = "/api/kv/paths/11111111-1111-4111-8111-111111111111";
test("shared KV queries admit only exact read-only metadata routes and collection filters", () => {
  for (const url of ["/api/kv/mounts?cursor=abc", "/api/kv/paths?mountId=abc&cursor=def", "/api/kv/policies", "/api/kv/identities", "/api/kv/audit?pathId=abc&operationId=def", path, path + "/capabilities", path + "/status", path + "/versions"])
    assert.equal(isKvMetadataQuery(url), true, url);
  for (const url of [path + "/data", path + "/versions/1/data", path + "/adopt", path + "/rollback", "/api/kv/export", "/api/kv/import/preview", "/api/kv/automation", "/api/kv/operations/11111111-1111-4111-8111-111111111111", "/api/kv/history/gc/preview", "/api/kv/rotations"])
    assert.equal(isKvMetadataQuery(url), false, url);
});
test("KV metadata query spelling cannot smuggle private actions or unsupported parameters into cache", () => {
  for (const url of ["https://bortus.invalid/api/kv/mounts", "//bortus.invalid/api/kv/mounts", path + "/%64ata", path + "/versions?version=1", "/api/kv/paths?key=private", "/api/kv/mounts?cursor=a&cursor=b", "/api/kv/mounts#private", "/api/kv/mounts/", "/api/kv/paths/not-an-id/status"])
    assert.equal(isKvMetadataQuery(url), false, url);
});
