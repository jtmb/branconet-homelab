import infrastructureAssert from 'node:assert/strict';
import {readFileSync as infrastructureRead} from 'node:fs';
import {createHash as infrastructureHash} from 'node:crypto';
import {createRequire as infrastructureRequire} from 'node:module';
import {assertCurrentRegisterSources} from '../scripts/auth-register-current-unit-plan.mjs';
assertCurrentRegisterSources(infrastructureRead(new URL('./auth-register-post-source.test.ts',import.meta.url),'utf8'),infrastructureRead(new URL('../src/app/api/auth/register/route.ts',import.meta.url),'utf8'),infrastructureRead(new URL('./auth-register-post-node22.test.mjs',import.meta.url),'utf8'));
infrastructureAssert.equal(process.versions.node,'22.23.3');
const infrastructureCompilerPath=infrastructureRequire(import.meta.url).resolve(process.env.BORTUS_SOURCE_TYPESCRIPT??'typescript');
const infrastructureCompiler=infrastructureRequire(import.meta.url)(infrastructureCompilerPath);
infrastructureAssert.equal(infrastructureCompiler.version,'5.9.3');
infrastructureAssert.equal(infrastructureHash('sha256').update(infrastructureRead(infrastructureCompilerPath)).digest('hex'),'3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675');
const infrastructureOrder=["exact declaration: independent success order, receivers, arguments and status201","falsy gate refuses before body undefined","falsy gate refuses before body null","falsy gate refuses before body false","falsy gate refuses before body 0","falsy gate refuses before body ","truthy gate is characterized without claiming real registration policy","immediate fault routes exact identity to accountFailure at ensure:call","immediate fault routes exact identity to accountFailure at accounts.registrationOpen:get","immediate fault routes exact identity to accountFailure at accounts.registrationOpen:call","immediate fault routes exact identity to accountFailure at req.json:get","immediate fault routes exact identity to accountFailure at req.json:call","immediate fault routes exact identity to accountFailure at schema.safeParse:get","immediate fault routes exact identity to accountFailure at schema.safeParse:call","immediate fault routes exact identity to accountFailure at parsed.success","immediate fault routes exact identity to accountFailure at parsed.data","immediate fault routes exact identity to accountFailure at data.username","immediate fault routes exact identity to accountFailure at data.password","immediate fault routes exact identity to accountFailure at bcrypt.hash:get","immediate fault routes exact identity to accountFailure at bcrypt.hash:call","immediate fault routes exact identity to accountFailure at accounts.register:get","immediate fault routes exact identity to accountFailure at accounts.register:call","immediate fault routes exact identity to accountFailure at user.id","immediate fault routes exact identity to accountFailure at user.username","immediate fault routes exact identity to accountFailure at user.sessionVersion","immediate fault routes exact identity to accountFailure at sign:call","immediate fault routes exact identity to accountFailure at json:get","immediate fault routes exact identity to accountFailure at json:call","immediate fault routes exact identity to accountFailure at response.cookies","immediate fault routes exact identity to accountFailure at cookies.set:get","immediate fault routes exact identity to accountFailure at process.env","immediate fault routes exact identity to accountFailure at env.NODE_ENV","immediate fault routes exact identity to accountFailure at cookies.set:call","await rejection calls accountFailure once at ensure:call","await rejection calls accountFailure once at accounts.registrationOpen:call","await rejection calls accountFailure once at req.json:call","await rejection calls accountFailure once at bcrypt.hash:call","await rejection calls accountFailure once at accounts.register:call","await rejection calls accountFailure once at sign:call","invalid schema nullish-only message [{\"message\":\"public-invalid\"}]","invalid schema nullish-only message []","invalid schema nullish-only message [{}]","invalid schema nullish-only message [{\"message\":null}]","invalid schema nullish-only message [{}]","invalid schema nullish-only message [{\"message\":\"\"}]","invalid schema nullish-only message [{\"message\":0}]","invalid schema nullish-only message [{\"message\":false}]","malformed inert issues route failure null","malformed inert issues route failure undefined","safeParse remains synchronous; returned thenable is not assimilated","null parse result routes failure before hashing","null inert registered user routes failure after register and before signing","strict NODE_ENV production comparison production","strict NODE_ENV production comparison Production","strict NODE_ENV production comparison  production","strict NODE_ENV production comparison undefined","strict NODE_ENV production comparison null","strict NODE_ENV production comparison 0","strict NODE_ENV production comparison true","strict NODE_ENV production comparison [object Object]","strict NODE_ENV production comparison production","setter result is ignored and argument objects are fresh on each invocation","await settlement fences downstream work at ensure","await settlement fences downstream work at open","await settlement fences downstream work at body","await settlement fences downstream work at hash","await settlement fences downstream work at register","await settlement fences downstream work at sign","body result exact identity reaches synchronous parser","hash and sign results preserve exact synthetic identity","response return assimilation failure bypasses try catch success","response return assimilation failure bypasses try catch locked","response return assimilation failure bypasses try catch invalid","response return assimilation failure bypasses try catch catch","accountFailure synchronous throw propagates without retry","accountFailure returned rejected promise propagates without retry","accountFailure thenable settles as async return value","success thenable settles only after cookie call"];
let infrastructureCount=0;
function infrastructureControl(name,...args){infrastructureAssert.equal(name,infrastructureOrder[infrastructureCount++]);return test(name,...args);}
// BEGIN EXACT NATIVE TYPE-ERASED ORIGINAL; only current-source pin, Node22 version and registration recording differ.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

                                                                                                                         
const require = createRequire(import.meta.url);
assert.equal(process.version, 'v22.23.3');
const compiler = require(process.env.BORTUS_SOURCE_TYPESCRIPT ?? 'typescript')            ;
const raw = readFileSync(new URL('../src/app/api/auth/register/route.ts', import.meta.url));
// Canonical LF accepts Git and Windows CRLF; every other byte is pinned.
const expectedCanonical = '601f87718aa72a21682b2a896e13a2cb49da1baa1f7ad1f35b09174413378acd';
assert.equal(createHash('sha256').update(raw.toString('utf8').replace(/\r\n/g, '\n')).digest('hex'), expectedCanonical);
const text = raw.toString('utf8');
const start = text.indexOf('export async function POST(');
assert.ok(start >= 0);
assert.equal(text.indexOf('export async function POST(', start + 1), -1);
const selected = text.slice(start);
const compiled = compiler.transpileModule(selected.replace(/^export /, ''), { compilerOptions: { target: 99, module: 0 }, reportDiagnostics: true });
assert.equal(compiled.diagnostics?.length ?? 0, 0);
const factory = new Function('ensureJwtSecret', 'accounts', 'registerSchema', 'bcrypt', 'signJWT', 'NextResponse', 'AUTH_COOKIE', 'process', 'accountFailure', compiled.outputText + '\nreturn POST;');

               
                                                                                           
                                                                                        
                                                                                             
                                                                       
                                                                               
                                                                             
  
function harness(c         = {}) {
  const trace           = [];
  const fault = Object.freeze({ publicFault: 'registration-source' });
  const body = Object.freeze({ publicBody: 'synthetic-registration' });
  const cookieName = Object.freeze({ publicCookieName: 'inert' });
  const hash = Object.hasOwn(c, 'hash') ? c.hash : Object.freeze({ publicHash: 'placeholder' });
  const token = Object.hasOwn(c, 'token') ? c.token : Object.freeze({ publicToken: 'placeholder' });
  const calls = { open: []               , parse: []               , hash: []               , register: []               , sign: []               , json: []               , set: []               , failures: []                };
  function hit(name        ) { trace.push(name); if (c.faultAt === name) throw fault; }
  function settle(name        , value         ) { hit(name); return c.rejectAt === name ? Promise.reject(fault) : value; }
  const data = { get username() { hit('data.username'); return 'public-user'; }, get password() { hit('data.password'); return 'public-password'; } };
  const parsed = { get success() { hit('parsed.success'); return !c.invalid; }, get data() { hit('parsed.data'); return data; }, get error() { hit('parsed.error'); return { issues: Object.hasOwn(c, 'issues') ? c.issues : [{ message: 'public-invalid' }] }; } };
  const user = { get id() { hit('user.id'); return 'public-id'; }, get username() { hit('user.username'); return 'public-canonical-user'; }, get sessionVersion() { hit('user.sessionVersion'); return 3; } };
  const accounts = {
    get registrationOpen() { hit('accounts.registrationOpen:get'); return function(               ...args           ) { assert.equal(this, accounts); calls.open.push(args); return settle('accounts.registrationOpen:call', Object.hasOwn(c, 'openResult') ? c.openResult : Object.hasOwn(c, 'open') ? c.open : true); }; },
    get register() { hit('accounts.register:get'); return function(               ...args           ) { assert.equal(this, accounts); calls.register.push(args); return settle('accounts.register:call', Object.hasOwn(c, 'registerResult') ? c.registerResult : Object.hasOwn(c, 'user') ? c.user : user); }; },
  };
  const schema = { get safeParse() { hit('schema.safeParse:get'); return function(               ...args           ) { hit('schema.safeParse:call'); assert.equal(this, schema); calls.parse.push(args); return Object.hasOwn(c, 'parseResult') ? c.parseResult : parsed; }; } };
  const bcrypt = { get hash() { hit('bcrypt.hash:get'); return function(               ...args           ) { assert.equal(this, bcrypt); calls.hash.push(args); return settle('bcrypt.hash:call', Object.hasOwn(c, 'hashResult') ? c.hashResult : hash); }; } };
  const response = c.response ?? { publicResponse: 'created' };
  const branchResponse = c.branchResponse ?? { publicResponse: 'refused' };
  const failureResponse = Object.hasOwn(c, 'failureResponse') ? c.failureResponse : { publicResponse: 'account-failure' };
  const cookies = { get set() { hit('cookies.set:get'); return function(               ...args           ) { hit('cookies.set:call'); assert.equal(this, cookies); calls.set.push(args); return c.setterReturn; }; } };
  Object.defineProperty(response, 'cookies', { get() { hit('response.cookies'); return cookies; }, configurable: true });
  const next = { get json() { hit('json:get'); return function(               ...args           ) { hit('json:call'); assert.equal(this, next); calls.json.push(args); return (args[1]                   ).status === 201 ? response : branchResponse; }; } };
  const req = { get json() { hit('req.json:get'); return function(               ...args           ) { assert.equal(this, req); assert.deepEqual(args, []); return settle('req.json:call', Object.hasOwn(c, 'bodyResult') ? c.bodyResult : body); }; } };
  const env = { get NODE_ENV() { hit('env.NODE_ENV'); return Object.hasOwn(c, 'env') ? c.env : 'test'; } };
  const fakeProcess = { get env() { hit('process.env'); return env; } };
  const ensure = () => settle('ensure:call', c.ensureResult);
  const sign = (...args           ) => { calls.sign.push(args); return settle('sign:call', Object.hasOwn(c, 'signResult') ? c.signResult : token); };
  const fail = (...args           ) => { hit('accountFailure:call'); calls.failures.push(args); if (c.failureThrows) throw fault; return failureResponse; };
  const post = factory(ensure, accounts, schema, bcrypt, sign, next, cookieName, fakeProcess, fail)                                      ;
  return { post, req, trace, calls, fault, body, hash, token, cookieName, response, branchResponse, failureResponse, user };
}
const successOrder = ['ensure:call','accounts.registrationOpen:get','accounts.registrationOpen:call','req.json:get','req.json:call','schema.safeParse:get','schema.safeParse:call','parsed.success','parsed.data','data.username','data.password','bcrypt.hash:get','bcrypt.hash:call','accounts.register:get','accounts.register:call','user.id','user.username','user.sessionVersion','sign:call','json:get','user.id','user.username','json:call','response.cookies','cookies.set:get','process.env','env.NODE_ENV','cookies.set:call'];

infrastructureControl('exact declaration: independent success order, receivers, arguments and status201', async () => {
  const h=harness(); assert.equal(await h.post(h.req),h.response); assert.deepEqual(h.trace,successOrder);
  assert.deepEqual(h.calls.open,[[]]); assert.deepEqual(h.calls.parse,[[h.body]]);
  assert.deepEqual(h.calls.hash,[['public-password',12]]);
  assert.deepEqual(h.calls.register,[[{username:'public-user',passwordHash:h.hash}]]);
  assert.deepEqual(h.calls.sign,[[{sub:'public-id',username:'public-canonical-user',sessionVersion:3}]]);
  assert.deepEqual(h.calls.json,[[{id:'public-id',username:'public-canonical-user'},{status:201}]]);
  assert.deepEqual(h.calls.set,[[h.cookieName,h.token,{httpOnly:true,secure:false,sameSite:'lax',path:'/',maxAge:604800}]]);
  assert.deepEqual(Object.keys(h.calls.set[0][2]          ),['httpOnly','secure','sameSite','path','maxAge']); assert.deepEqual(h.calls.failures,[]);
});
for (const open of [undefined,null,false,0,'']) infrastructureControl('falsy gate refuses before body '+String(open),async()=>{
  const h=harness({open}); assert.equal(await h.post(h.req),h.branchResponse);
  assert.deepEqual(h.trace,['ensure:call','accounts.registrationOpen:get','accounts.registrationOpen:call','json:get','json:call']);
  assert.deepEqual(h.calls.json,[[{error:'Registration is locked. Set ALLOW_REGISTRATION=true to enable.'},{status:403}]]);
  for(const k of ['parse','hash','register','sign','set','failures']         ) assert.equal(h.calls[k].length,0);
});
infrastructureControl('truthy gate is characterized without claiming real registration policy',async()=>{const h=harness({open:{publicGate:'truthy'}});assert.equal(await h.post(h.req),h.response);});
for(const faultAt of [...new Set(successOrder)]) infrastructureControl('immediate fault routes exact identity to accountFailure at '+faultAt,async()=>{
  const h=harness({faultAt}); assert.equal(await h.post(h.req),h.failureResponse); assert.deepEqual(h.calls.failures,[[h.fault]]);
  const i=successOrder.indexOf(faultAt); assert.deepEqual(h.trace,[...successOrder.slice(0,i+1),'accountFailure:call']);
});
for(const rejectAt of ['ensure:call','accounts.registrationOpen:call','req.json:call','bcrypt.hash:call','accounts.register:call','sign:call']) infrastructureControl('await rejection calls accountFailure once at '+rejectAt,async()=>{
  const h=harness({rejectAt}); assert.equal(await h.post(h.req),h.failureResponse);assert.deepEqual(h.calls.failures,[[h.fault]]);assert.equal(h.calls.set.length,0);
});
for(const issues of [[{message:'public-invalid'}],[],[{}],[{message:null}],[{message:undefined}],[{message:''}],[{message:0}],[{message:false}]]) infrastructureControl('invalid schema nullish-only message '+JSON.stringify(issues),async()=>{
  const h=harness({invalid:true,issues});assert.equal(await h.post(h.req),h.branchResponse);
  const message=(issues[0]                                )?.message??'Invalid input';assert.deepEqual(h.calls.json,[[{error:message},{status:400}]]);
  for(const k of ['hash','register','sign','set','failures']         )assert.equal(h.calls[k].length,0);
});
for(const issues of [null,undefined]) infrastructureControl('malformed inert issues route failure '+String(issues),async()=>{const h=harness({invalid:true,issues});assert.equal(await h.post(h.req),h.failureResponse);assert.equal(h.calls.failures.length,1);assert.equal(h.calls.hash.length,0);});
infrastructureControl('safeParse remains synchronous; returned thenable is not assimilated',async()=>{
  let touched=false;const h=harness({parseResult:{get then(){touched=true;throw new Error('unread');}}});assert.equal(await h.post(h.req),h.failureResponse);assert.equal(touched,false);assert.equal(h.calls.failures.length,1);
});
infrastructureControl('null parse result routes failure before hashing',async()=>{const h=harness({parseResult:null});assert.equal(await h.post(h.req),h.failureResponse);assert.equal(h.calls.hash.length,0);assert.equal(h.calls.failures.length,1);});
infrastructureControl('null inert registered user routes failure after register and before signing',async()=>{const h=harness({user:null});assert.equal(await h.post(h.req),h.failureResponse);assert.equal(h.calls.register.length,1);assert.equal(h.calls.sign.length,0);assert.equal(h.calls.failures.length,1);});
for(const env of ['production','Production',' production',undefined,null,0,true,{},Object('production')]) infrastructureControl('strict NODE_ENV production comparison '+String(env),async()=>{const h=harness({env});await h.post(h.req);assert.equal((h.calls.set[0][2]                    ).secure,env==='production');});
infrastructureControl('setter result is ignored and argument objects are fresh on each invocation',async()=>{
  let touched=false;const ignored=Object.defineProperty({},'then',{get(){touched=true;throw new Error('unread setter result');}});const h=harness({setterReturn:ignored});await h.post(h.req);await h.post(h.req);assert.equal(touched,false);
  for(const group of [h.calls.register,h.calls.sign,h.calls.json])assert.notEqual(group[0][0],group[1][0]);assert.notEqual(h.calls.json[0][1],h.calls.json[1][1]);assert.notEqual(h.calls.set[0][2],h.calls.set[1][2]);
});
for(const hold of ['ensure','open','body','hash','register','sign']         ) infrastructureControl('await settlement fences downstream work at '+hold,async()=>{
  let release                                  ;const held=new Promise         (resolve=>{release=resolve;});const configs                           ={ensure:{ensureResult:held},open:{openResult:held},body:{bodyResult:held},hash:{hashResult:held},register:{registerResult:held},sign:{signResult:held}};
  const h=harness(configs[hold]);const pending=h.post(h.req);for(let i=0;i<10;i++)await Promise.resolve();
  const marker={ensure:'ensure:call',open:'accounts.registrationOpen:call',body:'req.json:call',hash:'bcrypt.hash:call',register:'accounts.register:call',sign:'sign:call'}[hold];assert.deepEqual(h.trace,successOrder.slice(0,successOrder.indexOf(marker)+1));assert.ok(release);
  release({ensure:undefined,open:true,body:h.body,hash:h.hash,register:h.user,sign:h.token}[hold]);assert.equal(await pending,h.response);assert.deepEqual(h.calls.failures,[]);
});
infrastructureControl('body result exact identity reaches synchronous parser',async()=>{const value={publicBody:'alternate'};const h=harness({bodyResult:value});await h.post(h.req);assert.equal(h.calls.parse[0][0],value);});
infrastructureControl('hash and sign results preserve exact synthetic identity',async()=>{const hash={publicHash:'alternate'};const token={publicToken:'alternate'};const h=harness({hash,token});await h.post(h.req);assert.equal((h.calls.register[0][0]                          ).passwordHash,hash);assert.equal(h.calls.set[0][1],token);});
for(const branch of ['success','locked','invalid','catch']         ) infrastructureControl('response return assimilation failure bypasses try catch '+branch,async()=>{
  const marker={publicFault:'return-assimilation'};const response=Object.defineProperty({},'then',{get(){throw marker;}});
  const h=harness(branch==='success'?{response}:branch==='locked'?{open:false,branchResponse:response}:branch==='invalid'?{invalid:true,branchResponse:response}:{rejectAt:'ensure:call',failureResponse:response});
  await assert.rejects(h.post(h.req),e=>e===marker);assert.equal(h.calls.failures.length,branch==='catch'?1:0);assert.equal(h.calls.set.length,branch==='success'?1:0);
});
infrastructureControl('accountFailure synchronous throw propagates without retry',async()=>{const h=harness({rejectAt:'ensure:call',failureThrows:true});await assert.rejects(h.post(h.req),e=>e===h.fault);assert.equal(h.calls.failures.length,1);assert.equal(h.calls.json.length,0);});
infrastructureControl('accountFailure returned rejected promise propagates without retry',async()=>{const marker={publicFault:'failure-result'};const h=harness({rejectAt:'ensure:call',failureResponse:Promise.reject(marker)});await assert.rejects(h.post(h.req),e=>e===marker);assert.equal(h.calls.failures.length,1);});
infrastructureControl('accountFailure thenable settles as async return value',async()=>{const result={publicResult:'failure-value'};const h=harness({rejectAt:'ensure:call',failureResponse:{then(resolve                      ){resolve(result);}}});assert.equal(await h.post(h.req),result);assert.equal(h.calls.failures.length,1);});
infrastructureControl('success thenable settles only after cookie call',async()=>{let h                           ;const result={publicResult:'created'};h=harness({response:{then(resolve                      ){assert.equal(h.calls.set.length,1);resolve(result);}}});assert.equal(await h.post(h.req),result);assert.equal(h.calls.failures.length,0);});

// Imports, schema initialization and callee implementations are outside scope.
// Actual accounts/credentials/auth/JWT/cookies/password hashing/Prisma/SQL/ORM/
// HTTP/native/backend/build/server/recovery/performance/production stay inert.

// END EXACT NATIVE TYPE-ERASED ORIGINAL
infrastructureAssert.equal(infrastructureCount,infrastructureOrder.length);
