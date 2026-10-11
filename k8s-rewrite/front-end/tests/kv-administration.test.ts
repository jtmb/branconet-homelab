import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ADMIN_ACTIONS,
  AdministrationClient,
  AdminFailure,
  AdminCancelled,
  appendImpact,
  impactAcknowledgement,
  canAct,
  destroyBody,
  gcBody,
  pathConfirmation,
  type ImpactPage,
  type PathSnapshot,
} from "../src/components/secrets/kv-administration-model";
import { KV_ACTIONS } from "../src/lib/kv-contract";
import { historyGc, nativeDestroy, policyUpdate } from "../src/lib/kv-schemas";

const id = "11111111-1111-4111-8111-111111111111",
  mountId = "22222222-2222-4222-8222-222222222222";
const admin = {
  authenticated: true,
  username: "synthetic-operator",
  role: "write",
  engineAdmin: true,
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const snapshot: PathSnapshot = {
  path: {
    id,
    mountId,
    path: "apps/credentials",
    namespace: "apps",
    name: "original-secret",
    revision: 7,
    retention: 20,
    fields: [{ field: "user", key: "original_under_scored_key" }],
  },
  status: {
    pathId: id,
    resourceVersion: "captured-rv",
    head: 2,
    tombstone: false,
    adopted: true,
    versions: 2,
    guardedAdoption: true,
  },
  capabilities: {
    pathId: id,
    revision: 7,
    nativeMutationEnabled: true,
    permissions: { list: true, destroy: true, rotate: false, update: true },
  },
  versions: {
    pathId: id,
    resourceVersion: "captured-rv",
    head: 2,
    items: [
      { version: 1, createdAt: "2026-10-01T00:00:00Z", tombstone: false },
      { version: 2, createdAt: "2026-10-02T00:00:00Z", tombstone: false },
    ],
  },
};
const impact = (
  aliases: string[],
  cursor: string | null,
  count = 3,
  fingerprint = "a".repeat(64),
): ImpactPage => ({
  required: true,
  revision: 8,
  fingerprint,
  affectedAliasCount: count,
  nonsecretConfigurationAffected: true,
  nextCursor: cursor,
  items: aliases.map((alias) => ({
    alias,
    namespace: "apps",
    name: "original-secret",
    key: "original_under_scored_key",
    pathId: id,
    path: "apps/credentials",
    pathRevision: 7,
    mountRevision: 2,
    beforeAllowed: true,
    afterAllowed: false,
    basis: "registered-path-metadata",
  })),
});

test("admin action names and captured bodies match the real strict routes", () => {
  assert.deepEqual(ADMIN_ACTIONS, KV_ACTIONS);
  const body = destroyBody(snapshot, [1], pathConfirmation(snapshot));
  assert(nativeDestroy.safeParse(body).success);
  assert.equal(body.resourceVersion, "captured-rv");
  assert.equal(body.expectedHead, 2);
  assert.equal(body.pathRevision, snapshot.path.revision);
  assert(
    policyUpdate.safeParse({
      principal: "legacy-lookup",
      mountId,
      prefix: "apps",
      effect: "deny",
      actions: ["read"],
      revision: 4,
      legacyImpact: {
        fingerprint: "a".repeat(64),
        aliases: ["exact_under_scored_alias"],
        confirmLegacyImpact: true,
      },
    }).success,
  );
  assert(
    !nativeDestroy.safeParse({ ...body, uid: "invented-api-field" }).success,
  );
});

test("admin capability does not bypass a data deny, stale capability or guarded-mode disable", () => {
  assert.equal(canAct(snapshot, "rotate"), false);
  assert.equal(canAct(snapshot, "destroy"), true);
  assert.equal(
    canAct(
      { ...snapshot, capabilities: { ...snapshot.capabilities, revision: 6 } },
      "destroy",
    ),
    false,
  );
  assert.equal(
    canAct(
      {
        ...snapshot,
        capabilities: {
          ...snapshot.capabilities,
          nativeMutationEnabled: false,
        },
      },
      "destroy",
    ),
    false,
  );
  assert.equal(
    canAct(
      {
        ...snapshot,
        capabilities: {
          ...snapshot.capabilities,
          nativeMutationEnabled: false,
        },
      },
      "update",
      false,
    ),
    true,
  );
  assert.throws(
    () => destroyBody(snapshot, [2], pathConfirmation(snapshot)),
    /Tombstone/,
  );
  assert.throws(
    () => destroyBody(snapshot, [1], "apps/credentials"),
    /captured target/,
  );
  assert.throws(
    () => destroyBody(snapshot, [1, 1], pathConfirmation(snapshot)),
    /captured target/,
  );
  assert.throws(
    () => destroyBody(snapshot, [99], pathConfirmation(snapshot)),
    /captured target/,
  );
});

test("legacy acknowledgment requires every exact alias page and separate config acknowledgment", () => {
  const first = appendImpact(null, impact(["alias_a", "alias_b"], "alias_b"));
  assert(!first.complete);
  assert.throws(
    () => impactAcknowledgement(first, true, true),
    /every impact page/,
  );
  const complete = appendImpact(first, impact(["alias_c"], null));
  assert(complete.complete);
  assert.throws(
    () => impactAcknowledgement(complete, true, false),
    /every impact page/,
  );
  assert.deepEqual(impactAcknowledgement(complete, true, true), {
    fingerprint: "a".repeat(64),
    aliases: ["alias_a", "alias_b", "alias_c"],
    confirmLegacyImpact: true,
    confirmConfigurationImpact: true,
  });
  assert.throws(
    () => appendImpact(first, impact(["alias_c"], null, 3, "b".repeat(64))),
    /changed/,
  );
  assert.throws(
    () => appendImpact(first, impact(["alias_b"], null)),
    /paging changed/,
  );
  assert.throws(() => appendImpact(first, impact([], null)), /Incomplete/);
});

test("GC retains exact displayed UID/RV, source revision and age boundaries", () => {
  const candidate = {
    name: "kv-" + "1".repeat(32) + "-" + "2".repeat(24),
    uid: "owned-history-uid",
    resourceVersion: "history-rv",
  };
  const preview = {
    pathId: id,
    pathRevision: 7,
    resourceVersion: "captured-rv",
    expectedHead: 2,
    minimumAgeHours: 24,
    eligible: 1,
    retained: 2,
    complete: true,
    items: [candidate],
  };
  const body = gcBody(
    snapshot,
    preview,
    [candidate],
    pathConfirmation(snapshot),
  );
  assert(historyGc.safeParse(body).success);
  assert.deepEqual(body.histories, [candidate]);
  assert.throws(
    () =>
      gcBody(
        snapshot,
        { ...preview, pathRevision: 6 },
        [candidate],
        pathConfirmation(snapshot),
      ),
    /changed/,
  );
  assert.throws(
    () =>
      gcBody(
        snapshot,
        { ...preview, minimumAgeHours: 23 },
        [candidate],
        pathConfirmation(snapshot),
      ),
    /changed/,
  );
  assert.throws(
    () =>
      gcBody(
        snapshot,
        preview,
        [{ ...candidate, uid: "replacement-uid" }],
        pathConfirmation(snapshot),
      ),
    /changed/,
  );
  assert.throws(
    () =>
      gcBody(
        snapshot,
        preview,
        [{ ...candidate, resourceVersion: "later-rv" }],
        pathConfirmation(snapshot),
      ),
    /changed/,
  );
});

test("readonly, scoped human and token sessions cannot enter the administration mutation callback", async () => {
  for (const session of [
    { ...admin, role: "readonly" },
    { ...admin, engineAdmin: false },
    { authenticated: false },
  ]) {
    let invoked = false,
      lost = 0;
    const client = new AdministrationClient(
      (async () => json(session)) as typeof fetch,
      () => lost++,
    );
    await assert.rejects(
      client.run(async () => {
        invoked = true;
        return "must not issue";
      }),
      AdminFailure,
    );
    assert(!invoked);
    assert.equal(lost, 1);
  }
});

test("browser fetch retains its global receiver instead of the request-client instance", async () => {
  let requests = 0;
  const client = new AdministrationClient(async function (
    this: typeof globalThis,
  ) {
    assert.equal(this, globalThis);
    requests++;
    return json(admin);
  } as typeof fetch);
  const result = await client.run(async () => "safe metadata");
  assert.equal(result, "safe metadata");
  assert.equal(requests, 2);
});

test("a one-time token cannot be released after logout, role loss or account switch", async () => {
  for (const after of [
    { authenticated: false },
    { ...admin, engineAdmin: false },
    { ...admin, role: "readonly" },
    { ...admin, username: "another-account" },
  ]) {
    let sessions = 0,
      issues = 0,
      lost = 0;
    const client = new AdministrationClient(
      (async (url: string | URL | Request) => {
        if (String(url) === "/api/auth/session")
          return json(sessions++ === 0 ? admin : after);
        issues++;
        return json({ id, credential: "synthetic-token-never-release" });
      }) as typeof fetch,
      () => lost++,
    );
    await assert.rejects(
      client.run((request) =>
        request("/api/kv/identities", "POST", { synthetic: true }),
      ),
      AdminFailure,
    );
    assert.equal(issues, 1);
    assert.equal(sessions, 2);
    assert.equal(lost, 1);
  }
});

test("navigation/close fences an ignored-abort late one-time reveal", async () => {
  let release!: (value: Response) => void;
  const delayed = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const client = new AdministrationClient((async (
    url: string | URL | Request,
  ) =>
    String(url) === "/api/auth/session"
      ? json(admin)
      : delayed) as typeof fetch);
  const work = client.run((request) =>
    request("/api/kv/identities", "POST", { synthetic: true }),
  );
  await new Promise((resolve) => setImmediate(resolve));
  client.invalidate();
  release(json({ id, credential: "synthetic-late-token" }));
  await assert.rejects(work, AdminCancelled);
});

test("a deadline reports an unknown outcome instead of silently cancelling or repeating the mutation", async () => {
  let sent = 0;
  const client = new AdministrationClient(
    (async (url, init) => {
      if (String(url) === "/api/auth/session") return json(admin);
      sent++;
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          "abort",
          () => reject(new Error("synthetic-private-transport-body")),
          { once: true },
        );
      });
    }) as typeof fetch,
    () => {},
    5,
  );
  await assert.rejects(
    client.run((request) =>
      request("/api/kv/identities", "POST", { synthetic: true }),
    ),
    (failure: unknown) =>
      failure instanceof AdminFailure &&
      failure.status === 408 &&
      !failure.message.includes("synthetic-private"),
  );
  assert.equal(sent, 1);
});

test("stale/revoked mutations are sent once, fixed errors omit private bodies and preserve recovery metadata", async () => {
  let mutations = 0;
  const client = new AdministrationClient((async (
    url: string | URL | Request,
  ) => {
    if (String(url) === "/api/auth/session") return json(admin);
    mutations++;
    return json(
      {
        error: "synthetic-private-value",
        operationId: id,
        outcome: "recovery-required",
      },
      409,
    );
  }) as typeof fetch);
  await assert.rejects(
    client.run((request) =>
      request("/api/kv/policies/" + id, "PATCH", { revision: 5 }),
    ),
    (failure: unknown) => {
      assert(failure instanceof AdminFailure);
      assert.equal(failure.operationId, id);
      assert.equal(failure.outcome, "recovery-required");
      assert(!failure.message.includes("synthetic-private-value"));
      return true;
    },
  );
  assert.equal(mutations, 1);
});
