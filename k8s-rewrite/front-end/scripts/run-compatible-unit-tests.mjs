import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,readdirSync,lstatSync,existsSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {unitTestPlan,executionFor,executionBatches,artifactStages,assertArtifactState,dispatchForBatch} from './current-packaging-unit-plan.mjs';
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
export function qualificationFingerprint(root,plan){
 const files=[];
 function visit(relative){
  for(const name of readdirSync(join(root,relative)).sort()){
   const file=join(relative,name),stat=lstatSync(join(root,file));assert.equal(stat.isSymbolicLink(),false,'source symlink');
   if(stat.isDirectory())visit(file);else {assert.ok(stat.isFile());files.push(file);}
  }
 }
 for(const dir of ['src','tests','scripts','prisma'])visit(dir);
 files.push('package.json','package-lock.json','tsconfig.json','next.config.ts','eslint.config.mjs','native/secret-flat-selector.c','runtime/direct-account-reader-worker.cjs');
 return digest(JSON.stringify({selected:plan.selected,replacements:plan.replacements,packagingDispatch:plan.packagingDispatch,publicAuthority:plan.publicAuthority,inputs:files.sort().map(file=>[file,digest(readFileSync(join(root,file)))])}));
}
export function validatePortableProof(proof,context){
 assert.equal(proof.schema,1,'portable proof schema');assert.equal(proof.phase,'portable-passed','portable phase must pass exactly once');
 assert.equal(proof.runId,context.runId,'run identity');assert.equal(proof.sourceFingerprint,context.sourceFingerprint,'source provenance');
 assert.equal(proof.node,context.node,'runtime version');assert.equal(proof.nodeSHA256,context.nodeSHA256,'runtime binary');
 assert.deepEqual(proof.portable,{tests:5,pass:5,fail:0,cancelled:0,skipped:0,todo:0},'complete original portable fixture');
}
function artifactState(root){
 const file=join(root,'native/secret-flat-selector.node');
 try {const stat=lstatSync(file);return {exists:true,regularFile:stat.isFile()&&!stat.isSymbolicLink(),sha256:stat.isFile()?digest(readFileSync(file)):undefined};}
 catch(error){if(error.code==='ENOENT')return {exists:false};throw error;}
}
export async function runBatch(root,batch,scheduling=['--test-concurrency=2']){
 console.log('BORTUS_COMPAT_BATCH '+JSON.stringify(batch));
 const dispatch=dispatchForBatch(root,batch.files);
 const result=spawnSync(process.execPath,[...batch.flags,'--import','tsx',...dispatch.flags,'--test',...scheduling,...batch.files],{cwd:root,env:{...process.env,...dispatch.env},encoding:'utf8',maxBuffer:64*1024*1024});
 if(result.stdout)await new Promise((resolve,reject)=>process.stdout.write(result.stdout,error=>error?reject(error):resolve()));
 if(result.stderr)await new Promise((resolve,reject)=>process.stderr.write(result.stderr,error=>error?reject(error):resolve()));
 if(result.error)throw result.error;assert.equal(result.signal,null,'unit child terminated');
 const totals={};for(const key of ['tests','pass','fail','cancelled','skipped','todo']){
  const found=[...result.stdout.matchAll(new RegExp('^# '+key+' (\\d+)\\s*$','gm'))];assert.equal(found.length,1,'missing/ambiguous TAP total: '+key);totals[key]=Number(found[0][1]);
 }
 return {status:result.status??1,totals,files:batch.files,flags:batch.flags};
}
export async function main(args=process.argv.slice(2)){
 const root=fileURLToPath(new URL('../',import.meta.url)),plan=unitTestPlan(root);
 assert.equal(process.versions.node,'22.23.3');
 if(args[0]==='--plan'){assert.equal(args.length,1);console.log(JSON.stringify({plan,stages:artifactStages(plan.selected)}));return;}
 if(args[0]==='--group'){
  const selected=executionFor(plan,args);let status=0;
  for(const batch of executionBatches(selected)){const result=await runBatch(root,batch,['--test-concurrency=1']);status ||= result.status;}
  process.exitCode=status;return;
 }
 assert.ok(args.length===0||(args.length===1&&['--portable','--remaining'].includes(args[0])),'unknown aggregate arguments');
 const path=process.env.BORTUS_UNIT_RECEIPT,runId=process.env.BORTUS_UNIT_RUN_ID;
 assert.ok(path&&runId,'BORTUS_UNIT_RECEIPT and BORTUS_UNIT_RUN_ID are required; no state fallback');
 const stages=artifactStages(plan.selected),context={runId,sourceFingerprint:qualificationFingerprint(root,plan),node:process.versions.node,nodeSHA256:digest(readFileSync(process.execPath))};
 console.log('BORTUS_COMPAT_PLAN '+JSON.stringify({selected:plan.selected.length,stages,runId}));
 if(args[0]!=='--remaining'){
  assert.equal(existsSync(path),false,'preserve previous aggregate proof');assertArtifactState(stages[0],artifactState(root));
  const portable=await runBatch(root,stages[0]);assert.equal(portable.status,0,'portable fixture failed');
  const proof={schema:1,phase:'portable-passed',...context,portable:portable.totals,startedUTC:new Date().toISOString()};
  validatePortableProof(proof,context);assertArtifactState(stages[0],artifactState(root));writeFileSync(path,JSON.stringify(proof,null,2)+'\n',{flag:'wx'});
  if(args[0]==='--portable')return;
  assertArtifactState(stages[1],artifactState(root));
  const build=spawnSync(process.execPath,['scripts/build-secret-flat-native.mjs'],{cwd:root,stdio:'inherit'});
  if(build.error)throw build.error;assert.equal(build.signal,null);assert.equal(build.status,0,'genuine native preparation failed');
 }
 const proof=JSON.parse(readFileSync(path,'utf8'));validatePortableProof(proof,context);assertArtifactState(stages[2],artifactState(root));
 proof.phase='remaining-started';writeFileSync(path,JSON.stringify(proof,null,2)+'\n');
 const results=[];let status=0;
 for(const batch of stages.slice(2)){
  assertArtifactState(batch,artifactState(root));const result=await runBatch(root,batch);results.push(result);status ||= result.status;
 }
 assert.equal(qualificationFingerprint(root,plan),context.sourceFingerprint,'source changed during aggregate execution');
 proof.phase=status?'failed':'complete';proof.remaining=results;proof.finishedUTC=new Date().toISOString();
 proof.totals=Object.fromEntries(Object.keys(proof.portable).map(key=>[key,proof.portable[key]+results.reduce((n,r)=>n+r.totals[key],0)]));
 writeFileSync(path,JSON.stringify(proof,null,2)+'\n');console.log('BORTUS_COMPAT_RESULT '+JSON.stringify({phase:proof.phase,selected:plan.selected.length,totals:proof.totals}));process.exitCode=status;
}
if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url)await main();
