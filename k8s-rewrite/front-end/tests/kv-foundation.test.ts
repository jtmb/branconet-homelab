import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm, mkdir, readdir, readFile, writeFile, cp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { AccountStore, AccountError } from "../src/lib/account-store";
import { KvRegistry } from "../src/lib/kv-registry";
import { KV_ACTIONS, KvError, fieldMapping, kvConfig, logicalPath, policyAllows, requireGuarded } from "../src/lib/kv-contract";
import { presentedCredential } from "../src/lib/kv-credentials";
import { publicClusterMetadata } from "../src/lib/cluster-metadata";

const denied = (status: number) => (error: unknown) => error instanceof KvError && error.status === status;

test("resource metadata cannot reveal value-bearing annotations or workload env/arguments", () => {
  const marker = "synthetic-private-other-key";
  const projection = publicClusterMetadata({ deployment: { metadata: { name: "safe", annotations: { "last-applied": marker }, managedFields: [{ value: marker }], labels: { app: "safe" } }, spec: { template: { metadata: { annotations: { value: marker } }, spec: { containers: [{ name: "api", image: "example.invalid/api:v1", env: [{ name: "PASSWORD", value: marker }], args: [marker], command: [marker] }] } } }, status: { conditions: [{ type: "Ready", status: "False", reason: "Waiting", message: marker }] } } });
  assert(!JSON.stringify(projection).includes(marker));
  assert(JSON.stringify(projection).includes("example.invalid/api:v1") && JSON.stringify(projection).includes('"name":"safe"'));
});

test("canonical paths, complete prefix segments, deny override and guarded configuration", () => {
  for (const value of ["", "a//b", "a/./b", "a/../b", "a%2fb", "a%252fb", "a\\b", "a/", "/a", "a b", "caf\u0065\u0301/key", "a\ud800"])
    assert.throws(() => logicalPath(value), denied(400));
  assert.equal(logicalPath("apps/café/key"), "apps/café/key");
  const rule = { mountId: null, prefix: "apps/api", effect: "allow", actions: '["list","read"]' };
  assert(policyAllows([rule], { mountId: "mount", path: "apps/api/key" }, "read"));
  assert(!policyAllows([rule], { mountId: "mount", path: "apps/apiculture" }, "read"));
  assert(!policyAllows([rule, { ...rule, prefix: "apps/api/private", effect: "deny" }], { mountId: "mount", path: "apps/api/private/key" }, "read"));
  assert.throws(() => policyAllows([{ ...rule, actions: "invalid" }], { mountId: "mount", path: "apps/api/key" }, "read"), denied(503));
  assert.deepEqual(fieldMapping([{ field: "__proto__", key: "under_scored_key" }], "apps", "existing-name"), [{ field: "__proto__", key: "under_scored_key" }]);
  assert.throws(() => fieldMapping([{ field: "a", key: "same" }, { field: "b", key: "same" }], "apps", "existing-name"), denied(400));
  assert.equal(kvConfig({}).guardedAdoption, false);
  assert.throws(() => requireGuarded(kvConfig({})), denied(403));
  assert.equal(kvConfig({ BORTUS_KV_GUARDED_ADOPTION: "true" }).guardedAdoption, true); // Flag assertion only; no admission/RBAC proof.
  for (const env of [{ BORTUS_KV_RETENTION: "0" }, { BORTUS_KV_RETENTION: "101" }, { BORTUS_KV_RETENTION: "2.5" }, { BORTUS_KV_RETENTION: "20", BORTUS_KV_MAX_RETENTION: "10" }, { BORTUS_KV_GUARDED_ADOPTION: "yes" }])
    assert.throws(() => kvConfig(env), denied(503));
});

test("forward KV migration preserves existing users and native references without value ingestion", { timeout: 90000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-kv-migration-"));
  const url = `file:${path.join(dir, "test.db").replaceAll("\\", "/")}`, schema = path.join(dir, "schema.prisma");
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  let db: PrismaClient | undefined;
  try {
    const current = await readFile("prisma/schema.prisma", "utf8");
    const old = current.replace(/^  engineAdmin.*\r?\n/m, "").replace(/\/\/ KV tables contain metadata only\.[\s\S]*?(?=model Node)/, "");
    await writeFile(schema, old);
    await mkdir(path.join(dir, "migrations"));
    for (const file of await readdir("prisma/migrations")) if (file !== "20261010210000_kv_metadata")
      await cp(path.join("prisma/migrations", file), path.join(dir, "migrations", file), { recursive: true });
    const cli = path.resolve("node_modules/prisma/build/index.js");
    execFileSync(process.execPath, [cli, "migrate", "deploy", "--schema", schema], { env, stdio: "pipe" });
    db = new PrismaClient({ datasources: { db: { url } } });
    await db.$executeRaw`INSERT INTO users (id, username, passwordHash, role, sessionVersion, createdAt) VALUES ('old-writer', 'old_writer', 'fixture-preserved-hash', 'write', 7, '2026-10-01T00:00:00Z'), ('old-reader', 'old_reader', 'fixture-reader-hash', 'readonly', 0, '2026-10-01T00:00:00Z')`;
    await db.secretReference.create({ data: { alias: "secret_original_underscored_key", namespace: "apps", name: "imported", key: "under_scored_key" } });
    await db.variable.create({ data: { key: "legacy_password", value: "synthetic-quarantined-only", encrypted: true, category: "secret" } });
    await cp("prisma/migrations/20261010210000_kv_metadata", path.join(dir, "migrations/20261010210000_kv_metadata"), { recursive: true });
    await writeFile(schema, current);
    execFileSync(process.execPath, [cli, "migrate", "deploy", "--schema", schema], { env, stdio: "pipe" });
    const user = await db.user.findUniqueOrThrow({ where: { id: "old-writer" } });
    assert.equal(user.passwordHash, "fixture-preserved-hash"); assert.equal(user.sessionVersion, 7); assert.equal(user.engineAdmin, true);
    assert.equal((await db.user.findUniqueOrThrow({ where: { id: "old-reader" } })).engineAdmin, false);
    const grants = await db.kvPolicy.findMany();
    assert.deepEqual(JSON.parse(grants.find(p => p.principal === "user:old-writer")!.actions), [...KV_ACTIONS]);
    assert.deepEqual(JSON.parse(grants.find(p => p.principal === "user:old-reader")!.actions), ["list"]);
    assert.equal(await db.secretReference.count(), 1); assert.equal((await db.secretReference.findFirstOrThrow()).key, "under_scored_key");
    assert.equal(await db.kvPath.count(), 0); assert.equal(await db.kvAudit.count(), 0); assert.equal(await db.kvIdentity.count(), 0);
    const diff = execFileSync(process.execPath, [cli, "migrate", "diff", "--from-url", url, "--to-schema-datamodel", schema, "--script"], { env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    assert(diff.includes("empty migration"));
  } finally { await db?.$disconnect(); await rm(dir, { recursive: true, force: true }); }
});

test("KV metadata ownership, serialized administration and scoped token lifecycle", { timeout: 90000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-kv-registry-"));
  const url = `file:${path.join(dir, "test.db").replaceAll("\\", "/")}`, env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  const oldRegistration = process.env.ALLOW_REGISTRATION;
  process.env.ALLOW_REGISTRATION = "false";
  const clients = [0, 1].map(() => new PrismaClient({ datasources: { db: { url } } }));
  const [db] = clients, stores = clients.map(client => new AccountStore(client)), registries = clients.map(client => new KvRegistry(client, ["apps", "other", "bortus-history"], kvConfig({})));
  const [registry] = registries;
  const actor = (user: { id: string; sessionVersion: number }) => ({ id: user.id, sessionVersion: user.sessionVersion });
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    const admin = await stores[0].register({ username: "operator", passwordHash: "fixture-hash" }), adminActor = actor(admin);
    const scoped = await stores[0].create(adminActor, { username: "scoped", passwordHash: "fixture-scoped-hash", role: "write" }), scopedUser = await db.user.findUniqueOrThrow({ where: { id: scoped.id } }), scopedActor = actor(scopedUser);
    const broad = await stores[0].create(adminActor, { username: "broad", passwordHash: "fixture-broad-hash", role: "write" });
    const reader = await stores[0].create(adminActor, { username: "reader", passwordHash: "fixture-reader-hash", role: "readonly" }), readerUser = await db.user.findUniqueOrThrow({ where: { id: reader.id } });
    const mount = await registry.createMount(adminActor, { name: "applications", namespaces: ["apps"] });
    const scope = { mountId: mount.id, path: "apps/api/key" };
    await registry.savePolicy(adminActor, { principal: `user:${scoped.id}`, mountId: mount.id, prefix: "apps/api", effect: "allow", actions: ["list", "read", "create", "update"] });
    await registry.savePolicy(adminActor, { principal: `user:${broad.id}`, mountId: null, prefix: "", effect: "allow", actions: [...KV_ACTIONS] });

    await t.test("scoped writers cannot reset, promote, create or delete peer identities regardless of flag", async () => {
      assert.equal(scopedUser.engineAdmin, false); assert.equal(admin.engineAdmin, true);
      for (const target of [admin.id, broad.id]) {
        for (const input of [{ passwordHash: "replacement" }, { role: "readonly" as const }, { engineAdmin: true }])
          await assert.rejects(stores[1].update(scopedActor, target, input), (e: unknown) => e instanceof AccountError && e.status === 403);
        await assert.rejects(stores[1].delete(scopedActor, target), (e: unknown) => e instanceof AccountError && e.status === 403);
      }
      await assert.rejects(stores[1].create(scopedActor, { username: "forbidden", passwordHash: "unused", role: "write" }), (e: unknown) => e instanceof AccountError && e.status === 403);
      assert.equal((await db.user.findUniqueOrThrow({ where: { id: broad.id } })).passwordHash, "fixture-broad-hash");
    });

    await t.test("mount scopes, metadata CAS and concurrent selected-key ownership", async () => {
      await assert.rejects(registry.createMount(scopedActor, { name: "forbidden", namespaces: ["apps"] }), denied(403));
      await assert.rejects(registry.createMount(adminActor, { name: "forbidden", namespaces: ["not-allowed"] }), denied(403));
      await assert.rejects(registry.createMount(adminActor, { name: "history", namespaces: ["bortus-history"] }), denied(403));
      const result = await Promise.allSettled(registries.map((r, index) => r.registerPath(scopedActor, { ...scope, path: `apps/api/credential-${index}`, namespace: "apps", name: "original", fields: [{ field: "password", key: "under_scored_key" }] })));
      assert.equal(result.filter(r => r.status === "fulfilled").length, 1);
      for (const item of result) if (item.status === "rejected") assert(denied(409)(item.reason));
      await registry.registerPath(scopedActor, { ...scope, path: "apps/api/sibling", namespace: "apps", name: "original", fields: [{ field: "binary", key: "another-key" }] });
      await assert.rejects(registry.registerPath(scopedActor, { ...scope, path: "apps/apiculture/key", namespace: "apps", name: "original", fields: [{ field: "x", key: "x" }] }), denied(403));
      await assert.rejects(registry.changeMount(adminActor, mount.id, undefined, { name: "renamed" }), denied(428));
      await assert.rejects(registry.changeMount(adminActor, mount.id, mount.revision, { namespaces: ["other"] }), denied(409));
      const changed = await registry.changeMount(adminActor, mount.id, mount.revision, { name: "renamed" }); assert.equal(changed!.revision, 2);
      await assert.rejects(registry.changeMount(adminActor, mount.id, mount.revision, null), denied(409));
      await assert.rejects(registry.changeMount(adminActor, mount.id, 2, null), denied(409));
    });

    await t.test("readonly has metadata only even when a policy mistakenly grants values", async () => {
      await registry.savePolicy(adminActor, { principal: `user:${reader.id}`, mountId: mount.id, prefix: "", effect: "allow", actions: [...KV_ACTIONS] });
      assert.equal((await registry.listPaths(actor(readerUser), mount.id)).items.length, 2);
      await assert.rejects(registry.authorize(actor(readerUser), scope, "read"), denied(403));
      await assert.rejects(registry.authorize(actor(readerUser), scope, "update"), denied(403));
    });

    await t.test("deny overrides user/admin allow and applies to complete path segments", async () => {
      await registry.authorize(scopedActor, scope, "read");
      const deny = await registry.savePolicy(adminActor, { principal: `user:${scoped.id}`, mountId: mount.id, prefix: "apps/api", effect: "deny", actions: ["read"] });
      await assert.rejects(registry.authorize(scopedActor, scope, "read"), denied(403));
      await registry.deletePolicy(adminActor, deny.id, deny.revision);
      const adminDeny = await registry.savePolicy(adminActor, { principal: `user:${admin.id}`, mountId: mount.id, prefix: "apps/api", effect: "deny", actions: ["read"] });
      await assert.rejects(registry.authorize(adminActor, scope, "read"), denied(403));
      await registry.admin(adminActor); // Metadata administration can repair a denied value grant.
      await registry.deletePolicy(adminActor, adminDeny.id, adminDeny.revision);
    });

    await t.test("audit pages and capabilities obey fresh scoped/readonly policy and administrator revocation", async () => {
      const initialMetadataGrant=await db.kvPolicy.findFirstOrThrow({where:{principal:"user:"+scoped.id,mountId:null,prefix:"",actions:'["list"]'}});
      await registry.deletePolicy(adminActor,initialMetadataGrant.id,initialMetadataGrant.revision); // Replace bootstrap metadata breadth with this fixture's explicit prefix scope.
      const p=(await registry.listPaths(scopedActor,mount.id)).items[0];
      const scopedCaps=await registry.capabilities(scopedActor,p.id);assert.equal(scopedCaps.permissions.read,true);assert.equal(scopedCaps.permissions.destroy,false);assert.equal(scopedCaps.initializationAllowed,false);
      const readerCaps=await registry.capabilities(actor(readerUser),p.id);assert.equal(readerCaps.permissions.list,true);assert.equal(readerCaps.permissions.read,false);assert.equal(readerCaps.permissions.update,false);
      await db.kvAudit.createMany({data:Array.from({length:205},()=>({actorId:scoped.id,pathId:p.id,mountId:mount.id,path:p.path,namespace:"apps",name:p.name,action:"synthetic-update",previousVersion:1,newVersion:2,outcome:"committed"}))});
      await db.kvAudit.create({data:{actorId:admin.id,mountId:mount.id,path:"other/private",namespace:"apps",name:"private",action:"synthetic-private",outcome:"committed"}});
      let cursor:string|undefined,seen=0;const ids=new Set<string>();
      do {const page=await registry.listAudit(scopedActor,{cursor});assert(page.items.length<=100);for(const row of page.items){assert(row.path==="apps/api"||row.path?.startsWith("apps/api/"));assert(!ids.has(row.id));ids.add(row.id);}seen+=page.items.length;cursor=page.nextCursor??undefined;}while(cursor);
      assert(seen>=205);
      const deny=await registry.savePolicy(adminActor,{principal:"user:"+scoped.id,mountId:mount.id,prefix:p.path,effect:"deny",actions:["list"]});
      await assert.rejects(registry.capabilities(scopedActor,p.id),denied(403));
      assert(!(await registry.listAudit(scopedActor,{})).items.some(row=>row.pathId===p.id));await registry.deletePolicy(adminActor,deny.id,deny.revision);
      const changedDb={user:db.user,kvPolicy:db.kvPolicy,kvAudit:{findMany:async(input:any)=>{const rows=await db.kvAudit.findMany(input);await db.user.update({where:{id:admin.id},data:{engineAdmin:false}});return rows;}}} as unknown as PrismaClient;
      try {await assert.rejects(new KvRegistry(changedDb,registry.namespaces,registry.config).listAudit(adminActor,{}),denied(403));}
      finally {await db.user.update({where:{id:admin.id},data:{engineAdmin:true}});}
    });

    await t.test("one-time token/hash projection, distinct audience and owner-policy intersection", async () => {
      const issue = () => registry.issueIdentity(scopedActor, { ownerId: scoped.id, name: "consumer", expiresAt: new Date(Date.now() + 3600000), scopes: [{ mountId: mount.id, prefix: "apps/api", actions: ["read", "destroy"] }] });
      const issued = await issue();
      const tokenActor = await registry.authenticateIdentity("Bearer " + issued.credential);
      assert(presentedCredential("Bearer " + issued.credential)); assert.equal(presentedCredential("Bearer fake-lookup-token"), null); assert.equal(presentedCredential("Bearer eyJ.fixture.jwt"), null);
      await registry.authorize(tokenActor, scope, "read");
      await assert.rejects(registry.authorize(tokenActor, scope, "destroy"), denied(403));
      await assert.rejects(registry.authorize(tokenActor, { ...scope, path: "apps/apiculture/key" }, "read"), denied(403));
      await assert.rejects(registry.admin(tokenActor), denied(403));
      const row = await db.kvIdentity.findUniqueOrThrow({ where: { id: issued.id } });
      assert.equal(row.credentialHash.length, 64); assert(!JSON.stringify(row).includes(issued.credential));
      const listing = await registry.listIdentities(scopedActor);
      assert(!JSON.stringify(listing).includes(issued.credential)); assert(!JSON.stringify(listing).includes(row.credentialHash));
      const audit = await db.kvAudit.findMany(); assert(!JSON.stringify(audit).includes(issued.credential) && !JSON.stringify(audit).includes(row.credentialHash));
      await registry.revokeIdentity(scopedActor, issued.id);
      await assert.rejects(registry.authenticateIdentity("Bearer " + issued.credential), denied(401));
      const expired = await issue(); await db.kvIdentity.update({ where: { id: expired.id }, data: { expiresAt: new Date(0) } });
      await assert.rejects(registry.authenticateIdentity("Bearer " + expired.credential), denied(401));
      await assert.rejects(registry.issueIdentity(scopedActor, { ownerId: scoped.id, name: "overlong", expiresAt: new Date(Date.now() + 31 * 86400000), scopes: [{ mountId: mount.id, prefix: "", actions: ["read"] }] }), denied(400));
      const reset = await issue(); await stores[0].update(scopedActor, scoped.id, { passwordHash: "fixture-new-self-password" });
      await assert.rejects(registry.authenticateIdentity("Bearer " + reset.credential), denied(401));
      const refreshed = actor(await db.user.findUniqueOrThrow({ where: { id: scoped.id } }));
      const demoted = await registry.issueIdentity(refreshed, { ownerId: scoped.id, name: "demoted", expiresAt: new Date(Date.now() + 3600000), scopes: [{ mountId: mount.id, prefix: "", actions: ["read"] }] });
      await stores[0].update(adminActor, scoped.id, { role: "readonly" });
      await assert.rejects(registry.authenticateIdentity("Bearer " + demoted.credential), denied(401));
      await stores[0].delete(adminActor, scoped.id);
      await assert.rejects(registry.authenticateIdentity("Bearer " + demoted.credential), denied(401));
    });

    await t.test("concurrent flag removal preserves the last effective admin while a nonadmin writer remains", async () => {
      await stores[0].update(adminActor, broad.id, { engineAdmin: true });
      const broadActor = actor(await db.user.findUniqueOrThrow({ where: { id: broad.id } }));
      const attempts = await Promise.allSettled([stores[0].update(adminActor, broad.id, { engineAdmin: false }), stores[1].update(broadActor, admin.id, { engineAdmin: false })]);
      assert.equal(attempts.filter(r => r.status === "fulfilled").length, 1);
      assert.equal(await db.user.count({ where: { role: "write", engineAdmin: true } }), 1);
      assert.equal(await db.user.count({ where: { role: "write" } }), 2);
    });
  } finally {
    if (oldRegistration === undefined) delete process.env.ALLOW_REGISTRATION; else process.env.ALLOW_REGISTRATION = oldRegistration;
    await Promise.all(clients.map(client => client.$disconnect())); await rm(dir, { recursive: true, force: true });
  }
});
