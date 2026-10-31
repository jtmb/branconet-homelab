'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Worker,isMainThread,parentPort,workerData,threadId}=require('node:worker_threads');
const {isAscii}=require('node:buffer');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const out=__dirname,inputs=JSON.parse(fs.readFileSync(path.join(out,'inputs.json')));
const names=['apps',...Array.from({length:17},(_,i)=>'scope-'+String(i).padStart(2,'0'))];
const profiles=[{name:'public334-small',count:334,annotation:44},{name:'public200',count:200,annotation:44},{name:'public1000',count:1000,annotation:44},{name:'public1000-long-annotations16KiB',count:1000,annotation:16384}];
function loadParser(clock) {
  const bytes=fs.readFileSync(path.join(out,'exact-parser.js'));
  const ctx={Buffer,TextDecoder,isAscii,AbortController,exports:{},Date:clock?{now:clock}:Date};vm.createContext(ctx);vm.runInContext(bytes.toString('utf8'),ctx);return ctx;
}
function split(b,n=16384) {const result=[];for(let i=0;i<b.length;i+=n){const piece=Buffer.allocUnsafeSlow(Math.min(n,b.length-i));b.copy(piece,0,i,i+piece.length);result.push(piece);}return result;}
function fixture(profile,scope) {
  const namespace=names[scope],items=[];
  for(let local=0;local<Math.max(0,Math.ceil((profile.count-scope)/18));local++){
    const index=scope+local*18;
    items.push({apiVersion:'v1',kind:'Secret',metadata:{namespace,name:'secret-'+String(index).padStart(5,'0'),uid:'native-uid-'+index,resourceVersion:'10',labels:{fixture:'metadata'},annotations:{'kubectl.kubernetes.io/last-applied-configuration':'A'.repeat(profile.annotation)}},type:'Opaque',data:{payload:Buffer.alloc(64,7).toString('base64'),original_under_score:'',empty:''}});
  }
  return Buffer.from(JSON.stringify({apiVersion:'v1',kind:'SecretList',metadata:{resourceVersion:'10'},items}));
}
if(!isMainThread){
  if(workerData.role==='producer'){
    const bodies=profiles.map(p=>names.map((_,scope)=>fixture(p,scope)));
    parentPort.postMessage({ready:true,threadId,bodyManifest:bodies.map((row,i)=>({profile:profiles[i].name,totalBytes:row.reduce((n,b)=>n+b.length,0),pages:row.map(b=>({bytes:b.length,sha256:sha(b)}))}))});
    parentPort.on('message',job=>{if(job.shutdown){parentPort.close();return;}setTimeout(()=>{const chunks=split(bodies[job.profile][job.scope]);parentPort.postMessage({id:job.id,chunks,readyAt:performance.now()});},12);});
  }else{
    const ctx=loadParser();parentPort.postMessage({ready:true,threadId,compiledSHA256:sha(fs.readFileSync(path.join(out,'exact-parser.js')))});
    parentPort.on('message',job=>{
      if(job.shutdown){parentPort.close();return;}
      const execute=()=>{const start=performance.now();try{
        const chunks=job.chunks.map(b=>Buffer.from(b.buffer,b.byteOffset,b.byteLength));
        const value=ctx.parse(chunks,job.namespace,200);parentPort.postMessage({id:job.id,ok:true,value,parseMs:performance.now()-start,startedAt:start,endedAt:performance.now()});
      }catch(error){parentPort.postMessage({id:job.id,ok:false,status:error.status===503?503:0,parseMs:performance.now()-start,startedAt:start,endedAt:performance.now()});}};
      if(job.controlDelayMs)setTimeout(execute,job.controlDelayMs);else execute();
    });
  }
  return;
}
const globalStart=performance.now(),globalDeadline=globalStart+55000;
const report={startedUtc:new Date().toISOString(),pid:process.pid,node:process.version,scope:'One public-only off-thread mechanism diagnostic; exact parser and budget, modeled four held namespace/request slots, no TLS/auth/production changes',caps:inputs.caps,source:inputs.productionSource,profileManifest:[],cold:[],timings:[],differential:{cases:0,refusals:0},controls:[],failures:[],workers:[],performanceAcceptance:false,limitations:[
  'Timer-only producer runs on a distinct worker so inline endpoint blocking cannot delay the producer itself; IPC body delivery is common to both modes. No actual TLS, SDK authentication, API, KubeConfig, native retries or HTTP serialization is modeled.',
  'One parser worker and one producer worker share the same two-CPU affinity. No production process pool, source modification, credential/value cache or changed frozen benchmark.',
  'Full exact metadata is cloned back from parser worker, including long public annotation strings; no DTO/unknown-field loss. Body bytes charged once before buffering; copying can transiently duplicate memory and is not a32MiB RSS promise.',
  'Namespace jobs hold four slots through full parse and post-parse deadline checks; callbacks, samples, IPC and producer instrumentation add overhead. No result establishes A07/A21 or explains the full34ms endpoint gap.',
  'Cancellation/deadline controls model parse ownership and late reply refusal; they do not replace real SDK/socket cancellation or final integrated HTTP tests.'
]};
fs.writeFileSync(path.join(out,'started.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
process.on('exit',code=>fs.writeFileSync(path.join(out,'child-exit.json'),JSON.stringify({pid:process.pid,exitCode:code,completedUtc:new Date().toISOString()})+'\n'));
const checked=()=>{if(performance.now()>=globalDeadline)throw Error('Bounded diagnostic global deadline');};
let nextId=0,producer,parser,watchdog;
const producerJobs=new Map(),parserJobs=new Map();
function freshWorker(role){return new Worker(__filename,{workerData:{role},resourceLimits:{maxOldGenerationSizeMb:256,maxYoungGenerationSizeMb:32}});}
async function stopWorker(worker){
  if(!worker)return null;if(worker.threadId===-1)return {alreadyStopped:true};
  return await new Promise(resolve=>{let finished=false;const complete=(code,forced)=>{if(finished)return;finished=true;clearTimeout(timer);resolve({exitCode:code,forced});};const timer=setTimeout(()=>worker.terminate().then(code=>complete(code,true)),500);worker.once('exit',code=>complete(code,false));worker.postMessage({shutdown:true});});
}
async function ready(worker,role){
  const begin=performance.now();return new Promise((resolve,reject)=>{
    worker.once('error',reject);worker.once('exit',code=>{if(code!==0)reject(Error('Owned worker failed'));});
    worker.on('message',msg=>{
      if(msg.ready){report.workers.push({role,threadId:msg.threadId,readyMs:performance.now()-begin});resolve(msg);return;}
      const jobs=role==='producer'?producerJobs:parserJobs,entry=jobs.get(msg.id);if(!entry)return;
      jobs.delete(msg.id);entry.resolve(msg);
    });
  });
}
function producerRequest(profile,scope){
  const id=++nextId;return new Promise(resolve=>{producerJobs.set(id,{resolve});producer.postMessage({id,profile,scope});});
}
function parserRequest(chunks,namespace,controlDelayMs=0){
  const id=++nextId,begin=performance.now();let postSyncMs;
  const promise=new Promise(resolve=>{parserJobs.set(id,{resolve:msg=>resolve({...msg,roundTripMs:performance.now()-begin,postSyncMs})});const post=performance.now();parser.postMessage({id,chunks,namespace,controlDelayMs});postSyncMs=performance.now()-post;});return promise;
}
const actualFiles={};
for(const row of inputs.sources){
  const raw=fs.readFileSync(path.join(out,path.basename(row.path)));assert.equal(sha(raw),row.sha256);assert.equal(sha(fs.readFileSync(path.join(inputs.repo,row.path))),row.workingSHA256);actualFiles[path.basename(row.path)]=raw.toString('utf8');
}
assert.equal(sha(fs.readFileSync(inputs.compiler)),inputs.compilerSHA256);assert.equal(sha(fs.readFileSync(inputs.node)),inputs.nodeSHA256);
const cluster=actualFiles['cluster-secrets.ts'];
const prefix=cluster.slice(0,cluster.indexOf('export function secretSummary'));
const helper=actualFiles['secret-ascii-span.ts'].replace(/^import .*\r?\n/gm,'');
const summary=actualFiles['secret-summary-json.ts'].replace(/^import .*\r?\n/gm,'');
const compileInput=prefix+'\n'+helper+'\n'+summary+'\nglobalThis.parse=parseSecretSummaryPage;globalThis.Budget=SecretListBudget;globalThis.SecretError=SecretError;';
const ts=require(inputs.compiler);const js=ts.transpileModule(compileInput,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
fs.writeFileSync(path.join(out,'exact-parser-input.ts'),compileInput,{flag:'wx'});fs.writeFileSync(path.join(out,'exact-parser.js'),js,{flag:'wx'});
report.compiled={inputSHA256:sha(Buffer.from(compileInput)),outputSHA256:sha(Buffer.from(js)),summaryRawSHA256:sha(Buffer.from(actualFiles['secret-summary-json.ts'])),productionParserBodyUnchanged:true};
const ctx=loadParser();
const outcomeInline=(chunks,namespace='apps')=>{try{return {ok:true,value:ctx.parse(chunks,namespace,200)}}catch(error){return {ok:false,status:error.status}}};
const canonical=x=>JSON.stringify(x);
async function operation(mode,profileIndex,coldFactory){
  checked();const start=performance.now(),metrics={mode,profile:profiles[profileIndex].name,wallMs:0,activeMax:0,chargedBytes:0,acceptedItems:0,callbackSyncMs:[],workerParseMs:[],workerRoundTripMs:[],workerPostSyncMs:[],producerReadyToDispatchMs:[],callbackLoopGapMs:[],sourcePageCount:18,resultSHA256:null};
  if(coldFactory)await coldFactory();
  const budget=new ctx.Budget(Date.now()+15000),all=Array.from({length:18},()=>[]);let next=0,active=0,published=0;
  let last=performance.now();const loop=setInterval(()=>{const now=performance.now();metrics.callbackLoopGapMs.push(now-last);last=now;},1);
  const worker=async()=>{
    try{while(next<18){budget.check();const scope=next++;active++;metrics.activeMax=Math.max(metrics.activeMax,active);assert(active<=4);
      try{
        const requestDeadline=Math.min(budget.deadline,Date.now()+8000);const response=await producerRequest(profileIndex,scope);const chunks=response.chunks.map(b=>Buffer.from(b.buffer,b.byteOffset,b.byteLength));metrics.producerReadyToDispatchMs.push(performance.now()-response.readyAt);
        let bytes=0;for(const b of chunks){bytes+=b.length;budget.consumeBytes(b.length);}assert(bytes<=4194304&&chunks.length<=16384);budget.check();assert(Date.now()<requestDeadline);
        const sync=performance.now();let value;
        if(mode==='inline'){value=ctx.parse(chunks,names[scope],200);metrics.callbackSyncMs.push(performance.now()-sync);}
        else{const task=parserRequest(chunks,names[scope]);metrics.callbackSyncMs.push(performance.now()-sync);const parsed=await task;assert.equal(parsed.ok,true);metrics.workerParseMs.push(parsed.parseMs);metrics.workerRoundTripMs.push(parsed.roundTripMs);metrics.workerPostSyncMs.push(parsed.postSyncMs);value=parsed.value;}
        budget.check();assert(Date.now()<requestDeadline);budget.consumeItems(value.items.length);all[scope]=value.items;published+=value.items.length;
      }finally{active--;}
    }}catch(error){budget.fail(error);}
  };
  try{await Promise.all(Array.from({length:4},worker));budget.check();metrics.wallMs=performance.now()-start;assert.equal(active,0);assert.equal(published,profiles[profileIndex].count);assert(budget.bytes<=33554432&&budget.items<=10000);metrics.chargedBytes=budget.bytes;metrics.acceptedItems=budget.items;
    // Full differential serialization is deliberately outside complete-wall timing.
    const value=all.flat();metrics.resultSHA256=sha(Buffer.from(canonical(value)));assert(!canonical(value).includes(Buffer.alloc(64,7).toString('base64')));return metrics;
  }finally{clearInterval(loop);budget.finish();assert.equal(active,0);}
}
function corpus(){
  const meta='{"namespace":"apps","name":"public","uid":"public-uid","resourceVersion":"10"}';
  const base=(m=meta)=>Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{},"items":[{"apiVersion":"v1","kind":"Secret","metadata":'+m+',"data":{"__proto__":"AA==","empty":""},"unknown":{"nested":["PUBLIC_SKIPPED"]}}]}');
  const nested=n=>'['.repeat(n)+'0'+']'.repeat(n);
  const rows=[{bytes:base(),valid:true},{bytes:base(meta.slice(0,-1)+',"__proto__":{"public":true},"constructor":false,"duplicate":1,"duplicate":2}'),valid:true},{bytes:base(meta.replace('public-uid','snow-雪😀\\n\\uD800')),valid:true},{bytes:base(meta.replace('namespace','namesp\\u0061ce')),valid:true}];
  for(const n of [29,30,31,32,33])rows.push({bytes:base(meta.slice(0,-1)+',"duplicate":'+nested(n)+',"duplicate":0}'),valid:undefined});
  for(const malformed of ['{"a":1,}','{"a":01}','{"a":truefalse}','{"a":"\\x"}','{"a":"\\u00gg"}','{"a":"\u0000"}','{"a":undefined}','{"a":1e}','{"a":]}'])rows.push({bytes:base(meta.slice(0,-1)+',"extra":'+malformed+'}'),valid:false});
  for(const bytes of [[0xc0,0x80],[0xed,0xa0,0x80],[0xf4,0x90,0x80,0x80],[0x80],[0xf0,0x9f]]){
    const b=base(),i=b.indexOf('public-uid');rows.push({bytes:Buffer.concat([b.subarray(0,i),Buffer.from(bytes),b.subarray(i)]),valid:false});
  }
  rows.push({bytes:Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),base()]),valid:false});return rows;
}
async function controls(){
  for(const mode of ['inline','worker']){
    const b=fixture(profiles[0],0),chunks=split(b),budget=new ctx.Budget(Date.now()+15000);budget.consumeBytes(b.length);
    const start=performance.now();let active=1,published=0,heldAfterAbort=false;
    if(mode==='worker'){
      const task=parserRequest(chunks,'apps',20);budget.fail(new ctx.SecretError(503,'Public diagnostic cancellation'));heldAfterAbort=active===1;await task;
    }else{ctx.parse(chunks,'apps',200);budget.fail(new ctx.SecretError(503,'Public diagnostic cancellation'));heldAfterAbort=active===1;}
    try{budget.check();published++;}catch(error){assert.equal(error.status,503);}finally{active--;budget.finish();}
    assert.equal(published,0);assert.equal(active,0);assert(heldAfterAbort);assert.equal(budget.bytes,b.length);
    report.controls.push({mode,case:'Cancellation after accepted body/parse ownership fences late result',elapsedMs:performance.now()-start,heldUntilSettlement:true,published:0,activeAfter:0,chargedBytes:budget.bytes});
    let now=1000;const test=loadParser(()=>now),deadlineBudget=new test.Budget(1001);deadlineBudget.consumeBytes(b.length);let parsed;
    if(mode==='worker')parsed=await parserRequest(chunks,'apps');else parsed={value:test.parse(chunks,'apps',200)};
    assert(parsed.value);now=1002;assert.throws(()=>deadlineBudget.check(),{status:503});report.controls.push({mode,case:'Post-parse original-budget clock crosses deadline',published:0,chargedBytes:deadlineBudget.bytes});deadlineBudget.finish();
    const expired=new ctx.Budget(Date.now()-1);assert.throws(()=>expired.check(),{status:503});report.controls.push({mode,case:'Expired/pre-aborted budget starts no owned job',requestsStarted:0});
  }
  const b=fixture(profiles[0],0),budget=new ctx.Budget(Date.now()+8);budget.consumeBytes(b.length);const task=parserRequest(split(b),'apps',20);let active=1;await new Promise(r=>setTimeout(r,10));assert.throws(()=>budget.check(),{status:503});assert.equal(active,1);await task;active--;budget.finish();report.controls.push({mode:'worker',case:'Actual deadline while parser owned keeps slot until reply; no publication',published:0,activeAfter:active,heldUntilSettlement:true});
  assert.equal(producerJobs.size,0);assert.equal(parserJobs.size,0);
}
(async()=>{
  watchdog=setTimeout(()=>{report.failures.push({phase:'global','classification':'Owned55s deadline'});process.exitCode=1;producer?.terminate();parser?.terminate();},55000);watchdog.unref();
  try{
    producer=freshWorker('producer');const producerInfo=await ready(producer,'producer');report.profileManifest=producerInfo.bodyManifest;
    for(const p of producerInfo.bodyManifest){assert(p.totalBytes<=33554432);assert(p.pages.every(x=>x.bytes<=4194304));}
    report.cold.push(await operation('inline',0));
    const cold=await operation('worker',0,async()=>{const start=performance.now();parser=freshWorker('parser');const p=await ready(parser,'parser');assert.equal(p.compiledSHA256,report.compiled.outputSHA256);report.coldParserStartupMs=performance.now()-start;});report.cold.push(cold);
    assert.equal(report.cold[0].resultSHA256,report.cold[1].resultSHA256);
    for(const row of corpus())for(const cut of new Set([0,1,Math.floor(row.bytes.length/2),row.bytes.length-1,row.bytes.length])){
      checked();const chunks=[row.bytes.subarray(0,cut),Buffer.alloc(0),row.bytes.subarray(cut)],a=outcomeInline(chunks),b=await parserRequest(chunks,'apps');assert.equal(a.ok,b.ok);if(row.valid!==undefined)assert.equal(a.ok,row.valid);
      if(a.ok)assert.equal(canonical(a.value),canonical(b.value));else{assert.equal(a.status,503);assert.equal(b.status,503);report.differential.refusals++;}report.differential.cases++;
    }
    await controls();
    for(let p=0;p<profiles.length;p++)for(let observation=0;observation<7;observation++){
      const order=observation%2===0?['inline','worker']:['worker','inline'];let prior;
      for(const mode of order){checked();const result=await operation(mode,p);result.observation=observation;report.timings.push(result);if(prior){assert.equal(prior.resultSHA256,result.resultSHA256);assert.equal(prior.chargedBytes,result.chargedBytes);assert.equal(prior.acceptedItems,result.acceptedItems);}prior=result;fs.writeFileSync(path.join(out,'progress.json'),JSON.stringify({phase:'timings',rows:report.timings.length,profile:p,observation})+'\n');}
    }
    report.passed=true;
  }catch(error){report.passed=false;report.failures.push({phase:report.timings.length?'timings':'setup-equivalence-controls',classification:error instanceof assert.AssertionError?'assertion':'bounded-runtime',stackFrames:String(error.stack||'').split('\n').filter(l=>/^\s+at /.test(l)).map(l=>l.replace(/\(.*?diagnostic.cjs:/,'(diagnostic.cjs:')).slice(0,4)});process.exitCode=1;}
  finally{
    clearTimeout(watchdog);report.cleanup={producerExit:await stopWorker(producer),parserExit:await stopWorker(parser),producerJobs:producerJobs.size,parserJobs:parserJobs.size};report.completedUtc=new Date().toISOString();report.elapsedMs=performance.now()-globalStart;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
  }
})();
