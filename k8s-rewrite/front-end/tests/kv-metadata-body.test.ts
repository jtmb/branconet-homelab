import assert from "node:assert/strict";
import { test } from "node:test";
import { kvAdminMetadataBody, kvBody } from "../src/lib/kv-http";
import { KV_ADMIN_METADATA_BODY_BYTES, KV_BODY_BYTES, KvError } from "../src/lib/kv-contract";
import type { KvRegistry } from "../src/lib/kv-registry";
import { policyCreateRequest } from "../src/lib/kv-schemas";

const actor = { id: "synthetic-body-reader", sessionVersion: 0 };
const denied = (status: number) => (error: unknown) => error instanceof KvError && error.status === status;
const registry = (admin: () => Promise<unknown>) => ({ admin }) as unknown as KvRegistry;
const policy = { principal: "legacy-lookup", mountId: null, prefix: "service", effect: "deny", actions: ["read"] };

test("large metadata reader checks fresh administration before touching headers or body", async () => {
  let reads = 0, checks = 0;
  const unread = {
    get headers() { reads++; throw Error("Headers must remain unread"); },
    get body() { reads++; throw Error("Body must remain unread"); },
  } as unknown as Request;
  await assert.rejects(kvAdminMetadataBody(registry(async () => { checks++; throw new KvError(403, "Administration withdrawn"); }), actor, unread, policyCreateRequest), denied(403));
  assert.equal(checks, 1); assert.equal(reads, 0);
});

test("complete maximum-length alias metadata fits only the scoped larger reader and still uses strict schemas", async () => {
  const aliases = Array.from({ length: 10000 }, (_, i) => "secret_" + String(i).padStart(5, "0") + "_" + "x".repeat(240));
  const body = JSON.stringify({ ...policy, legacyImpact: { fingerprint: "a".repeat(64), aliases, confirmLegacyImpact: true } });
  assert(aliases.every(alias => alias.length === 253));
  assert(Buffer.byteLength(body) > KV_BODY_BYTES && Buffer.byteLength(body) < KV_ADMIN_METADATA_BODY_BYTES);
  const request = (extra = "") => new Request("https://synthetic.invalid/metadata", { method: "POST", headers: { "Content-Type": "application/json" }, body: extra || body });
  await assert.rejects(kvBody(request(), policyCreateRequest), denied(413));
  let checks = 0;
  const admin = registry(async () => { checks++; });
  const accepted = await kvAdminMetadataBody(admin, actor, request(), policyCreateRequest);
  assert.deepEqual(accepted.legacyImpact!.aliases, aliases); assert.equal(checks, 1);
  await assert.rejects(kvAdminMetadataBody(admin, actor, request(JSON.stringify({ ...JSON.parse(body), fields: [{ value: "synthetic-unaccepted-field" }] })), policyCreateRequest), denied(400));
});

test("larger metadata envelope retains byte and fragmentation limits", async () => {
  const admin = registry(async () => {});
  const oversized = new Request("https://synthetic.invalid/metadata", { method: "POST", headers: { "Content-Type": "application/json", "Content-Length": String(KV_ADMIN_METADATA_BODY_BYTES + 1) }, body: "{}" });
  await assert.rejects(kvAdminMetadataBody(admin, actor, oversized, policyCreateRequest), denied(413));
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < 4097; i++) controller.enqueue(new Uint8Array([32]));
      controller.enqueue(new TextEncoder().encode(JSON.stringify(policy))); controller.close();
    },
    cancel() { cancelled = true; },
  });
  const fragmented = new Request("https://synthetic.invalid/metadata", { method: "POST", headers: { "Content-Type": "application/json" }, body, duplex: "half" } as RequestInit);
  await assert.rejects(kvAdminMetadataBody(admin, actor, fragmented, policyCreateRequest), denied(413));
  assert.equal(cancelled, true);
});
