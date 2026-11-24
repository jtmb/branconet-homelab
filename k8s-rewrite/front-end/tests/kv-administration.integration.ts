import { test } from "node:test";
import assert from "node:assert/strict";
import { administrationFixture } from "./helpers/kv-administration-fixture";
import { administrationCleanupFault } from "./helpers/kv-administration-cleanup-fault";
import {
  AdministrationClient,
  AdminFailure,
  appendImpact,
  impactAcknowledgement,
  type ImpactPage,
  type ImpactSnapshot,
  type Policy,
  type Identity,
} from "../src/components/secrets/kv-administration-model";

test(
  "administration UI client uses actual HTTP CAS, full alias acknowledgments, one-time identity issue and fresh revocation",
  { timeout: 180000 },
  async () => {
    const fixture = await administrationFixture();
    try {
      const sent: string[] = [];
      const client = new AdministrationClient((async (url, init) => {
        sent.push((init?.method ?? "GET") + " " + url);
        return fixture.request(
          String(url),
          init?.method ?? "GET",
          init?.body ? JSON.parse(String(init.body)) : undefined,
        );
      }) as typeof fetch);
      const policy = fixture.policies[0];
      await fixture.db.kvPolicy.update({
        where: { id: policy.id },
        data: { revision: { increment: 1 } },
      });
      await assert.rejects(
        client.run((request) =>
          request(`/api/kv/policies/${policy.id}`, "PATCH", {
            principal: policy.principal,
            mountId: policy.mountId,
            prefix: policy.prefix,
            effect: "deny",
            actions: ["list"],
            revision: 1,
          }),
        ),
        (error: unknown) =>
          error instanceof AdminFailure && error.status === 409,
      );
      assert.equal(
        sent.filter((item) => item === "PATCH /api/kv/policies/" + policy.id)
          .length,
        1,
      );
      const updated = await client.run((request) =>
        request<Policy>(`/api/kv/policies/${policy.id}`, "PATCH", {
          principal: policy.principal,
          mountId: policy.mountId,
          prefix: policy.prefix,
          effect: "deny",
          actions: ["list"],
          revision: 2,
        }),
      );
      assert.equal(updated.revision, 3);
      const legacy = await fixture.checked(
        await fixture.request("/api/kv/legacy"),
      );
      let impact: ImpactSnapshot | null = null,
        cursor: string | undefined,
        pages = 0;
      do {
        const page: ImpactPage = await client.run((request) =>
          request<ImpactPage>("/api/kv/legacy/preview", "POST", {
            kind: "principal",
            enabled: false,
            revision: legacy.revision,
            ...(cursor ? { cursor } : {}),
          }),
        );
        impact = appendImpact(impact, page);
        cursor = page.nextCursor ?? undefined;
        pages++;
      } while (cursor);
      assert.equal(pages, 7);
      assert.equal(impact!.aliases.length, 603);
      assert(impact!.complete);
      assert.throws(
        () => impactAcknowledgement(impact, true, false),
        /configuration/,
      );
      const acknowledgment = impactAcknowledgement(impact, true, true);
      await fixture.db.kvServicePrincipal.update({
        where: { id: "legacy-lookup" },
        data: { revision: { increment: 1 } },
      });
      await assert.rejects(
        client.run((request) =>
          request("/api/kv/legacy", "PATCH", {
            enabled: false,
            revision: legacy.revision,
            legacyImpact: acknowledgment,
          }),
        ),
        (error: unknown) =>
          error instanceof AdminFailure && error.status === 409,
      );
      const identity = await client.run((request) =>
        request<Identity & { credential: string }>(
          "/api/kv/identities",
          "POST",
          {
            ownerId: fixture.owner.id,
            name: "ui_http_automation",
            expiresAt: new Date(Date.now() + 3600000).toISOString(),
            scopes: [
              {
                mountId: fixture.mount.id,
                prefix: fixture.registered.path,
                actions: ["list"],
              },
            ],
          },
        ),
      );
      assert.match(identity.credential, /^bortus_kv_v1_/);
      const listed = await fixture.checked(
        await fixture.request("/api/kv/identities"),
      );
      assert(!JSON.stringify(listed).includes(identity.credential));
      assert(!JSON.stringify(listed).includes("credentialHash"));
      const automate = () =>
        fetch(fixture.origin + "/api/kv/automation", {
          method: "POST",
          headers: {
            authorization: "Bearer " + identity.credential,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            operation: "status",
            pathId: fixture.registered.id,
          }),
          signal: AbortSignal.timeout(15000),
        });
      assert.equal((await automate()).status, 200);
      await client.run((request) =>
        request(`/api/kv/identities/${identity.id}`, "DELETE", { revision: identity.revision }),
      );
      assert.equal((await automate()).status, 401);
      const source = await fixture.checked(
        await fixture.request(`/api/kv/paths/${fixture.registered.id}/status`),
      );
      const versions = await fixture.checked(await fixture.request(`/api/kv/paths/${fixture.registered.id}/versions`));
      const selectedHistory = versions.items.find((row: { version: number }) => row.version === 2);
      const fault = await administrationCleanupFault(fixture.dir);
      try {
        const cleanup = await client.run((request) =>
          request<Record<string, any>>(
            `/api/kv/paths/${fixture.registered.id}/destroy`,
            "POST",
            {
              sourceUid: source.uid,
              histories: [{ version: 2, name: selectedHistory.name, uid: selectedHistory.uid }],
              resourceVersion: source.resourceVersion,
              expectedHead: source.head,
              confirmPath: fixture.registered.path,
              versions: [2],
            },
          ),
        );
        assert.equal(cleanup.outcome, "committed");
        assert.equal(cleanup.cleanupComplete, false);
        assert.equal(cleanup.cleanup.length, 1);
        assert.equal(cleanup.cleanup[0].outcome, "recovery-required");
        assert.equal(cleanup.cleanup[0].status, 503);
        assert.equal(fault.denied(), 1);
        assert(
          fixture.native.objects.has("history/" + cleanup.cleanup[0].name),
        );
        const versions = await fixture.checked(
          await fixture.request(
            `/api/kv/paths/${fixture.registered.id}/versions`,
          ),
        );
        assert(
          !versions.items.some((row: { version: number }) => row.version === 2),
        );
        assert.equal(versions.head, 3);
      } finally {
        await fault.close();
      }
      const canonical = fixture.native.objects.get("apps/original-secret")!;
      assert.equal(
        canonical.data?.unrelated,
        Buffer.from("synthetic-other-key-annotation-never-render").toString(
          "base64",
        ),
      );
      assert.equal(canonical.metadata?.labels?.original, "retained");
      assert.equal(
        canonical.metadata?.annotations?.[
          "kubectl.kubernetes.io/last-applied-configuration"
        ],
        "synthetic-other-key-annotation-never-render",
      );
      const writesBeforeRecovery = fixture.native.calls.filter(
        (call) => call.method !== "GET",
      ).length;
      const recovered = await client.run((request) =>
        request<{ outcome: string }>(
          `/api/kv/operations/${fixture.ambiguousOperationId}`,
        ),
      );
      assert.equal(recovered.outcome, "ambiguous");
      assert.equal(
        fixture.native.calls.filter((call) => call.method !== "GET").length,
        writesBeforeRecovery,
      );
      await fixture.control("withdraw-admin");
      let invoked = false;
      await assert.rejects(
        client.run(async () => {
          invoked = true;
          return "must not issue";
        }),
        AdminFailure,
      );
      assert(!invoked);
      const metadata = await fixture.checked(
        await fixture.request(`/api/kv/paths/${fixture.registered.id}/status`),
      );
      assert(!JSON.stringify(metadata).includes("synthetic-native"));
      const calls = fixture.native.calls;
      assert(calls.every((call) => !call.path.includes("production")));
    } finally {
      await fixture.close();
    }
  },
);
