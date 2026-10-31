'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const { once } = require('node:events');
const { spawn, execFileSync } = require('node:child_process');
const { PrismaClient } = require('@prisma/client');
const checks = [];
const deadline = setTimeout(() => { process.exitCode = 1; if (child) child.kill('SIGTERM'); }, 60000);
let child, db, dir, exited;
(async () => {
  const { SignJWT } = await import('jose');
  dir = await fs.mkdtemp(path.join(os.tmpdir(), 'bortus-handler-production-'));
  const database = `file:${path.join(dir, 'public.db')}`;
  const env = { ...process.env, DATABASE_URL: database, BOTRUS_JWT_SECRET: 'public-handler-production-signing-only', BORTUS_SECRET_NAMESPACES: 'apps', BORTUS_SECRET_ALIASES_FILE: path.join(dir, 'aliases.json'), NODE_ENV: 'production', HOSTNAME: '127.0.0.1', BORTUS_DISABLE_PROVISIONING: 'true' };
  delete env.RUST_LOG; delete env.KUBERNETES_SERVICE_HOST;
  await fs.writeFile(env.BORTUS_SECRET_ALIASES_FILE, JSON.stringify([{ alias: 'public-fixture', namespace: 'apps', name: 'public-object', key: 'field' }]));
  execFileSync(process.execPath, [path.resolve('node_modules/prisma/build/index.js'), 'migrate', 'deploy'], { env, stdio: 'pipe' });
  db = new PrismaClient({ datasources: { db: { url: database } } });
  await db.variable.create({ data: { key: 'public_setting', value: 'public', category: 'general' } });
  const user = await db.user.create({ data: { username: 'public_handler', passwordHash: 'unused-public-fixture-hash', role: 'write', engineAdmin: true } });
  const token = async (version = 0) => 'botrus_auth_token=' + await new SignJWT({ sub: user.id, username: 'untrusted-token-name', sessionVersion: version }).setProtectedHeader({ alg: 'HS256' }).setExpirationTime('1h').sign(new TextEncoder().encode(env.BOTRUS_JWT_SECRET));
  const cookie = await token();
  const portHolder = net.createServer(); portHolder.listen(0, '127.0.0.1'); await once(portHolder, 'listening');
  const port = portHolder.address().port; await new Promise(resolve => portHolder.close(resolve));
  child = spawn(process.execPath, [path.resolve('.next/standalone/server.js')], { env: { ...env, PORT: String(port) }, stdio: 'ignore' });
  exited = once(child, 'exit');
  console.log('HANDLER_HTTP_OWNED_PROCESS ' + JSON.stringify({ pid: child.pid }));
  const base = `http://127.0.0.1:${port}`;
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(base + '/api/health/live', { signal: AbortSignal.timeout(1000) })).ok) { ready = true; break; } } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready);
  const get = (route, credential = cookie) => fetch(base + route, { headers: { cookie: credential }, signal: AbortSignal.timeout(5000) });
  for (const route of ['/api/vars', '/api/secret-references']) {
    assert.equal((await get(route)).status, 200); checks.push('write metadata GET accepted: ' + route);
  }
  let response = await get('/api/auth/session'), body = await response.json();
  assert.equal(response.status, 200); assert.equal(body.authenticated, true); assert.equal(body.username, user.username); assert.equal(body.engineAdmin, true); assert.equal('passwordHash' in body, false); checks.push('current session fields only');
  await db.user.update({ where: { id: user.id }, data: { username: 'public_renamed', role: 'readonly', engineAdmin: false } });
  body = await (await get('/api/auth/session')).json();
  assert.equal(body.authenticated, true); assert.equal(body.role, 'readonly'); assert.equal(body.username, 'public_renamed'); assert.equal(body.engineAdmin, false); checks.push('fresh demotion/admin withdrawal and DB username');
  for (const route of ['/api/vars', '/api/secret-references']) { assert.equal((await get(route)).status, 200); checks.push('readonly metadata accepted: ' + route); }
  await db.user.update({ where: { id: user.id }, data: { sessionVersion: 1 } });
  for (const route of ['/api/vars', '/api/secret-references']) { assert.equal((await get(route)).status, 401); checks.push('reset stale cookie refused: ' + route); }
  assert.equal((await (await get('/api/auth/session')).json()).authenticated, false); checks.push('reset session unauthenticated');
  const freshCookie = await token(1);
  assert.equal((await get('/api/vars', freshCookie)).status, 200); checks.push('fresh version accepted without cached revocation');
  await db.user.delete({ where: { id: user.id } });
  for (const route of ['/api/vars', '/api/secret-references']) { assert.equal((await get(route, freshCookie)).status, 401); checks.push('deleted account refused: ' + route); }
  assert.equal((await (await get('/api/auth/session', freshCookie)).json()).authenticated, false); checks.push('deleted session unauthenticated');
  console.log('HANDLER_HTTP_ASSERTIONS ' + JSON.stringify({ checks: checks.length, failed: 0, privateValuesLogged: false }));
})().catch(error => { console.log('HANDLER_HTTP_FAILURE ' + JSON.stringify({ classification: error.name, completedChecks: checks.length })); process.exitCode = 1; }).finally(async () => {
  clearTimeout(deadline);
  if (child && child.exitCode === null) child.kill('SIGTERM');
  const exit = child ? await exited : null;
  if (db) await db.$disconnect();
  if (dir) {
    assert.equal(path.dirname(dir), os.tmpdir()); assert.ok(path.basename(dir).startsWith('bortus-handler-production-'));
    await fs.rm(dir, { recursive: true, force: true });
  }
  console.log('HANDLER_HTTP_CLEANUP ' + JSON.stringify({ childExit: exit, fixtureRemoved: !!dir }));
});
