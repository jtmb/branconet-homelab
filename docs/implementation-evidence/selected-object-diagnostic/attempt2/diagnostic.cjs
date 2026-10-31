'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const {isAscii}=require('node:buffer');
const started=performance.now(),deadline=started+50000;
const checked=()=>{if(performance.now()>deadline)throw Error('Diagnostic deadline');};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
process.on('exit',code=>fs.writeFileSync(path.join(__dirname,'child-exit.json'),JSON.stringify({pid:process.pid,exitCode:code,completedUtc:new Date().toISOString()})+'\n'));
const out=__dirname,repo='C:/Users/james/.codex/worktrees/bortus-app-recovered/kubernetes migration';
const inputs=JSON.parse(fs.readFileSync(path.join(out,'inputs.json')));
const source={};for(const row of inputs.sources){const raw=fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',row.path));if(sha(raw)!==row.sha256)throw Error('Source mismatch');source[path.basename(row.path)]=raw.toString('utf8');}
const before=source['secret-summary-json.ts'];
const method=`  private objectString() {
    this.expect(34);
    for (;;) {
      if (this.peek() < 0) throw invalid();
      const chunk = this.chunks[this.index];
      const quote = chunk.indexOf(34, this.offset), escape = chunk.indexOf(92, this.offset);
      if (quote >= 0 && (escape < 0 || quote < escape)) { this.offset = quote + 1; return; }
      if (escape >= 0) { this.offset = escape + 1; if (this.take() < 0) throw invalid(); }
      else this.offset = chunk.length;
    }
  }
  object(depth: number) {
    if (depth > 32) throw invalid();
    this.expect(123);
    const stack = [{ end: 125, depth, state: 0 }];
    while (stack.length) {
      const frame = stack[stack.length - 1]; this.space(); const byte = this.peek();
      if (byte < 0) throw invalid();
      // Empty containers are legal at depth32; every value token is checked
      // before decoding, including values later overwritten by duplicate keys.
      if (byte === frame.end && frame.state !== 1) { this.take(); stack.pop(); continue; }
      if (frame.state === 0) { this.string(); frame.state = 1; continue; }
      if (frame.state === 1) { this.expect(58); frame.state = 2; continue; }
      if (frame.state === 3) { this.expect(44); frame.state = frame.end === 125 ? 0 : 2; continue; }
      const nextDepth = frame.depth + 1; if (nextDepth > 32) throw invalid(); frame.state = 3;
      if (byte === 123 || byte === 91) { this.take(); stack.push({ end: byte === 123 ? 125 : 93, depth: nextDepth, state: byte === 123 ? 0 : 2 }); }
      else if (byte === 34) this.objectString();
      else {
        let count = 0;
        for (;;) {
          const token = this.peek();
          if (token < 0 || token === 44 || token === 93 || token === 125 || token === 32 || token === 9 || token === 10 || token === 13) break;
          this.take(); count++;
        }
        if (!count) throw invalid();
      }
    }
  }
`;
let after=before.replace('  capture(parse: () => unknown, selectedString = false): unknown {',method+'  capture(parse: () => unknown, selectedString = false): unknown {');
let scopeReplacements=0;
after=after.replace(/const value = reader.capture\(\(\) => reader.skip\(([12])\)\);(\r?\n +if \(!value)/g,(_,depth,tail)=>{scopeReplacements++;return 'const value = reader.capture(() => reader.object('+depth+'));'+tail;});
if(scopeReplacements!==2)throw Error('Metadata scope markers mismatch');
const exactMethod=(text,begin,end)=>text.slice(text.indexOf(begin),text.indexOf(end,text.indexOf(begin)));
const structural=[['string','  string(): boolean {','  private longString(): boolean {'],['capture','  capture(parse:','  text():'],['text','  text():','  members(']].map(([name,a,b])=>{const x=exactMethod(before,a,b),y=exactMethod(after,a,b);if(x!==y)throw Error('Structural change '+name);return {name,beforeSha256:sha(Buffer.from(x)),afterSha256:sha(Buffer.from(y)),equal:true};});
fs.writeFileSync(path.join(out,'candidate-summary.ts'),after,{flag:'wx'});
const cluster=source['cluster-secrets.ts'];
const errorClass=cluster.slice(cluster.indexOf('export class SecretError'),cluster.indexOf('export interface SecretTarget'));
const validation=cluster.slice(cluster.indexOf('const dnsLabel'),cluster.indexOf('// Kubernetes exception bodies'));
const helper=source['secret-ascii-span.ts'].replace(/^import .*\r?\n/gm,'');
const ts=require(path.join(repo,'k8s-rewrite/front-end/node_modules/typescript'));
function compile(text,label){const input=errorClass+'\n'+validation+'\n'+helper+'\n'+text.replace(/^import .*\r?\n/gm,'')+'\nglobalThis.Reader=Reader;globalThis.parse=parseSecretSummaryPage;';const js=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;fs.writeFileSync(path.join(out,label+'-functions.js'),js,{flag:'wx'});const ctx={Buffer,TextDecoder,isAscii,exports:{}};vm.createContext(ctx);vm.runInContext(js,ctx);return ctx;}
const old=compile(before,'baseline'),next=compile(after,'candidate');
const report={scope:'Pure selected-object parser equivalence/CPU diagnostic; no production behavior edit or endpoint acceptance',inputs,node:process.version,pid:process.pid,startedUtc:new Date().toISOString(),structural,originalMetadataCaptureScopesOnly:true,cases:0,malformedCases:0,timings:[],causal:[],limitations:['Pure isolated parser, not TLS/endpoint timing; same public bytes for both variants.','Native values, unknown fields and immutable boolean keep current parser paths.','Object boundary/depth scanner still performs original key grammar and unchanged fatal decode+JSON.parse, with pre-parse depth checks.','Microtiming cannot establish A07/A21 or no-regression acceptance.'],performanceAcceptance:false};
fs.writeFileSync(path.join(out,'started.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
const split=(raw,n)=>Array.from({length:Math.ceil(raw.length/n)},(_,i)=>raw.subarray(i*n,(i+1)*n));
function outcome(ctx,chunks){try{return {ok:true,value:ctx.parse(chunks,'apps',200)}}catch(e){return {ok:false,status:e.status,message:e.message}}}
function equivalent(chunks,expectedValid){checked();const a=outcome(old,chunks),b=outcome(next,chunks);if(JSON.stringify(a)!==JSON.stringify(b))throw Error('Differential mismatch case '+report.cases);if(expectedValid!==undefined&&a.ok!==expectedValid)throw Error('Oracle mismatch case '+report.cases);if(!a.ok){if(a.status!==503||a.message!=='Invalid Kubernetes Secret summary response')throw Error('Error contract');report.malformedCases++;}report.cases++;return a;}
const metadata={namespace:'apps',name:'public',uid:'public-uid',resourceVersion:'public-rv',labels:{public:'label'},annotations:{'bortus.io/kv-state':'{"format":1}','kubectl.kubernetes.io/last-applied-configuration':'PUBLIC_ANNOTATION'}};
const itemMeta=JSON.stringify(metadata);
function page(metadataRaw=itemMeta,rootRaw='{"continue":"public-cursor"}',count=1){return Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":'+rootRaw+',"items":['+Array.from({length:count},(_,i)=>'{"apiVersion":"v1","kind":"Secret","metadata":'+metadataRaw.replace('"name":"public"','"name":"public-'+i+'"')+',"data":{"__proto__":"SKIPPED_VALUE_SENTINEL","":"","binary":"AA=="},"stringData":{"private":"SKIPPED_VALUE_SENTINEL"},"unknown":{"nested":["SKIPPED_VALUE_SENTINEL"]},"type":"Opaque","immutable":true}').join(',')+']}');}
const publicCases=[page(),page(itemMeta.replace('"public":"label"','"public":"snow-雪😀\\n\\\"\\\\\\uD800"')),page(itemMeta.replace('"namespace"','"namesp\\u0061ce"')),page(itemMeta.slice(0,-1)+',"__proto__":{"public":true},"constructor":false,"toString":null,"numbers":[-0,1.25e+2,0.001]}'),page(itemMeta.slice(0,-1)+',"duplicate":{"first":1},"duplicate":{"last":2}}'),page(itemMeta.slice(0,-1)+',"array":[true,false,null,{"nested":[]},[]]}')];
for(const raw of publicCases){for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),Buffer.alloc(0),raw.subarray(at)],true);equivalent(split(raw,1),true);}
function nest(n,leaf='0'){return '['.repeat(n)+leaf+']'.repeat(n);}
for(let n=0;n<=34;n++)for(const leaf of ['0','"public"','{}','[]'])for(const root of [false,true]){
 const meta=root?'{}':itemMeta.slice(0,-1)+',"nested":'+nest(n,leaf)+'}';const rootMeta=root?'{"nested":'+nest(n,leaf)+'}':'{}';const raw=page(meta,rootMeta);for(const chunks of [[raw],split(raw,1),split(raw,4096)])equivalent(chunks);
}
// Deep overwritten duplicate keys must be refused from raw pre-parse depth, not
// merely by walking the post-JSON object after the deep first value disappeared.
for(const root of [false,true])for(const n of [30,31,32,33]){
 const deep='{'+(root?'':itemMeta.slice(1,-1)+',')+'"duplicate":'+nest(n)+',"duplicate":0}';const raw=root?page(itemMeta,deep):page(deep);for(const chunks of [[raw],split(raw,1),split(raw,64)])equivalent(chunks);
}
const malformed=['{"nested":[1,]}','{"nested":{"a":1,}}','{"nested":01}','{"nested":1e}','{"nested":truefalse}','{"nested":"\\x"}','{"nested":"\\u00gg"}','{"nested":"\u0000"}','{"nested":undefined}','{"nested":{"a":1]}}','{"nested":}','{"nested":1 "next":2}','{"nested":"unfinished','{"nested":"\\'];
for(const bad of malformed)for(const root of [false,true]){const raw=root?page(itemMeta,bad):page(itemMeta.slice(0,-1)+',"extra":'+bad+'}');for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],false);}
for(let byte=0;byte<256;byte++){
 const raw=page(itemMeta.replace('PUBLIC_ANNOTATION','A~Z'));const at=raw.indexOf(Buffer.from('A~Z'))+1;raw[at]=byte;
 for(const cut of [at-1,at,at+1,at+2,raw.length])equivalent([raw.subarray(0,cut),Buffer.alloc(0),raw.subarray(cut)],byte>=32&&byte<128&&byte!==34&&byte!==92);
}
for(const bytes of [[0xc0,0x80],[0xe0,0x80,0x80],[0xed,0xa0,0x80],[0xf4,0x90,0x80,0x80],[0x80],[0xf0,0x9f]]){
 const raw=page(itemMeta.replace('PUBLIC_ANNOTATION','BEFORE_AFTER'));const at=raw.indexOf(Buffer.from('BEFORE_AFTER'))+7;const changed=Buffer.concat([raw.subarray(0,at),Buffer.from(bytes),raw.subarray(at)]);for(const cut of [at-1,at,at+1,at+bytes.length,changed.length])equivalent([changed.subarray(0,cut),changed.subarray(cut)],false);
}
for(const raw of [page(itemMeta,'[]'),page('[]'),page(itemMeta,'null'),page('null'),page() .subarray(0,page().length-1),Buffer.concat([page(),Buffer.from('x')])])equivalent([raw],false);
// Observe only counts/content-refusal booleans, never retain decoded strings.
function causal(ctx,label,raw){const proto=ctx.Reader.prototype,skip=proto.skip,string=proto.string,capture=proto.capture,counts={skip:0,string:0,capture:0,decode:0,jsonParse:0};proto.skip=function(...a){counts.skip++;return skip.apply(this,a)};proto.string=function(...a){counts.string++;return string.apply(this,a)};proto.capture=function(...a){counts.capture++;return capture.apply(this,a)};
 class Observed extends TextDecoder{decode(...args){const value=super.decode(...args);counts.decode++;if(value.includes('SKIPPED_VALUE_SENTINEL'))throw Error('Native/unknown value entered capture');return value;}}
 const oldDecoder=ctx.TextDecoder,oldJSON=ctx.JSON;ctx.TextDecoder=Observed;ctx.JSON={parse(...args){counts.jsonParse++;if(args[0].includes('SKIPPED_VALUE_SENTINEL'))throw Error('Native JSON capture');return JSON.parse(...args)}};
 try{const result=ctx.parse([raw],'apps',200);if(JSON.stringify(result).includes('SKIPPED_VALUE_SENTINEL'))throw Error('Value escaped');report.causal.push({label,...counts});}finally{proto.skip=skip;proto.string=string;proto.capture=capture;ctx.TextDecoder=oldDecoder;if(oldJSON===undefined)delete ctx.JSON;else ctx.JSON=oldJSON;}}
causal(old,'baseline200',page(itemMeta,'{"continue":"public-cursor"}',200));causal(next,'candidate200',page(itemMeta,'{"continue":"public-cursor"}',200));
const median=a=>a.slice().sort((a,b)=>a-b)[Math.floor(a.length/2)];const p95=a=>a.slice().sort((a,b)=>a-b)[Math.ceil(a.length*.95)-1];
const run=(ctx,chunks,n)=>{const t=performance.now();for(let i=0;i<n;i++){if(i%32===0)checked();ctx.parse(chunks,'apps',200);}return (performance.now()-t)/n;};
function timing(label,raw,chunkSize){const chunks=split(raw,chunkSize);equivalent(chunks,true);for(let i=0;i<12;i++){old.parse(chunks,'apps',200);next.parse(chunks,'apps',200);}const one=run(old,chunks,1),n=Math.max(1,Math.min(2000,Math.ceil(8/Math.max(one,.001))));const a=[],b=[];for(let i=0;i<15;i++){checked();if(i%2===0){a.push(run(old,chunks,n));b.push(run(next,chunks,n));}else{b.push(run(next,chunks,n));a.push(run(old,chunks,n));}}report.timings.push({label,bytes:raw.length,chunkSize,chunks:chunks.length,iterations:n,observations:15,beforeMs:a,afterMs:b,beforeMedianMs:median(a),afterMedianMs:median(b),ratio:median(b)/median(a),beforeP95Ms:p95(a),afterP95Ms:p95(b),p95Ratio:p95(b)/p95(a)});}
for(const count of [1,56,200])for(const size of [256,16384,65536])timing('full-public-metadata-'+count,page(itemMeta,'{"continue":"public-cursor"}',count),size);
for(const [label,meta] of [['escaped',JSON.stringify({...metadata,annotations:{public:'snow-雪😀\n"\\'.repeat(8)}})],['nested',itemMeta.slice(0,-1)+',"numbers":[1,-0,0.02,1.25e3],"flags":{"a":true,"b":null,"c":false},"nested":[[],{}]}'],['long',JSON.stringify({...metadata,annotations:{public:'PUBLIC_ANNOTATION'.repeat(2048)}})]])for(const size of [256,16384])timing('full-'+label,page(meta,'{}',56),size);
report.completedUtc=new Date().toISOString();report.elapsedMs=performance.now()-started;report.cpu=process.cpuUsage();report.rssBytes=process.memoryUsage().rss;report.equivalencePassed=true;report.exactProductionSourceUnchanged=inputs.sources.every(r=>sha(fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',r.path)))===r.sha256);if(!report.exactProductionSourceUnchanged)throw Error('Source changed');report.diagnosticSha256=sha(fs.readFileSync(__filename));fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({equivalence:true,cases:report.cases,malformed:report.malformedCases,elapsedMs:report.elapsedMs,timings:report.timings.length,sourceUnchanged:report.exactProductionSourceUnchanged,performanceAcceptance:false}));
