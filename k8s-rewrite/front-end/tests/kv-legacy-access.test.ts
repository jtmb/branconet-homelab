import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, writeFile, rm, mkdir, cp, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient, type Prisma } from "@prisma/client";
import { AccountStore } from "../src/lib/account-store";
import { KvRegistry, type PolicyInput } from "../src/lib/kv-registry";
import { KvLegacyAccess, type LegacyAcknowledgement } from "../src/lib/kv-legacy-access";
import { KvNativeEngine } from "../src/lib/kv-native-engine";
import { KvError, kvConfig } from "../src/lib/kv-contract";
import { createSecretTransport } from "../src/lib/secret-client";
import { flatSecretGuard, requireLegacyPrincipal } from "../src/lib/secret-access";
import { SecretStore } from "../src/lib/cluster-secrets";
import { nativeTlsFixture } from "./helpers/native-tls";

const denied = (status: number) => (error: unknown) => error instanceof KvError && error.status === status;

test("legacy audit migration preserves old rows, accounts and exact grants without value ingestion", { timeout: 90000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-legacy-forward-")), url = "file:" + path.join(dir, "db.sqlite").replaceAll("\\", "/"), schema = path.join(dir, "schema.prisma");
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  const db = new PrismaClient({ datasources: { db: { url } } });
  try {
    const source = await readFile("prisma/schema.prisma", "utf8"); await writeFile(schema, source);
    await mkdir(path.join(dir, "migrations"));
    for (const migration of await readdir("prisma/migrations")) if (migration !== "20261010230000_legacy_access_audit") await cp(path.join("prisma/migrations", migration), path.join(dir, "migrations", migration), { recursive: true });
    const cli = path.resolve("node_modules/prisma/build/index.js");
    execFileSync(process.execPath, [cli, "migrate", "deploy", "--schema", schema], { env, stdio: "pipe" });
    await db.$executeRaw`INSERT INTO users (id,username,passwordHash,role,engineAdmin,sessionVersion,createdAt) VALUES ('old-user','old_user','synthetic-preserved-hash','write',true,7,'2026-10-01T00:00:00Z')`;
    await db.$executeRaw`INSERT INTO kv_audit (id,actorId,action,pathId,outcome,createdAt) VALUES ('old-audit','old-user','read','old-path','authorized','2026-10-01T00:00:00Z')`;
    await db.kvLegacyGrant.create({ data: { pathId: "old-path", alias: "original_under_scored_alias", namespace: "apps", name: "source", key: "under_scored_key" } });
    await cp("prisma/migrations/20261010230000_legacy_access_audit", path.join(dir, "migrations/20261010230000_legacy_access_audit"), { recursive: true });
    execFileSync(process.execPath, [cli, "migrate", "deploy", "--schema", schema], { env, stdio: "pipe" });
    const row = await db.kvAudit.findUniqueOrThrow({ where: { id: "old-audit" } });
    assert.equal(row.actorId, "old-user"); assert.equal(row.action, "read"); assert.equal(row.outcome, "authorized"); assert.equal(row.principal, null); assert.equal(row.alias, null); assert.equal(row.key, null);
    assert.equal((await db.user.findUniqueOrThrow({ where: { id: "old-user" } })).passwordHash, "synthetic-preserved-hash"); assert.equal((await db.user.findUniqueOrThrow({ where: { id: "old-user" } })).sessionVersion, 7);
    assert.equal((await db.kvLegacyGrant.findFirstOrThrow()).key, "under_scored_key"); assert.equal(await db.kvLegacyGrant.count(), 1);
    const diff = execFileSync(process.execPath, [cli, "migrate", "diff", "--from-url", url, "--to-schema-datamodel", schema, "--script"], { env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }); assert(diff.includes("empty migration"));
  } finally { await db.$disconnect(); assert.equal(path.dirname(path.resolve(dir)), path.resolve(tmpdir())); assert(path.basename(dir).startsWith("bortus-legacy-forward-")); await rm(dir, { recursive: true, force: true }); }
});

test("legacy administration acknowledges all 603 exact aliases across 12 namespaces and fences fresh metadata", { timeout: 90000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-legacy-access-")), url = "file:" + path.join(dir, "db.sqlite").replaceAll("\\", "/"), aliasFile = path.join(dir, "aliases.json");
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  const previousConfig = process.env.KUBECONFIG, previousAliases = process.env.BORTUS_SECRET_ALIASES_FILE;
  const db = new PrismaClient({ datasources: { db: { url } } }); let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  const marker = "SYNTHETIC_PRIVATE_LEGACY_VALUE";
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    native = await nativeTlsFixture(dir); process.env.KUBECONFIG = native.config; process.env.BORTUS_SECRET_ALIASES_FILE = aliasFile;
    const scopes = Array.from({ length: 18 }, (_, index) => "apps-" + index);
    const aliases = Array.from({ length: 603 }, (_, index) => ({ alias: "legacy/path-original_under_scored-" + index, namespace: scopes[index % 12], name: "imported", key: index % 2 ? "under_scored_key" : "constructor" }));
    const fileRows = aliases.slice(300); await writeFile(aliasFile, JSON.stringify(fileRows)); await db.secretReference.createMany({ data: aliases.slice(0, 300) });
    const accounts = new AccountStore(db), admin = await accounts.register({ username: "legacy_operator", passwordHash: "synthetic-hash" });
    const actor = { id: admin.id, sessionVersion: admin.sessionVersion }, registry = new KvRegistry(db, scopes, kvConfig({ BORTUS_HISTORY_NAMESPACE: "history", BORTUS_KV_GUARDED_ADOPTION: "true" }));
    const access = new KvLegacyAccess(registry), transport = createSecretTransport(), engine = new KvNativeEngine(registry, transport, () => registry.legacyAliases(db));
    const mount = await registry.createMount(actor, { name: "legacy", namespaces: scopes });
    const paths: { id: string }[] = [];
    for (let index = 0; index < 12; index++) {
      const registered = await registry.registerPath(actor, { mountId: mount.id, path: "services/imported/" + index, namespace: scopes[index], name: "imported", fields: [{ field: "user", key: "constructor" }, { field: "password", key: "under_scored_key" }] }); paths.push(registered);
      const source = native.seed(scopes[index], "imported", { constructor: Buffer.from(marker).toString("base64"), under_scored_key: Buffer.from(marker + "-password").toString("base64"), unrelated: Buffer.from(marker + "-other").toString("base64") });
      await engine.adopt(actor, registered.id, { resourceVersion: source.metadata!.resourceVersion, expectedHead: 0, legacyAliases: aliases.filter(ref => ref.namespace === scopes[index]).map(ref => ref.alias) });
    }
    assert.equal(await db.kvLegacyGrant.count(), 603); assert.equal((await access.state(actor)).revision, 13);
    const rule: PolicyInput = { principal: "legacy-lookup", mountId: mount.id, prefix: "services/imported", effect: "deny", actions: ["read"] };
    const allPreview = async () => {
      const rows: string[] = []; let cursor: string | undefined, fingerprint: string | undefined;
      do { const page = await registry.previewPolicy(actor, rule, undefined, undefined, cursor); assert(page.required); assert.equal(page.affectedAliasCount, 603); assert(page.items.length <= 100);
        if (fingerprint) assert.equal(page.fingerprint, fingerprint); fingerprint = page.fingerprint; rows.push(...page.items.map(item => item.alias)); cursor = page.nextCursor ?? undefined; assert(!JSON.stringify(page).includes(marker));
      } while (cursor);
      assert.equal(rows.length, 603); assert.equal(new Set(rows).size, 603); return { fingerprint: fingerprint!, aliases: rows, confirmLegacyImpact: true as const };
    };
    let acknowledgement: LegacyAcknowledgement;
    await t.test("seven bounded pages list the complete impact with no native requests or values", async () => {
      const before = native!.calls.length; acknowledgement = await allPreview(); assert.equal(native!.calls.length, before); assert.deepEqual([...acknowledgement.aliases].sort(), aliases.map(ref => ref.alias).sort());
      await assert.rejects(registry.savePolicy(actor, rule), denied(428));
      await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, { ...acknowledgement, aliases: acknowledgement.aliases.slice(1) }), denied(409));
      await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, { ...acknowledgement, aliases: [...acknowledgement.aliases, acknowledgement.aliases[0]] }), denied(400)); assert.equal(await db.kvPolicy.count({ where: { principal: "legacy-lookup" } }), 0);
    });
    await t.test("external alias and path/principal revisions invalidate old acknowledgements", async () => {
      const changed = fileRows.map(ref => ({ ...ref })); changed[0].key = changed[0].key === "constructor" ? "under_scored_key" : "constructor";
      await writeFile(aliasFile, JSON.stringify(changed)); await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, acknowledgement), denied(409)); await writeFile(aliasFile, JSON.stringify(fileRows));
      await db.kvPath.update({ where: { id: paths[0].id }, data: { revision: { increment: 1 } } });
      await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, acknowledgement), denied(409)); acknowledgement = await allPreview();
      await db.kvServicePrincipal.update({ where: { id: "legacy-lookup" }, data: { revision: { increment: 1 } } });
      await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, acknowledgement), denied(409)); acknowledgement = await allPreview();
    });
    await t.test("mount metadata revision changes invalidate the earlier impact fingerprint", async () => {
      try {
        const before = await registry.previewPolicy(actor, rule);
        await db.kvMount.update({ where: { id: mount.id }, data: { revision: { increment: 1 } } });
        const after = await registry.previewPolicy(actor, rule);
        assert.notEqual(after.fingerprint, before.fingerprint);
        await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, { ...acknowledgement, fingerprint: before.fingerprint! }), denied(409));
      } finally { acknowledgement = await allPreview(); }
    });
    await t.test("fresh mount scopes enter the fingerprint and exclude removed namespaces", async () => {
      try {
        const before = await registry.previewPolicy(actor, rule);
        await db.kvMount.update({ where: { id: mount.id }, data: { namespaces: JSON.stringify(scopes.slice(1)) } });
        const after = await registry.previewPolicy(actor, rule);
        assert.notEqual(after.fingerprint, before.fingerprint);
        const excluded = after.items.filter(row => row.namespace === scopes[0]); assert(excluded.length > 0);
        assert(excluded.every(row => row.basis === "outside-scope" && !row.beforeAllowed && !row.afterAllowed));
        await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, { ...acknowledgement, fingerprint: before.fingerprint! }), denied(409));
      } finally {
        await db.kvMount.update({ where: { id: mount.id }, data: { namespaces: JSON.stringify(scopes), revision: { increment: 1 } } });
        acknowledgement = await allPreview();
      }
    });
    await t.test("policy commits require exact acknowledgement; removal has its own fresh preview", async () => {
      const deniedRule = await registry.savePolicy(actor, rule, undefined, undefined, acknowledgement);
      const ref = aliases[0], store = new SecretStore(transport, scopes, flatSecretGuard(registry, transport, async () => null, ref.alias));
      await assert.rejects(store.read(ref), denied(403)); await assert.rejects(registry.deletePolicy(actor, deniedRule.id, deniedRule.revision), denied(428));
      const remove = await registry.previewPolicy(actor, null, deniedRule.id, deniedRule.revision);
      await registry.deletePolicy(actor, deniedRule.id, deniedRule.revision, { fingerprint: remove.fingerprint!, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true });
      assert.equal((await store.read(ref)).value, marker);
    });
    await t.test("moving a legacy deny to a human principal still requires its alias-impact acknowledgement", async () => {
      const preview = await registry.previewPolicy(actor, rule), deniedRule = await registry.savePolicy(actor, rule, undefined, undefined, { fingerprint: preview.fingerprint!, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true });
      const humanRule: PolicyInput = { ...rule, principal: "user:" + actor.id, effect: "allow" }, updatePreview = await registry.previewPolicy(actor, humanRule, deniedRule.id, deniedRule.revision);
      assert.equal(updatePreview.affectedAliasCount, 603); await assert.rejects(registry.savePolicy(actor, humanRule, deniedRule.id, deniedRule.revision), denied(428));
      const updated = await registry.savePolicy(actor, humanRule, deniedRule.id, deniedRule.revision, { fingerprint: updatePreview.fingerprint!, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true });
      assert.equal(await db.kvPolicy.count({ where: { principal: "legacy-lookup" } }), 0); await registry.deletePolicy(actor, updated.id, updated.revision);
    });
    await t.test("exact grant revocation and restore retain native objects and audit alias/key", async () => {
      const grant = await db.kvLegacyGrant.findFirstOrThrow(), state = await access.state(actor), change = { kind: "revoke" as const, grantId: grant.id, revision: state.revision };
      const before = native!.calls.length, preview = await access.preview(actor, change);
      assert.equal(preview.affectedAliasCount, 1); assert.equal(preview.selectedGrant!.id, grant.id); assert.equal(preview.selectedGrant!.key, grant.key);
      const ack = { fingerprint: preview.fingerprint, aliases: [grant.alias], confirmLegacyImpact: true as const };
      await access.commit(actor, { revision: change.revision, grantId: change.grantId, kind: "revoke" }, ack); assert.equal(native!.calls.length, before); assert.equal(await db.kvLegacyGrant.count(), 602);
      const ref = aliases.find(ref => ref.alias === grant.alias)!, store = new SecretStore(transport, scopes, flatSecretGuard(registry, transport, async () => null, ref.alias)); await assert.rejects(store.read(ref), denied(403));
      const currentPath = await registry.path(grant.pathId), restore = { kind: "grant" as const, pathId: grant.pathId, pathRevision: currentPath.revision, alias: grant.alias, revision: (await access.state(actor)).revision };
      const restorePreview = await access.preview(actor, { revision: restore.revision, alias: restore.alias, pathRevision: restore.pathRevision, pathId: restore.pathId, kind: "grant" }); assert.equal(restorePreview.items[0].beforeAllowed, false); assert.equal(restorePreview.items[0].afterAllowed, true);
      await access.commit(actor, restore, { fingerprint: restorePreview.fingerprint, aliases: [grant.alias], confirmLegacyImpact: true }); assert.equal(await db.kvLegacyGrant.count(), 603); assert.equal((await store.read(ref)).value, marker + (ref.key === "under_scored_key" ? "-password" : ""));
      const audit = await db.kvAudit.findFirstOrThrow({ where: { action: "legacy-revoke" } }); assert.equal(audit.alias, grant.alias); assert.equal(audit.key, grant.key); assert.equal(audit.principal, "legacy-lookup"); assert(!JSON.stringify(await db.kvAudit.findMany()).includes(marker));
    });
    await t.test("principal CAS acknowledges nonsecret configuration and invalidates earlier previews", async () => {
      const state = await access.state(actor), change = { kind: "principal" as const, enabled: false, revision: state.revision }, preview = await access.preview(actor, change);
      assert.equal(preview.affectedAliasCount, 603); assert.equal(preview.nonsecretConfigurationAffected, true);
      const ack = { fingerprint: preview.fingerprint, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true as const };
      await assert.rejects(access.commit(actor, change, ack), denied(400)); const before = native!.calls.length;
      await access.commit(actor, { revision: change.revision, enabled: change.enabled, kind: "principal" }, { ...ack, confirmConfigurationImpact: true }); assert.equal(native!.calls.length, before); await assert.rejects(requireLegacyPrincipal(registry), denied(403)); await assert.rejects(access.commit(actor, change, { ...ack, confirmConfigurationImpact: true }), denied(409));
      const enable = { kind: "principal" as const, enabled: true, revision: (await access.state(actor)).revision }, enablePreview = await access.preview(actor, enable);
      await access.commit(actor, enable, { fingerprint: enablePreview.fingerprint, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true, confirmConfigurationImpact: true }); await requireLegacyPrincipal(registry);
    });
    await t.test("concurrent principal changes have one winner and preserve revision CAS", async () => {
      const change = { kind: "principal" as const, enabled: false, revision: (await access.state(actor)).revision }, preview = await access.preview(actor, change);
      const ack = { fingerprint: preview.fingerprint, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true as const, confirmConfigurationImpact: true as const };
      const results = await Promise.allSettled([access.commit(actor, change, ack), access.commit(actor, change, ack)]);
      assert.equal(results.filter(result => result.status === "fulfilled").length, 1); const rejected = results.find(result => result.status === "rejected") as PromiseRejectedResult; assert(denied(409)(rejected.reason));
      const enable = { kind: "principal" as const, enabled: true, revision: (await access.state(actor)).revision }, enablePreview = await access.preview(actor, enable);
      await access.commit(actor, enable, { ...ack, fingerprint: enablePreview.fingerprint });
    });
    await t.test("fresh administrator withdrawal and unavailable aliases deny metadata changes", async () => {
      const preview = await registry.previewPolicy(actor, rule); await db.user.update({ where: { id: actor.id }, data: { engineAdmin: false } });
      await assert.rejects(registry.savePolicy(actor, rule, undefined, undefined, { fingerprint: preview.fingerprint!, aliases: aliases.map(ref => ref.alias), confirmLegacyImpact: true }), denied(403)); await assert.rejects(access.state(actor), denied(403));
      await db.user.update({ where: { id: actor.id }, data: { engineAdmin: true } });
      await writeFile(aliasFile, "invalid " + marker); await assert.rejects(registry.previewPolicy(actor, rule), error => error instanceof KvError && error.status === 503 && !error.message.includes(marker)); await writeFile(aliasFile, JSON.stringify(fileRows));
    });
    await t.test("audit failure rolls the grant and principal revision back atomically", async () => {
      const grant = await db.kvLegacyGrant.findFirstOrThrow(), state = await access.state(actor), change = { kind: "revoke" as const, grantId: grant.id, revision: state.revision }, preview = await access.preview(actor, change);
      const failedDb = new Proxy(db, { get(target, property) {
        if (property === "$transaction") return (callback: (client: Prisma.TransactionClient) => Promise<unknown>, options: object) => target.$transaction(tx => callback(new Proxy(tx, { get(client, field) { if (field === "kvAudit") return new Proxy(client.kvAudit, { get(delegate, method) { if (method === "create") return async () => { throw new Error(marker); }; return Reflect.get(delegate, method); } }); return Reflect.get(client, field); } })), options);
        return Reflect.get(target, property);
      } });
      const failed = new KvLegacyAccess(new KvRegistry(failedDb, scopes, registry.config));
      await assert.rejects(failed.commit(actor, change, { fingerprint: preview.fingerprint, aliases: [grant.alias], confirmLegacyImpact: true }), error => error instanceof KvError && error.status === 503 && !error.message.includes(marker));
      assert(await db.kvLegacyGrant.findUnique({ where: { id: grant.id } })); assert.equal((await access.state(actor)).revision, state.revision);
    });
    assert.equal(native.objects.size, 24); assert.equal(await db.kvLegacyGrant.count(), 603);
  } finally {
    await native?.close(); await db.$disconnect();
    if (previousConfig === undefined) delete process.env.KUBECONFIG; else process.env.KUBECONFIG = previousConfig;
    if (previousAliases === undefined) delete process.env.BORTUS_SECRET_ALIASES_FILE; else process.env.BORTUS_SECRET_ALIASES_FILE = previousAliases;
    assert.equal(path.dirname(path.resolve(dir)), path.resolve(tmpdir())); assert(path.basename(dir).startsWith("bortus-legacy-access-")); await rm(dir, { recursive: true, force: true });
  }
});
