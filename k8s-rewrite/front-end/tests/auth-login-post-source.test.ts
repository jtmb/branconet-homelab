import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

type Compiler = { transpileModule: (source: string, options: unknown) => { outputText: string; diagnostics?: unknown[] } };
const require = createRequire(import.meta.url);
const compiler = require(process.env.BORTUS_SOURCE_TYPESCRIPT ?? 'typescript') as Compiler;
const raw = readFileSync(new URL('../src/app/api/auth/login/route.ts', import.meta.url));
assert.equal(createHash('sha256').update(raw.toString('utf8').replace(/\r\n/g, '\n')).digest('hex'), '06d7b4d0684150eac758b00d1219771fb4a86145ac11f055739826a837aa1fb6');
const text = raw.toString('utf8');
const start = text.indexOf('export async function POST(');
assert.ok(start >= 0);
assert.equal(text.indexOf('export async function POST(', start + 1), -1);
const declaration = text.slice(start);
const compiled = compiler.transpileModule(declaration.replace(/^export /, ''), { compilerOptions: { target: 99, module: 0 }, reportDiagnostics: true });
assert.equal(compiled.diagnostics?.length ?? 0, 0);
const factory = new Function('ensureJwtSecret', 'loginSchema', 'prisma', 'bcrypt', 'signJWT', 'NextResponse', 'AUTH_COOKIE', 'process', 'console', compiled.outputText + '\nreturn POST;');

type Config = {
  faultAt?: string; rejectAt?: string; invalid?: boolean; issues?: unknown; user?: unknown;
  valid?: unknown; env?: unknown; setterReturn?: unknown; response?: Record<string, unknown>; errorResponse?: Record<string,unknown>; loggerReturn?: unknown;
  ensureResult?: unknown; bodyResult?: unknown; expectedBody?: unknown; token?: unknown; parseResult?: unknown;
};
function harness(c: Config = {}) {
  const trace: string[] = [];
  const failure = Object.freeze({ publicMarker: 'synthetic-fault' });
  const body = Object.freeze({ publicInput: 'inert-body' });
  const cookieName = Object.freeze({ publicCookie: 'inert-name' });
  const token = Object.hasOwn(c, 'token') ? c.token : Object.freeze({ publicToken: 'inert-token' });
  const calls = { json: [] as unknown[][], find: [] as unknown[][], compare: [] as unknown[][], sign: [] as unknown[][], set: [] as unknown[][], errors: [] as unknown[][] };
  function hit(name: string) { trace.push(name); if (c.faultAt === name) throw failure; }
  function settled(name: string, value: unknown) { hit(name); return c.rejectAt === name ? Promise.reject(failure) : value; }
  const data = { get username() { hit('data.username'); return 'public-user'; }, get password() { hit('data.password'); return 'public-password'; } };
  const parsed = { get success() { hit('parsed.success'); return !c.invalid; }, get data() { hit('parsed.data'); return data; }, get error() { hit('parsed.error'); return { issues: Object.hasOwn(c, 'issues') ? c.issues : [{ message: 'public-invalid' }] }; } };
  const user = { get id() { hit('user.id'); return 'public-id'; }, get username() { hit('user.username'); return 'public-canonical-user'; }, get sessionVersion() { hit('user.sessionVersion'); return 7; }, get passwordHash() { hit('user.passwordHash'); return 'public-hash-placeholder'; } };
  const store = { get set() { hit('cookies.set:get'); return function(this: unknown, ...args: unknown[]) { hit('cookies.set:call'); assert.equal(this, store); calls.set.push(args); return c.setterReturn; }; } };
  const response = c.response ?? { publicResponse: 'success' };
  Object.defineProperty(response, 'cookies', { get() { hit('response.cookies'); return store; }, configurable: true });
  const errorResponse = c.errorResponse ?? { publicResponse: 'error' };
  const next = { get json() { hit('json:get'); return function(this: unknown, ...args: unknown[]) { hit('json:call:' + (calls.json.length + 1)); assert.equal(this, next); calls.json.push(args); return args.length === 1 ? response : errorResponse; }; } };
  const schema = { get safeParse() { hit('schema.safeParse:get'); return function(this: unknown, value: unknown) { hit('schema.safeParse:call'); assert.equal(this, schema); assert.equal(value, Object.hasOwn(c, 'expectedBody') ? c.expectedBody : Object.hasOwn(c, 'bodyResult') ? c.bodyResult : body); return Object.hasOwn(c, 'parseResult') ? c.parseResult : parsed; }; } };
  const delegate = { get findUnique() { hit('user.findUnique:get'); return function(this: unknown, ...args: unknown[]) { assert.equal(this, delegate); calls.find.push(args); return settled('user.findUnique:call', Object.hasOwn(c, 'user') ? c.user : user); }; } };
  const prisma = { get user() { hit('prisma.user'); return delegate; } };
  const bcrypt = { get compare() { hit('bcrypt.compare:get'); return function(this: unknown, ...args: unknown[]) { assert.equal(this, bcrypt); calls.compare.push(args); return settled('bcrypt.compare:call', Object.hasOwn(c, 'valid') ? c.valid : true); }; } };
  const environment = { get NODE_ENV() { hit('env.NODE_ENV'); return Object.hasOwn(c, 'env') ? c.env : 'test'; } };
  const fakeProcess = { get env() { hit('process.env'); return environment; } };
  const logger = { get error() { hit('console.error:get'); return function(this: unknown, ...args: unknown[]) { hit('console.error:call'); assert.equal(this, logger); calls.errors.push(args); return c.loggerReturn; }; } };
  const req = { get json() { hit('req.json:get'); return function(this: unknown) { assert.equal(this, req); return settled('req.json:call', Object.hasOwn(c, 'bodyResult') ? c.bodyResult : body); }; } };
  const ensure = () => settled('ensure:call', c.ensureResult);
  const sign = (...args: unknown[]) => { calls.sign.push(args); return settled('sign:call', token); };
  const post = factory(ensure, schema, prisma, bcrypt, sign, next, cookieName, fakeProcess, logger) as (req: unknown) => Promise<unknown>;
  return { post, req, trace, calls, failure, body, cookieName, token, response, errorResponse, user };
}
const successOrder = ['ensure:call','req.json:get','req.json:call','schema.safeParse:get','schema.safeParse:call','parsed.success','parsed.data','data.username','data.password','prisma.user','user.findUnique:get','user.findUnique:call','bcrypt.compare:get','user.passwordHash','bcrypt.compare:call','user.id','user.username','user.sessionVersion','sign:call','json:get','user.id','user.username','json:call:1','response.cookies','cookies.set:get','process.env','env.NODE_ENV','cookies.set:call'];

test('exact declaration runs with entirely inert immediate bindings and independent call/receiver/argument order', async () => {
  const h = harness(); assert.equal(await h.post(h.req), h.response); assert.deepEqual(h.trace, successOrder);
  assert.deepEqual(h.calls.find, [[{ where: { username: 'public-user' } }]]);
  assert.deepEqual(h.calls.compare, [['public-password', 'public-hash-placeholder']]);
  assert.deepEqual(h.calls.sign, [[{ sub: 'public-id', username: 'public-canonical-user', sessionVersion: 7 }]]);
  assert.deepEqual(h.calls.json, [[{ id: 'public-id', username: 'public-canonical-user' }]]);
  assert.deepEqual(h.calls.set, [[h.cookieName,h.token,{ httpOnly:true,secure:false,sameSite:'lax',path:'/',maxAge:604800 }]]);
  assert.deepEqual(Object.keys(h.calls.set[0][2] as object), ['httpOnly','secure','sameSite','path','maxAge']); assert.deepEqual(h.calls.errors, []);
});
for (const env of ['production','Production',' production',undefined,null,0,true,{},Object('production')]) test('strict environment comparison ' + String(env), async () => {
  const h=harness({env}); await h.post(h.req); assert.equal((h.calls.set[0][2] as {secure:unknown}).secure, env === 'production');
});
test('fresh query/sign/response/options allocations across calls; setter result is ignored', async () => {
  let inspected=false; const ignored=Object.defineProperty({},'then',{get(){inspected=true;throw new Error('inert setter return must stay unread');}});
  const h=harness({setterReturn:ignored}); await h.post(h.req); await h.post(h.req); assert.equal(inspected,false);
  for (const group of [h.calls.find,h.calls.sign,h.calls.json]) assert.notEqual(group[0][0],group[1][0]);
  assert.notEqual((h.calls.find[0][0] as {where:unknown}).where,(h.calls.find[1][0] as {where:unknown}).where); assert.notEqual(h.calls.set[0][2],h.calls.set[1][2]);
});
for (const faultAt of [...new Set(successOrder)]) test('immediate fault enters fixed500 catch at '+faultAt, async () => {
  const h=harness({faultAt});
  if (faultAt==='json:get' || faultAt==='json:call:1') { await assert.rejects(h.post(h.req), e=>e===h.failure); assert.equal(h.calls.errors.length,1); }
  else { assert.equal(await h.post(h.req),h.errorResponse); assert.deepEqual(h.calls.errors,[['Login error:',h.failure]]); assert.deepEqual(h.calls.json.at(-1),[{error:'Internal server error'},{status:500}]); }
  const first=successOrder.indexOf(faultAt); assert.deepEqual(h.trace.slice(0,first+1),successOrder.slice(0,first+1));
});
for (const rejectAt of ['ensure:call','req.json:call','user.findUnique:call','bcrypt.compare:call','sign:call']) test('awaited rejection enters fixed500 catch at '+rejectAt, async () => {
  const h=harness({rejectAt}); assert.equal(await h.post(h.req),h.errorResponse); assert.deepEqual(h.calls.errors,[['Login error:',h.failure]]); assert.deepEqual(h.calls.json.at(-1),[{error:'Internal server error'},{status:500}]); assert.equal(h.calls.set.length,0);
});
for (const issues of [[{message:'public-invalid'}],[],[{}],[{message:null}],[{message:undefined}],[{message:''}],[{message:0}],[{message:false}]]) test('invalid parse nullish-only message handling '+JSON.stringify(issues), async () => {
  const h=harness({invalid:true,issues}); assert.equal(await h.post(h.req),h.errorResponse); const message=(issues[0] as {message?:unknown}|undefined)?.message ?? 'Invalid input'; assert.deepEqual(h.calls.json,[[{error:message},{status:400}]]); assert.equal(h.calls.find.length,0); assert.equal(h.calls.set.length,0); assert.equal(h.calls.errors.length,0);
});
test('malformed inert parse result fails closed without downstream lookup', async () => {
  const h=harness({parseResult:null}); assert.equal(await h.post(h.req),h.errorResponse); assert.equal(h.calls.find.length,0); assert.equal(h.calls.errors.length,1);
});
test('safeParse is synchronous; a promise-shaped result is not awaited', async () => {
  let touched=false; const h=harness({parseResult:{get then(){touched=true;throw new Error('not awaited');}}}); assert.equal(await h.post(h.req),h.errorResponse); assert.equal(touched,false); assert.equal(h.calls.find.length,0); assert.equal(h.calls.errors.length,1);
});
for (const user of [undefined,null,false,0,'']) test('falsy lookup denies without compare/sign/cookie '+String(user), async () => {
  const h=harness({user}); assert.equal(await h.post(h.req),h.errorResponse); assert.deepEqual(h.calls.json,[[{error:'Invalid username or password'},{status:401}]]); assert.equal(h.calls.compare.length,0); assert.equal(h.calls.sign.length,0); assert.equal(h.calls.set.length,0); assert.equal(h.calls.errors.length,0);
});
for (const valid of [undefined,null,false,0,'']) test('falsy comparison denies without sign/cookie '+String(valid), async () => {
  const h=harness({valid}); assert.equal(await h.post(h.req),h.errorResponse); assert.deepEqual(h.calls.json,[[{error:'Invalid username or password'},{status:401}]]); assert.equal(h.calls.sign.length,0); assert.equal(h.calls.set.length,0); assert.equal(h.calls.errors.length,0);
});
test('truthy comparison is used as truthy, token preserves exact inert identity', async () => {
  const token=Object.freeze({publicToken:'identity'}); const h=harness({valid:{},token}); assert.equal(await h.post(h.req),h.response); assert.equal(h.calls.set[0][1],token);
});
for (const hold of ['ensure','body']) test('await '+hold+' settles before downstream access', async () => {
  let release: ((value:unknown)=>void)|undefined; const held=new Promise<unknown>(resolve=>{release=resolve;}); const publicBody={publicBody:'released'}; const h=harness(hold==='ensure'?{ensureResult:held}:{bodyResult:held,expectedBody:publicBody}); const pending=h.post(h.req);
  await Promise.resolve(); await Promise.resolve(); assert.deepEqual(h.trace,hold==='ensure'?['ensure:call']:['ensure:call','req.json:get','req.json:call']);
  assert.ok(release); release(hold==='ensure'?undefined:publicBody); assert.equal(await pending,h.response); assert.equal(h.calls.errors.length,0);
});
test('success response then getter failure happens after set and bypasses catch', async () => {
  const marker={publicFault:'return-assimilation'}; const response=Object.defineProperty({},'then',{get(){throw marker;}}); const h=harness({response}); await assert.rejects(h.post(h.req),e=>e===marker); assert.equal(h.calls.set.length,1); assert.equal(h.calls.errors.length,0);
});
test('success response thenable settles after cookie set; setter thenable is never read', async () => {
  let h:ReturnType<typeof harness>; const result={publicResult:'thenable'}; const response={then(resolve:(value:unknown)=>void){assert.equal(h.calls.set.length,1);resolve(result);}}; h=harness({response}); assert.equal(await h.post(h.req),result); assert.equal(h.calls.errors.length,0);
});
for (const branch of ['invalid','missing-user','wrong-password','catch']) test('returned error response assimilation bypasses catch for '+branch, async () => {
  const marker={publicFault:'error-response-assimilation'}; const response=Object.defineProperty({},'then',{get(){throw marker;}});
  const branchConfig:Config=branch==='invalid'?{invalid:true}:branch==='missing-user'?{user:null}:branch==='wrong-password'?{valid:false}:{rejectAt:'ensure:call'};
  const h=harness({...branchConfig,errorResponse:response}); await assert.rejects(h.post(h.req),e=>e===marker); assert.equal(h.calls.json.length,1); assert.equal(h.calls.errors.length,branch==='catch'?1:0); assert.equal(h.calls.set.length,0);
});
test('catch ignores the logger returned thenable', async () => {
  let touched=false; const loggerReturn=Object.defineProperty({},'then',{get(){touched=true;throw new Error('logger return is ignored');}});
  const h=harness({rejectAt:'ensure:call',loggerReturn}); assert.equal(await h.post(h.req),h.errorResponse); assert.equal(touched,false); assert.deepEqual(h.calls.errors,[['Login error:',h.failure]]);
});
for (const issues of [null,undefined]) test('malformed inert issue collection enters catch '+String(issues), async () => {
  const h=harness({invalid:true,issues}); assert.equal(await h.post(h.req),h.errorResponse); assert.deepEqual(h.calls.json,[[{error:'Internal server error'},{status:500}]]); assert.equal(h.calls.errors.length,1); assert.equal(h.calls.find.length,0);
});
for (const faultAt of ['console.error:get','console.error:call']) test('catch logger fault propagates before fallback at '+faultAt, async () => {
  const h=harness({rejectAt:'ensure:call',faultAt}); await assert.rejects(h.post(h.req),e=>e===h.failure); assert.equal(h.calls.json.length,0); assert.equal(h.calls.set.length,0);
});

// Deliberately no application imports, schema initialization, real credentials,
// bcrypt/JWT/ORM/SQL/HTTP/native/backend/runtime/build/recovery/performance calls.
