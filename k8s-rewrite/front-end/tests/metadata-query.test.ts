import test from "node:test";
import assert from "node:assert/strict";
import { isSharedMetadataQuery } from "../src/lib/metadata-query";

const id = "20000000-0000-4000-8000-000000000000";
test("shared cache admits the existing metadata contracts and named KV reads", () => {
  for (const url of ["/api/auth/session", "/api/cluster/pods?namespace=apps", "/api/flux/repos", "/api/secrets?namespace=apps&name=example", "/api/deploy/history", "/api/kv/paths?mountId=" + id, "/api/kv/paths/" + id + "/versions"])
    assert.equal(isSharedMetadataQuery(url), true, url);
});
test("shared cache denies private requests even through normalized resource-prefix spellings", () => {
  for (const url of ["/api/kv/paths/" + id + "/data", "/api/cluster/../kv/paths/" + id + "/data", "/api/flux/../kv/operations/" + id,
    "/api/kv/mounts/../paths", "/api/cluster/../secrets?%6bey=value", "/api/flux/../deploy/history?jobId=value", "/api/cluster/pods/a/logs?tail=1", "/api/cluster/pods/a/yaml", "/api/cluster/pods/a/exec",
    "/api/cluster/pods/a/%79aml", "/api/flux/../kv/paths/" + id + "/%64ata", "/api/cluster/pods/a/%ZZ", "/api/vars/lookup?key=value", "https://example.invalid/api/kv/mounts", "/api/kv/import", "/api/kv/export"])
    assert.equal(isSharedMetadataQuery(url), false, url);
});
