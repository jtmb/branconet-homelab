import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const [repository,commit,mode,destination,dependencyRoot]=process.argv.slice(2);
const commits={baseline:'51e8cd66379c1f40a95ea02f4da7c8aed848f2a4',candidate:'15786222e4b01b0692ad9aebab99b8734b505c7b'};
assert.equal(commit,commits[mode]);assert(destination&&dependencyRoot);
assert(!path.resolve(destination).startsWith(path.resolve(repository)+path.sep));
const ts=createRequire(path.join(dependencyRoot,'package.json'))('typescript');
const hash=data=>createHash('sha256').update(data).digest('hex');
const hook='(globalThis as typeof globalThis & { __bortusNativeDiag: { span<T>(label: string, operation: () => T): T; attempt<T>(operation: () => T, limit: number, continued: boolean): T; decorateConfig<T>(value: T): T; counter(label: string, value: number): void } }).__bortusNativeDiag';
const targets={
 'src/lib/secret-client.ts':{createSecretTransport:'native.factory',nativeSecrets:'native.storeFactory'},
 'src/lib/cluster-secrets.ts':{secretSummary:'native.summary',list:'native.list'},
 'src/lib/auth.ts':{verifyJWT:'auth.jwt',getSession:'auth.session',getSessionFromHeaders:'auth.headerSession',...(mode==='candidate'?{currentSession:'auth.currentSession'}:{})},
 'src/middleware.ts':{middleware:'auth.middleware'},
 'src/lib/permissions.ts':{[mode==='candidate'?'getOperatorRole':'getCurrentRole']:'auth.role'},
 'src/lib/secrets-api.ts':{GET:'route.secrets',authorize:'auth.authorize'},
 'src/lib/secret-http.ts':{secretResponse:'response.envelope'},
};
if(mode==='candidate')targets['src/lib/secret-client.ts'].slot='native.queue';
await fs.mkdir(destination,{recursive:false});
const manifest={scope:'Protected source-derived native diagnostic, no tracked application or frozen harness edits',commit,mode,diagnostic_only:true,original_source_sha256:{},instrumented_source_sha256:{},hooks:{}};
for(const [relative,functions]of Object.entries(targets)){
 const bytes=execFileSync('git',['-C',repository,'show',commit+':k8s-rewrite/front-end/'+relative]);
 const source=bytes.toString('utf8'),parsed=ts.createSourceFile(relative,source,ts.ScriptTarget.Latest,true);
 const changes=[],counts={};const add=(at,value)=>changes.push({at,value});
 const edgePassThrough=mode==='baseline'&&['src/lib/auth.ts','src/middleware.ts'].includes(relative);
 const spanHook=edgePassThrough?`(${hook}?.span ?? (<T>(_label: string, operation: () => T): T => operation()))`:`${hook}.span`;
 const count=label=>{counts[label]=(counts[label]??0)+1;};
 function wrap(node,label){
  let hasAwait=false;function findAwait(child){if(ts.isAwaitExpression(child))hasAwait=true;ts.forEachChild(child,findAwait);}findAwait(node);
  count(label);add(node.getStart(parsed),`${hasAwait?'await ':''}${spanHook}(${JSON.stringify(label)},${hasAwait?'async ':''}()=> (`);add(node.end,'))');
 }
 function walk(node){
  if((ts.isFunctionDeclaration(node)||ts.isMethodDeclaration(node))&&node.body&&node.name&&functions[node.name.getText(parsed)]){
   const label=functions[node.name.getText(parsed)],async=node.modifiers?.some(item=>item.kind===ts.SyntaxKind.AsyncKeyword);
   count(label);add(node.body.getStart(parsed)+1,`return ${async?'await ':''}${spanHook}(${JSON.stringify(label)},${async?'async ':''}()=>{`);add(node.body.end-1,'});');
  }
  if(relative==='src/lib/secret-client.ts'&&ts.isNewExpression(node)&&node.expression.getText(parsed)==='KubeConfig'){
   count('config.decorate');add(node.getStart(parsed),`${hook}.decorateConfig(${hook}.span("config.construct",()=> (`);add(node.end,')))');
  }
  if(ts.isCallExpression(node)){
   const callee=node.expression.getText(parsed);
   if(callee==='prisma.user.findUnique')wrap(node,'auth.accountSQL');
   if(relative==='src/lib/secret-client.ts'){
    if(mode==='baseline'&&callee==='api.listNamespacedSecret'){
     count('native.attempt');add(node.getStart(parsed),`${hook}.attempt(()=> (`);add(node.end,'),200,!!cursor)');
    }
    if(mode==='candidate'&&callee==='request'&&node.arguments[1]?.getText(parsed).startsWith('route(namespace) + "?limit="')){
     count('native.attempt');add(node.getStart(parsed),`${hook}.attempt(()=> (`);add(node.end,'),limit,!!cursor)');
    }
    if(mode==='baseline'&&callee==='fetch')wrap(node,'native.fetchHeaders');
    if(mode==='baseline'&&callee==='response.text')wrap(node,'native.bodyText');
    if(mode==='candidate'&&callee==='object')wrap(node,'native.objectValidation');
   }
  }
  ts.forEachChild(node,walk);
 }
 walk(parsed);
 for(const label of Object.values(functions))assert.equal(counts[label],1,relative+':'+label);
 if(relative==='src/lib/secret-client.ts'){
  assert.equal(counts['config.decorate'],1);assert.equal(counts['native.attempt'],1);
  if(mode==='baseline'){assert.equal(counts['native.fetchHeaders'],1);assert.equal(counts['native.bodyText'],1);}
  else assert.equal(counts['native.objectValidation'],4);
 }
 let transformed=source;
 for(const change of changes.sort((a,b)=>b.at-a.at))transformed=transformed.slice(0,change.at)+change.value+transformed.slice(change.at);
 if(relative==='src/lib/secret-client.ts'&&mode==='candidate'){
  const before='bytes += chunk.length;';assert.equal(transformed.split(before).length,2);
  transformed=transformed.replace(before,`${hook}.counter("native.deliveredBodyBytes",chunk.length); ${before}`);
 }
 const diagnostics=ts.transpileModule(transformed,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true}).diagnostics;
 assert(!diagnostics?.some(item=>item.category===ts.DiagnosticCategory.Error),'Derived syntax error');
 const target=path.join(destination,relative);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,transformed);
 manifest.original_source_sha256[relative]=hash(bytes);manifest.instrumented_source_sha256[relative]=hash(transformed);manifest.hooks[relative]=counts;
}
manifest.frozen_source_commit=commits.candidate;
if(mode==='baseline')manifest.unobserved_edge_scope={policy:'Absent Node hook in Edge middleware/auth passes through the exact operation without instrumentation',files:['src/middleware.ts','src/lib/auth.ts'],stages:['auth.middleware','auth.headerSession','auth.jwt in Edge middleware'],timings:'unobserved, never zero latency; no Node/Edge causal attribution'};
for(const name of ['whole-server.mjs','run.py','summarize.py'])manifest.original_source_sha256['frozen/'+name]=hash(execFileSync('git',['-C',repository,'show',commits.candidate+':benchmarks/bortus-controlled-perf/'+name]));
await fs.writeFile(path.join(destination,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({commit,mode,source_files:Object.keys(targets).length,syntax_passed:true}));
