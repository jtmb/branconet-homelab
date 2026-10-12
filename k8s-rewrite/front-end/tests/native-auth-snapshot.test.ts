import { test } from "node:test";
import assert from "node:assert/strict";
import { AsyncLocalStorage } from "node:async_hooks";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { SignJWT } from "jose";
import type { SecretStore } from "../src/lib/cluster-secrets";

test("fresh native handler account snapshots retain independent middleware and revocation fences", { timeout: 90000 }, async t => {
  // Initialize the actual Next request context before loading its storage instances.
  Object.assign(globalThis, { AsyncLocalStorage });
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-native-auth-"));
  const url = `file:${path.join(dir, "accounts.db").replaceAll("\\", "/")}`;
  const keys = ["DATABASE_URL", "BOTRUS_JWT_SECRET"] as const;
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  process.env.DATABASE_URL = url; process.env.BOTRUS_JWT_SECRET = "public-native-auth-fixture-only";
  const clients: PrismaClient[] = []; let restoreFind = () => {};
  try {
    const env = { ...process.env }; delete env.RUST_LOG;
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    const writer = new PrismaClient({ datasources: { db: { url } } });
    clients.push(writer);
    const { default: singleton } = await import("../src/lib/db"); clients.push(singleton);
    const auth = await import("../src/lib/auth");
    const { getOperatorRole } = await import("../src/lib/permissions");
    const { middleware } = await import("../src/middleware");
    const { secretHandlers } = await import("../src/lib/secrets-api");
    const { NextRequest } = await import("next/server");
    const { createRequestStoreForAPI } = await import("next/dist/server/async-storage/request-store");
    const { workUnitAsyncStorage } = await import("next/dist/server/app-render/work-unit-async-storage.external");
    const { workAsyncStorage } = await import("next/dist/server/app-render/work-async-storage.external");
    const { createWorkStore } = await import("next/dist/server/async-storage/work-store");
    const { cookies } = await import("next/headers");
    const { GET: variables } = await import("../src/app/api/vars/route");
    const { GET: aliases } = await import("../src/app/api/secret-references/route");
    const { GET: session } = await import("../src/app/api/auth/session/route");
    let queries = 0, outage = false, nativeCalls = 0;
    const find = singleton.user.findUnique.bind(singleton.user);
    restoreFind = () => { singleton.user.findUnique = find; };
    singleton.user.findUnique = ((...args: Parameters<typeof find>) => {
      queries++; if (outage) throw new Error("Private synthetic database detail");
      return find(...args);
    }) as unknown as typeof singleton.user.findUnique;
    const context = <T>(cookie: string | null, operation: () => T) => {
      const request = new NextRequest("http://localhost/api/secrets", { headers: cookie ? { cookie } : {} });
      const store = createRequestStoreForAPI(request, { pathname: "/api/secrets" }, { tags: [], expirationsByCacheKind: new Map() }, undefined, undefined);
      const work = createWorkStore({ page: "/api/secrets/route", buildId: "public-native-auth-fixture", previouslyRevalidatedTags: [],
        renderOpts: { assetPrefix: "", supportsDynamicResponse: true, shouldWaitOnAllReady: false, isDraftMode: false, isRevalidate: false, nextExport: false,
          isDebugDynamicAccesses: false, dev: false, hasReadableErrorStacks: false, waitUntil: undefined, onClose: () => {}, onAfterTaskError: undefined,
          experimental: { isRoutePPREnabled: false, cacheComponents: false, authInterrupts: false } } });
      return workAsyncStorage.run(work, () => workUnitAsyncStorage.run(store, operation));
    };
    const handlers = secretHandlers(getOperatorRole, () => {
      nativeCalls++;
      return { list: async () => [] } as unknown as SecretStore;
    });
    const metadata = (cookie: string | null) => context(cookie, () => handlers.GET(new Request("http://localhost/api/secrets")));
    const values = (cookie: string | null) => context(cookie, () => handlers.GET(new Request("http://localhost/api/secrets?namespace=public&name=fixture&key=field")));
    const token = async (id: string, username: string, version = 0) => `botrus_auth_token=${await auth.signJWT({ sub: id, username, sessionVersion: version })}`;
    const create = (username: string) => writer.user.create({ data: { username, passwordHash: "unused-public-fixture-hash", role: "write", engineAdmin: true } });
    await t.test("actual Next dynamic work/request contexts expose request-owned cookies", async () => {
      assert.equal(await context("botrus_auth_token=public-placeholder", async () => (await cookies()).has(auth.AUTH_COOKIE)), true);
      assert.equal(await context(null, async () => (await cookies()).has(auth.AUTH_COOKIE)), false);
      assert.equal(queries, 0);
    });
    await t.test("absent invalid expired cookies make no account/native calls", async () => {
      const expired = await new SignJWT({ sub: "absent", username: "fixture" }).setProtectedHeader({ alg: "HS256" }).setExpirationTime(1).sign(new TextEncoder().encode(process.env.BOTRUS_JWT_SECRET));
      const before = queries;
      for (const cookie of [null, "other=public", "botrus_auth_token=invalid", `botrus_auth_token=${expired}`]) assert.equal((await metadata(cookie)).status, 401);
      assert.equal(queries, before); assert.equal(nativeCalls, 0);
    });
    await t.test("one query supplies exactly the fresh handler account fields", async () => {
      const user = await create("one_snapshot"), cookie = await token(user.id, "untrusted-token-name");
      const before = queries;
      assert.equal(await context(cookie, getOperatorRole), "write"); assert.equal(queries - before, 1);
      const account = await auth.getSessionAccountFromHeaders(cookie);
      assert.deepEqual(account, { id: user.id, username: user.username, sessionVersion: 0, role: "write", engineAdmin: true });
      assert.deepEqual(Object.keys(account!).sort(), ["engineAdmin", "id", "role", "sessionVersion", "username"]);
    });
    await t.test("deletion and session reset revoke previously valid cookies", async () => {
      for (const change of ["delete", "reset"] as const) {
        const user = await create("revoked_" + change), cookie = await token(user.id, user.username);
        assert.equal(await context(cookie, getOperatorRole), "write");
        if (change === "delete") await writer.user.delete({ where: { id: user.id } });
        else await writer.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
        const before = nativeCalls; assert.equal((await values(cookie)).status, 401); assert.equal(nativeCalls, before);
      }
    });
    await t.test("role and engine-admin withdrawal forbid values and body consumption but preserve metadata", async () => {
      for (const change of [{ role: "readonly" }, { engineAdmin: false }]) {
        const user = await create("withdrawn_" + Object.keys(change)[0]), cookie = await token(user.id, user.username);
        await writer.user.update({ where: { id: user.id }, data: change });
        assert.equal(await context(cookie, getOperatorRole), "readonly");
        const before = nativeCalls; assert.equal((await values(cookie)).status, 403);
        const request = new Request("http://localhost/api/secrets", { method: "POST", body: "invalid-public-json" });
        request.json = async () => assert.fail("Forbidden mutation must not consume its body");
        assert.equal((await context(cookie, () => handlers.POST(request))).status, 403); assert.equal(nativeCalls, before);
        assert.equal((await metadata(cookie)).status, 200); assert.equal(nativeCalls, before + 1);
      }
    });
    await t.test("middleware success cannot authorize a subsequently revoked or downgraded handler", async () => {
      for (const change of ["delete", "reset", "role", "admin"] as const) {
        const user = await create("between_" + change), cookie = await token(user.id, user.username);
        const before = queries;
        assert.equal((await middleware(new NextRequest("http://localhost/api/secrets", { headers: { cookie } }))).headers.get("x-middleware-next"), "1");
        assert.equal(queries - before, 1);
        if (change === "delete") await writer.user.delete({ where: { id: user.id } });
        else await writer.user.update({ where: { id: user.id }, data: change === "reset" ? { sessionVersion: 1 } : change === "role" ? { role: "readonly" } : { engineAdmin: false } });
        const calls = nativeCalls; assert.equal((await values(cookie)).status, change === "delete" || change === "reset" ? 401 : 403);
        assert.equal(queries - before, 2); assert.equal(nativeCalls, calls);
      }
    });
    await t.test("repeated/interleaved principals cannot reuse account authorization", async () => {
      const a = await create("interleaved_a"), b = await create("interleaved_b"), ca = await token(a.id, a.username), cb = await token(b.id, b.username);
      assert.deepEqual(await Promise.all([context(ca, getOperatorRole), context(cb, getOperatorRole)]), ["write", "write"]);
      await writer.user.update({ where: { id: a.id }, data: { engineAdmin: false } });
      const before = queries;
      assert.deepEqual(await Promise.all([context(cb, getOperatorRole), context(ca, getOperatorRole), context(ca, getOperatorRole)]), ["write", "readonly", "readonly"]);
      assert.equal(queries - before, 3);
    });
    await t.test("legacy versionless JWT is accepted only at account version zero", async () => {
      const user = await create("legacy_zero");
      const legacy = await new SignJWT({ sub: user.id, username: user.username }).setProtectedHeader({ alg: "HS256" }).setExpirationTime("1h").sign(new TextEncoder().encode(process.env.BOTRUS_JWT_SECRET));
      const cookie = `botrus_auth_token=${legacy}`;
      assert.equal(await context(cookie, getOperatorRole), "write"); assert.equal((await auth.getSessionFromHeaders(cookie))?.sessionVersion, 0);
      await writer.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
      assert.equal(await context(cookie, getOperatorRole), null); assert.equal(await auth.getSessionFromHeaders(cookie), null);
      assert.equal(await context(await token(user.id, user.username, 1), getOperatorRole), "write");
    });
    await t.test("database outage fails closed with a fixed private 503 before native access", async () => {
      const user = await create("outage"), cookie = await token(user.id, user.username), before = nativeCalls; outage = true;
      try {
        const response = await metadata(cookie); assert.equal(response.status, 503);
        assert.equal(response.headers.get("Cache-Control"), "no-store, private");
        assert.deepEqual(await response.json(), { error: "Kubernetes Secrets unavailable; no database fallback is permitted" });
        assert.equal(nativeCalls, before);
      } finally { outage = false; }
    });
    await t.test("vars aliases and session each read one fresh minimal handler account", async () => {
      const user = await create("handler_snapshot"), cookie = await token(user.id, "untrusted-token-name");
      for (const operation of [variables, () => aliases(new Request("http://localhost/api/secret-references")), session]) {
        const before = queries;
        const response = await context(cookie, operation);
        assert.equal(response.status, 200); assert.equal(queries - before, 1);
      }
      await writer.user.update({ where: { id: user.id }, data: { role: "readonly", engineAdmin: false, username: "handler_renamed" } });
      const before = queries;
      const response = await context(cookie, session);
      const body = await response.json();
      assert.equal(body.authenticated, true); assert.equal(body.role, "readonly");
      assert.equal(body.engineAdmin, false); assert.equal(body.username, "handler_renamed");
      assert.equal(queries - before, 1); assert.equal("passwordHash" in body, false);
      assert.equal((await context(cookie, variables)).status, 200);
      assert.equal((await context(cookie, () => aliases(new Request("http://localhost/api/secret-references")))).status, 200);
    });
    await t.test("middleware admission cannot survive handler deletion or session-version reset", async () => {
      for (const change of ["delete", "reset"] as const) {
        const user = await create("handler_revoked_" + change), cookie = await token(user.id, user.username);
        assert.equal((await middleware(new NextRequest("http://localhost/api/vars", { headers: { cookie } }))).headers.get("x-middleware-next"), "1");
        if (change === "delete") await writer.user.delete({ where: { id: user.id } });
        else await writer.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
        for (const operation of [variables, () => aliases(new Request("http://localhost/api/secret-references"))]) {
          const before = queries; assert.equal((await context(cookie, operation)).status, 401); assert.equal(queries - before, 1);
        }
        const before = queries, response = await context(cookie, session);
        assert.equal(response.status, 200); assert.equal((await response.json()).authenticated, false); assert.equal(queries - before, 1);
      }
    });
    await t.test("handler snapshots are not shared across requests or database outages", async () => {
      const user = await create("handler_outage"), cookie = await token(user.id, user.username);
      const before = queries;
      assert.equal((await context(cookie, session)).status, 200);
      await writer.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
      assert.equal((await (await context(cookie, session)).json()).authenticated, false);
      assert.equal(queries - before, 2);
      outage = true;
      try {
        assert.equal((await context(cookie, variables)).status, 503);
        assert.equal((await context(cookie, () => aliases(new Request("http://localhost/api/secret-references")))).status, 503);
        const response = await context(cookie, session);
        assert.equal(response.status, 500);
        assert.deepEqual(await response.json(), { authenticated: false, error: "Internal server error" });
      } finally { outage = false; }
    });
    await t.test("operator signing-material rotation does not retain cookies or bypass fresh account withdrawal", async () => {
      const original = process.env.BOTRUS_JWT_SECRET;
      try {
        const user = await create("signing_rotation"), oldCookie = await token(user.id, user.username);
        assert.equal(await context(oldCookie, getOperatorRole), "write");
        process.env.BOTRUS_JWT_SECRET = "public-native-auth-replacement-signing";
        const before = queries;
        assert.equal(await context(oldCookie, getOperatorRole), null); assert.equal(queries, before);
        const replacement = await token(user.id, user.username);
        assert.equal(await context(replacement, getOperatorRole), "write");
        await writer.user.update({ where: { id: user.id }, data: { role: "readonly", engineAdmin: false } });
        const calls = nativeCalls; assert.equal((await values(replacement)).status, 403); assert.equal(nativeCalls, calls);
        await writer.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
        assert.equal((await metadata(replacement)).status, 401);
        const reset = await token(user.id, user.username, 1); assert.equal((await metadata(reset)).status, 200);
        await writer.user.delete({ where: { id: user.id } }); assert.equal((await metadata(reset)).status, 401);
      } finally { process.env.BOTRUS_JWT_SECRET = original; }
    });
  } finally {
    restoreFind();
    await Promise.all(clients.map(client => client.$disconnect()));
    for (const key of keys) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-native-auth-")) throw Error("Unsafe native auth fixture cleanup");
    await rm(dir, { recursive: true, force: true });
  }
});
