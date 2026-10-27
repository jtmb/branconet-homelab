import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { z } from "zod/v3";

// PUBLIC synthetic source controls only. Actual selected TS/TSX declarations run
// against transactional/HTTP/hook doubles. No Prisma, native client, server,
// credential issuance, process/transport or recovery module can be loaded.
type Row = Record<string, any>;
const front = process.cwd();
const source = (file: string) => readFileSync(path.join(front, file), "utf8");
const plain = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const transpile = (text: string, filename: string) => ts.transpileModule(text, {
  fileName: filename, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  },
}).outputText;
class SecretError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}
const forbidden = () => { throw new Error("Outside public source-control scope"); };
const cluster = { SecretError, validateTarget: forbidden };
function evaluate(text: string, filename: string, dependencies: Row, globals: Row = {}) {
  const compiledModule = { exports: {} as any };
  runInNewContext(transpile(text, filename), {
    module: compiledModule, exports: compiledModule.exports,
    require: (name: string) => {
      assert(Object.hasOwn(dependencies, name), `Unselected dependency: ${name}`);
      return dependencies[name];
    },
    Buffer, Date, JSON, TextDecoder, Uint8Array, URL, setTimeout, clearTimeout,
    process: { env: {} }, ...globals,
  }, { filename, timeout: 5000 });
  return compiledModule.exports;
}
const contract = evaluate(source("src/lib/kv-contract.ts"), "kv-contract.ts", { "./cluster-secrets": cluster });
const revisionModule = evaluate(source("src/lib/kv-identity-revision.ts"), "kv-identity-revision.ts", {
  "node:crypto": { createHash }, "./kv-contract": contract,
});
const model = evaluate(source("src/components/secrets/kv-administration-model.ts"), "kv-administration-model.ts", {}, { AbortController });
const schemas = evaluate(source("src/lib/kv-schemas.ts"), "kv-schemas.ts", { zod: { z }, "./kv-contract": contract });
const { KvRegistry } = evaluate(source("src/lib/kv-registry.ts"), "kv-registry.ts", {
  "./kv-contract": contract, "./cluster-secrets": cluster, "./kv-identity-revision": revisionModule,
  "./kv-credentials": { issueCredential: () => ({ id: "public-issued", credential: "NONCREDENTIAL-PUBLIC-ISSUE", hash: "PUBLIC-HASH-DOUBLE" }), hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(key => [key, forbidden])),
});
const parsedHttp = ts.createSourceFile("kv-http.ts", source("src/lib/kv-http.ts"), ts.ScriptTarget.Latest, true);
const bodyDeclaration = parsedHttp.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === "kvBody");
assert(bodyDeclaration);
const { kvBody } = evaluate(bodyDeclaration.getText(parsedHttp), "selected-kvBody.ts", {}, { KvError: contract.KvError, KV_BODY_BYTES: contract.KV_BODY_BYTES });
const route = evaluate(source("src/app/api/kv/identities/[id]/route.ts"), "identity-delete-route.ts", {
  "@/lib/kv-http": { kvHuman: (operation: unknown) => operation, kvBody },
  "@/lib/kv-schemas": schemas,
}).DELETE;
const snapshot = () => ({
  id: "public-identity", ownerId: "public-owner", ownerSessionVersion: 7,
  name: "public-name", expiresAt: new Date("2099-01-01T00:00:00.000Z"), revokedAt: null,
  createdAt: new Date("2026-01-01T00:00:00.000Z"), credentialHash: "PUBLIC-HASH-DOUBLE",
});
const actor = { id: "public-owner", sessionVersion: 7 };
const revision = (row: Row) => revisionModule.identityRevision(row);
const deny = (status: number) => (error: any) => error instanceof contract.KvError && error.status === status;
const config = { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: false };

function fixture(options: Row = {}) {
  let row: Row | null = snapshot(), audits: Row[] = [], policies: Row[] = [];
  let user: Row | null = { id: actor.id, role: "write", engineAdmin: false, sessionVersion: 7 };
  let queue = Promise.resolve();
  const calls: string[] = [];
  const equal = (a: any, b: any) => a instanceof Date && b instanceof Date ? a.getTime() === b.getTime() : a === b;
  const matches = (value: Row, where: Row) => Object.entries(where).every(([key, expected]) => equal(value[key], expected));
  const project = (value: Row, select?: Row) => select ? Object.fromEntries(Object.keys(select).filter(key => select[key]).map(key => [key, value[key]])) : { ...value };
  const db: Row = {
    user: { findUnique: async () => user && { ...user } },
    kvIdentity: {
      findMany: async ({ where, select }: Row) => row && (!where.ownerId || row.ownerId === where.ownerId) ? [project(row, select)] : [],
    },
    $transaction: (work: (tx: Row) => Promise<unknown>) => {
      const run = queue.then(async () => {
        let pending = row && { ...row }; const pendingAudits: Row[] = [];
        const tx: Row = {
          accountLock: { update: async () => { calls.push("lock"); await options.beforeLock?.(); } },
          user: { findUnique: async () => { calls.push("fresh-user"); return user && { ...user }; } },
          kvMount: { findUnique: async () => ({ id: "public-mount" }) },
          kvPolicy: { count: async () => 0, create: async ({ data }: Row) => { policies.push(data); } },
          kvIdentity: {
            findUnique: async ({ where }: Row) => { calls.push("identity-read"); return pending && pending.id === where.id ? { ...pending } : null; },
            create: async ({ data, select }: Row) => { pending = { ...data, revokedAt: null, createdAt: snapshot().createdAt }; return project(pending!, select); },
            updateMany: async ({ where, data }: Row) => {
              calls.push("conditional-write"); options.inspectWhere?.(where);
              if (options.race) pending = { ...pending, ...options.race };
              if (!pending || !matches(pending, where)) return { count: 0 };
              pending = { ...pending, ...data }; return { count: 1 };
            },
          },
          kvAudit: { create: async ({ data }: Row) => {
            calls.push("audit"); if (options.auditFailure) throw new Error("PUBLIC AUDIT FAILURE"); pendingAudits.push(data);
          } },
        };
        const result = await work(tx);
        row = pending; audits = [...audits, ...pendingAudits]; return result;
      });
      queue = run.then(() => {}, () => {}); return run;
    },
  };
  const registry = new KvRegistry(db, ["public-namespace"], config, forbidden);
  return { registry, calls, get row() { return row; }, get audits() { return audits; }, get policies() { return policies; },
    setUser: (next: Row | null) => { user = next; }, setRow: (next: Row | null) => { row = next; },
    user: () => user!,
  };
}

test("opaque revision is the exact versioned public metadata tuple", () => {
  const row = snapshot();
  const expected = createHash("sha256").update(JSON.stringify([
    "bortus-identity-revision/v1", row.id, row.ownerId, row.name,
    row.expiresAt.toISOString(), null, row.createdAt.toISOString(),
  ])).digest("hex");
  assert.equal(revision(row), expected);
  assert.equal(revision({ ...row, credentialHash: "CHANGED-HASH-DOUBLE", ownerSessionVersion: 9 }), expected);
});
for (const [field, value] of Object.entries({ id: "other", ownerId: "other", name: "other", expiresAt: new Date(0), revokedAt: new Date(0), createdAt: new Date(0) }))
  test(`revision binds ${field}`, () => assert.notEqual(revision({ ...snapshot(), [field]: value }), revision(snapshot())));
for (const [label, value, status] of [["missing", undefined, 428], ["null", null, 400], ["integer", 1, 400], ["boolean", true, 400], ["object", {}, 400], ["empty", "", 400], ["uppercase", "A".repeat(64), 400], ["short", "a".repeat(63), 400]] as const)
  test(`identity revision ${label} refuses without mutation`, async () => {
    const f = fixture(); await assert.rejects(f.registry.revokeIdentity(actor, f.row!.id, value), deny(status));
    assert.equal(f.row!.revokedAt, null); assert.equal(f.audits.length, 0); assert(!f.calls.includes("conditional-write"));
  });
test("stale metadata capture refuses before writing", async () => {
  const f = fixture(), captured = revision(f.row!); f.setRow({ ...f.row, name: "changed-public-name" });
  await assert.rejects(f.registry.revokeIdentity(actor, "public-identity", captured), deny(409));
  assert.equal(f.row!.revokedAt, null); assert.equal(f.audits.length, 0);
});
test("matching revocation commits one conditional update and redacted audit", async () => {
  let where: Row = {}; const f = fixture({ inspectWhere: (value: Row) => { where = value; } });
  await f.registry.revokeIdentity(actor, f.row!.id, revision(f.row!));
  assert(f.row!.revokedAt instanceof Date); assert.equal(where.revokedAt, null);
  assert.deepEqual(Object.keys(where).sort(), ["createdAt", "expiresAt", "id", "name", "ownerId", "ownerSessionVersion", "revokedAt"].sort());
  assert.deepEqual(plain(f.audits), [{ actorId: actor.id, action: "identity-revoke", outcome: "committed" }]);
  assert.deepEqual(f.calls, ["lock", "fresh-user", "identity-read", "conditional-write", "audit"]);
  assert.equal(f.row!.credentialHash, "PUBLIC-HASH-DOUBLE"); assert.equal(f.policies.length, 0);
});
test("repeated old and current revoked captures preserve first timestamp and audit", async () => {
  const f = fixture(), old = revision(f.row!); await f.registry.revokeIdentity(actor, f.row!.id, old);
  const time = f.row!.revokedAt, now = revision(f.row!);
  for (const captured of [old, now]) await assert.rejects(f.registry.revokeIdentity(actor, f.row!.id, captured), deny(409));
  assert.equal(f.row!.revokedAt, time); assert.equal(f.audits.length, 1);
});
test("two competing captures allow exactly one commit", async () => {
  const f = fixture(), captured = revision(f.row!);
  const results = await Promise.allSettled([f.registry.revokeIdentity(actor, f.row!.id, captured), f.registry.revokeIdentity(actor, f.row!.id, captured)]);
  assert.equal(results.filter(result => result.status === "fulfilled").length, 1);
  const rejected = results.find(result => result.status === "rejected") as PromiseRejectedResult;
  assert(deny(409)(rejected.reason)); assert.equal(f.audits.length, 1);
  assert.equal(f.calls.filter(call => call === "conditional-write").length, 1);
});
for (const race of [{ revokedAt: new Date(0) }, { name: "raced-name" }, { ownerSessionVersion: 8 }])
  test(`conditional-write race ${Object.keys(race)[0]} refuses without success audit`, async () => {
    const f = fixture({ race }); await assert.rejects(f.registry.revokeIdentity(actor, f.row!.id, revision(f.row!)), deny(409));
    assert.equal(f.audits.length, 0); assert.equal(f.row!.revokedAt, null);
  });
test("audit failure rolls the revocation back", async () => {
  const f = fixture({ auditFailure: true });
  await assert.rejects(f.registry.revokeIdentity(actor, f.row!.id, revision(f.row!)), deny(503));
  assert.equal(f.row!.revokedAt, null); assert.equal(f.audits.length, 0);
});
for (const scenario of ["deleted", "session", "readonly", "nonowner", "automation"])
  test(`fresh ${scenario} authority refuses despite matching revision`, async () => {
    const f = fixture(); let caller = { ...actor } as Row; let status = 403;
    if (scenario === "deleted") { f.setUser(null); status = 401; }
    if (scenario === "session") { f.setUser({ ...f.user(), sessionVersion: 8 }); status = 401; }
    if (scenario === "readonly") f.setUser({ ...f.user(), role: "readonly" });
    if (scenario === "nonowner") { f.setUser({ ...f.user(), id: "public-other" }); caller = { id: "public-other", sessionVersion: 7 }; }
    if (scenario === "automation") caller.identityId = f.row!.id;
    await assert.rejects(f.registry.revokeIdentity(caller, f.row!.id, revision(f.row!)), deny(status));
    assert.equal(f.row!.revokedAt, null); assert.equal(f.audits.length, 0);
  });
test("missing target retains404", async () => {
  const f = fixture(); f.setRow(null); await assert.rejects(f.registry.revokeIdentity(actor, "missing-public-id", "a".repeat(64)), deny(404));
});
test("effective administrator may revoke a different owner", async () => {
  const f = fixture(); f.setUser({ ...f.user(), id: "public-admin", engineAdmin: true });
  await f.registry.revokeIdentity({ id: "public-admin", sessionVersion: 7 }, f.row!.id, revision(f.row!)); assert.equal(f.audits.length, 1);
});
test("authority is re-read after acquisition of transaction lock", async () => {
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  const f = fixture({ beforeLock: () => gate }), pending = f.registry.revokeIdentity(actor, f.row!.id, revision(f.row!));
  await Promise.resolve(); f.setUser({ ...f.user(), role: "readonly" }); release();
  await assert.rejects(pending, deny(403)); assert.equal(f.row!.revokedAt, null); assert.equal(f.audits.length, 0);
});
test("role-only demotion and re-promotion never stamp revocation or session version", async () => {
  const f = fixture(), initial = revision(f.row!), tokenActor = { ...actor, identityId: f.row!.id };
  const direct = { user: { findUnique: async () => f.user() }, kvIdentity: { findUnique: async () => f.row } };
  f.setUser({ ...f.user(), role: "readonly" }); await assert.rejects(f.registry.current(tokenActor, direct), deny(401));
  f.setUser({ ...f.user(), role: "write" }); await f.registry.current(tokenActor, direct);
  assert.equal(f.row!.revokedAt, null); assert.equal(f.row!.ownerSessionVersion, 7); assert.equal(revision(f.row!), initial);
});
test("owner and identity deny-aware policy intersection remains authoritative", async () => {
  const f = fixture(), target = { mountId: "public-mount", path: "apps/public" };
  let identityDeny = true, ownerDeny = false;
  const client = { user: { findUnique: async () => f.user() }, kvIdentity: { findUnique: async () => f.row }, kvPolicy: { findMany: async ({ where }: Row) => [
    { mountId: target.mountId, prefix: "apps", effect: "allow", actions: '["read"]' },
    ...((where.principal.startsWith("identity:") ? identityDeny : ownerDeny) ? [{ mountId: target.mountId, prefix: target.path, effect: "deny", actions: '["read"]' }] : []),
  ] } };
  const caller = { ...actor, identityId: f.row!.id };
  await assert.rejects(f.registry.authorize(caller, target, "read", client), deny(403));
  identityDeny = false; ownerDeny = true; await assert.rejects(f.registry.authorize(caller, target, "read", client), deny(403));
  ownerDeny = false; await f.registry.authorize(caller, target, "read", client);
});
test("list metadata exposes revision and excludes credential and owner-session fields", async () => {
  const f = fixture(), page = await f.registry.listIdentities(actor);
  assert.equal(page.items[0].revision, revision(f.row!)); assert.equal(page.nextCursor, null);
  assert.deepEqual(Object.keys(page.items[0]).sort(), ["id", "ownerId", "name", "expiresAt", "revokedAt", "createdAt", "revision"].sort());
});
test("issue metadata returns revision with the synthetic one-time field only", async () => {
  const f = fixture(); const issued = await f.registry.issueIdentity(actor, { ownerId: actor.id, name: "public-issue", expiresAt: new Date(Date.now() + 3600000), scopes: [{ mountId: "public-mount", prefix: "", actions: ["read"] }] });
  assert.equal(issued.revision, revision(f.row!)); assert.equal(issued.credential, "NONCREDENTIAL-PUBLIC-ISSUE");
  assert(!Object.hasOwn(issued, "credentialHash")); assert(!Object.hasOwn(issued, "ownerSessionVersion"));
  assert(!JSON.stringify(f.audits).includes(issued.credential));
});
const request = (body: unknown, headers: Row = { "content-type": "application/json" }) => new Request("https://public.invalid/api/kv/identities/public-identity", { method: "DELETE", headers, body: JSON.stringify(body) });
test("actual DELETE callback and bounded decoder forward the exact revision", async () => {
  const f = fixture(); await route(f.registry, actor, request({ revision: revision(f.row!) }), { id: f.row!.id }); assert.equal(f.audits.length, 1);
});
for (const [label, body, status] of [["missing", {}, 428], ["null", { revision: null }, 400], ["number", { revision: 1 }, 400], ["unknown", { revision: "a".repeat(64), token: "PUBLIC-NONCREDENTIAL" }, 400], ["stale", { revision: "a".repeat(64) }, 409]] as const)
  test(`DELETE ${label} body refuses without writes`, async () => {
    const f = fixture(); await assert.rejects(route(f.registry, actor, request(body), { id: f.row!.id }), deny(status)); assert.equal(f.audits.length, 0); assert.equal(f.row!.revokedAt, null);
  });
test("DELETE preserves content-type and body-size refusals", async () => {
  const f = fixture(); await assert.rejects(route(f.registry, actor, request({ revision: revision(f.row!) }, { "content-type": "text/plain" }), { id: f.row!.id }), deny(400));
  await assert.rejects(route(f.registry, actor, request({ revision: revision(f.row!) }, { "content-type": "application/json", "content-length": String(512 * 1024 + 1) }), { id: f.row!.id }), deny(413)); assert.equal(f.audits.length, 0);
});
test("client captures exact revision body and exact confirmation", () => {
  const identity = { ...plain(snapshot()), revision: revision(snapshot()) };
  assert.deepEqual(plain(model.identityRevokeBody(identity)), { revision: identity.revision });
  assert.equal(model.identityConfirmation(identity), `revoke ${identity.id} owner=${identity.ownerId} expires=${identity.expiresAt} revision=${identity.revision}`);
});
for (const invalid of [undefined, null, 1, "a".repeat(63), "A".repeat(64)])
  test(`legacy/malformed client revision ${String(invalid)?.slice(0, 8)} cannot build a DELETE`, () => {
    const identity = { ...plain(snapshot()), revision: invalid };
    assert.equal(model.canRevokeIdentity(identity), false); assert.throws(() => model.identityRevokeBody(identity), model.AdminInputError);
  });
test("client refuses a captured revoked identity even with valid revision", () => {
  const identity = { ...plain(snapshot()), revision: "a".repeat(64), revokedAt: new Date(0).toISOString() };
  assert.equal(model.canRevokeIdentity(identity), false); assert.throws(() => model.identityRevokeBody(identity), model.AdminInputError);
});

// Minimal selected-Identities hook/JSX receiver; useTask/usePage are inert doubles.
// This proves production capture/handler wiring, not React effects or DOM behavior.
function clientFixture(initial: Row) {
  let metadata = initial, cursor = 0; const slots: any[] = [], calls: Row[] = [];
  let pending: Promise<unknown> | undefined, release!: (value: unknown) => void;
  const task: Row = { busy: false, error: "", run: (work: any) => {
    task.busy = true;
    pending = work(async (url: string, method: string, body: unknown) => {
      calls.push({ url, method, body: plain(body) }); return new Promise(resolve => { release = resolve; });
    }).finally(() => { task.busy = false; });
  } };
  const file = "src/components/secrets/kv-administration.tsx", text = source(file);
  const parsed = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declaration = parsed.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === "Identities"); assert(declaration);
  const jsx = (type: string, props: Row) => ({ type, props });
  const component = evaluate(declaration.getText(parsed) + "\nmodule.exports = Identities;", file, { "react/jsx-runtime": { jsx, jsxs: jsx } }, {
    ...model, useState: (value: any) => { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], (next: any) => { slots[i] = next; }]; },
    useEffect: () => {}, usePage: () => ({ page: { items: [metadata] }, controls: null, task: { busy: false, error: "" }, refresh: () => {} }), useTask: () => task,
    Button: "Button", Table: "Table", TaskState: "TaskState", Field: "Field", Exact: "Exact", Check: "Check", Actions: "Actions", boxClass: "", inputClass: "",
  });
  const render = () => { cursor = 0; return component({ changed: () => {} }); };
  const flatten = (node: any): any[] => Array.isArray(node) ? node.flatMap(flatten) : node?.props ? [node, ...flatten(node.props.children)] : [];
  const button = (view: any, name: string) => { const element = flatten(view).find(node => node.type === "Button" && node.props.children === name); assert(element, name); return element.props; };
  const select = () => { button(render(), "Revoke identity").onClick(); const view = render(); const exact = flatten(view).find(node => node.type === "Exact"); assert(exact); exact.props.onChange(exact.props.expected); return render(); };
  return { render, select, button, calls, get task() { return task; }, setMetadata: (value: Row) => { metadata = value; }, settle: async () => { release({ success: true }); await pending; }, confirm: (view: Row) => { button(view, "Confirm revocation").onClick(); }, flatten };
}
test("actual client handler retains selected revision when list changes before dispatch", async () => {
  const original = { ...plain(snapshot()), revision: revision(snapshot()) }, ui = clientFixture(original); ui.select();
  ui.setMetadata({ ...original, revision: "b".repeat(64) }); ui.confirm(ui.render());
  assert.equal(ui.calls.length, 1); assert.deepEqual(ui.calls[0], { url: "/api/kv/identities/public-identity", method: "DELETE", body: { revision: original.revision } });
  assert.equal(ui.task.busy, true); assert.equal(ui.button(ui.render(), "Confirm revocation").disabled, true);
  await ui.settle();
});
test("actual client controls disable metadata with no revision", () => {
  const ui = clientFixture(plain(snapshot())); assert.equal(ui.button(ui.render(), "Revoke identity").disabled, true); assert.equal(ui.calls.length, 0);
});
test("actual selected client explains capture and explicit re-selection", () => {
  const ui = clientFixture({ ...plain(snapshot()), revision: revision(snapshot()) }), view = ui.select();
  const text = JSON.stringify(view); assert.match(text, /Refreshing the list does not replace this capture/); assert.match(text, /cancel, refresh metadata and select again/);
});
const admin = { authenticated: true, username: "public-admin", role: "write", engineAdmin: true };
for (const status of [409, 503])
  test(`AdministrationClient ${status} sends captured JSON once and no retry`, async () => {
    const calls: Row[] = []; const identity = { ...plain(snapshot()), revision: revision(snapshot()) };
    const client = new model.AdministrationClient(async (url: string, init: Row) => {
      calls.push({ url, method: init.method, body: init.body, headers: init.headers });
      return Response.json(url === "/api/auth/session" ? admin : { error: "PUBLIC-REFUSAL" }, { status: url === "/api/auth/session" ? 200 : status });
    });
    await assert.rejects(client.run((send: any) => send("/api/kv/identities/public-identity", "DELETE", model.identityRevokeBody(identity))), (error: any) => error instanceof model.AdminFailure && error.status === status);
    assert.equal(calls.length, 2); assert.deepEqual(JSON.parse(calls[1].body), { revision: identity.revision }); assert.deepEqual(plain(calls[1].headers), { "Content-Type": "application/json" });
  });
for (const stage of ["preflight", "operation", "postflight"])
  test(`AdministrationClient fresh denial at ${stage} withdraws and does not retry`, async () => {
    let calls = 0, withdrawn = 0, deletes = 0; const identity = { ...plain(snapshot()), revision: revision(snapshot()) };
    const client = new model.AdministrationClient(async (url: string) => {
      calls++; if (url !== "/api/auth/session") deletes++;
      const at = stage === "preflight" ? 1 : stage === "operation" ? 2 : 3;
      return calls === at ? new Response("PUBLIC-MALFORMED-DENIAL", { status: 403 }) : Response.json(url === "/api/auth/session" ? admin : { success: true });
    }, () => { withdrawn++; });
    await assert.rejects(client.run((send: any) => send("/api/kv/identities/public-identity", "DELETE", model.identityRevokeBody(identity))), (error: any) => error instanceof model.AdminFailure && error.status === 403);
    assert.equal(withdrawn, 1); assert.equal(calls, stage === "preflight" ? 1 : stage === "operation" ? 2 : 3); assert.equal(deletes, stage === "preflight" ? 0 : 1);
  });
