import { test } from "node:test";
import assert from "node:assert/strict";
import { SignJWT, jwtVerify } from "jose";
import { HmacKeySlot } from "../src/lib/jwt-key";
const imported = (bytes: Uint8Array<ArrayBuffer>) => crypto.subtle.importKey("raw", bytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done; }); return { promise, resolve }; };
test("one nonextractable HMAC import serves concurrent signing/verification without retaining raw bytes", async () => {
  let imports = 0; const raw: Uint8Array<ArrayBuffer>[] = [];
  const slot = new HmacKeySlot(() => "public-hmac-concurrency", async bytes => { imports++; raw.push(bytes); await new Promise(done => setImmediate(done)); return imported(bytes); });
  const tokens = await Promise.all(Array.from({ length: 20 }, () => slot.run(key => new SignJWT({ sub: "fixture" }).setProtectedHeader({ alg: "HS256" }).sign(key))));
  await Promise.all(tokens.map(token => slot.run(async key => {
    assert.equal(key.extractable, false); assert.deepEqual(key.usages, ["sign", "verify"]);
    assert.equal((await jwtVerify(token, key, { algorithms: ["HS256"] })).payload.sub, "fixture");
    await assert.rejects(crypto.subtle.exportKey("raw", key));
  })));
  assert.equal(imports, 1); assert(raw.every(bytes => bytes.every(byte => byte === 0)));
});
test("rotation waits for the prior import, refuses its pending operation and never overlaps imports", async () => {
  let secret: string | undefined = "public-rotation-a", calls = 0, active = 0, maximum = 0;
  const started = deferred(), release = deferred();
  const slot = new HmacKeySlot(() => secret, async bytes => {
    calls++; maximum = Math.max(maximum, ++active);
    try { if (calls === 1) { started.resolve(); await release.promise; } return await imported(bytes); }
    finally { active--; }
  });
  const old = slot.run(key => new SignJWT({ sub: "old" }).setProtectedHeader({ alg: "HS256" }).sign(key));
  const refused = assert.rejects(old, { message: "JWT signing key unavailable" });
  await started.promise; secret = "public-rotation-b";
  const replacements = Array.from({ length: 10 }, () => slot.run(key => new SignJWT({ sub: "new" }).setProtectedHeader({ alg: "HS256" }).sign(key)));
  await new Promise(done => setImmediate(done)); assert.equal(calls, 1); release.resolve(); await refused;
  const tokens = await Promise.all(replacements); assert.equal(calls, 2); assert.equal(maximum, 1); assert.equal(active, 0);
  await jwtVerify(tokens[0], new TextEncoder().encode(secret), { algorithms: ["HS256"] });
  await assert.rejects(jwtVerify(tokens[0], new TextEncoder().encode("public-rotation-a"), { algorithms: ["HS256"] }));
});
test("rotation during a held signature callback refuses completion; missing env clears old material", async () => {
  let secret: string | undefined = "public-held-a", calls = 0; const release = deferred(), started = deferred();
  const slot = new HmacKeySlot(() => secret, bytes => { calls++; return imported(bytes); });
  const held = slot.run(async key => { started.resolve(); await release.promise; return new SignJWT({ sub: "held" }).setProtectedHeader({ alg: "HS256" }).sign(key); });
  const refused = assert.rejects(held, { message: "JWT signing key unavailable" }); await started.promise; secret = "public-held-b"; release.resolve(); await refused;
  await slot.run(key => new SignJWT({ sub: "next" }).setProtectedHeader({ alg: "HS256" }).sign(key)); assert.equal(calls, 2);
  secret = undefined; await assert.rejects(slot.run(async () => assert.fail("No callback without current signing material")), { message: "JWT signing key unavailable" });
  secret = "public-held-b"; await slot.run(async key => { assert.equal(key.extractable, false); }); assert.equal(calls, 3);
});
test("import faults use a fixed error and a later request can recover without old-key fallback", async () => {
  let fail = true, calls = 0; const raw: Uint8Array<ArrayBuffer>[] = [];
  const slot = new HmacKeySlot(() => "public-import-fault", async bytes => { calls++; raw.push(bytes); if (fail) throw Error("private synthetic import detail"); return imported(bytes); });
  await assert.rejects(slot.run(async () => assert.fail("Failed imports cannot invoke a signature callback")), { message: "JWT signing key unavailable" });
  fail = false; await slot.run(async key => { assert.equal(key.extractable, false); }); assert.equal(calls, 2); assert(raw.every(bytes => bytes.every(byte => byte === 0)));
});
