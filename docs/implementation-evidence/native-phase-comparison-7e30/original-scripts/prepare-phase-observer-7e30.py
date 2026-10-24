from pathlib import Path
import hashlib,io,json,subprocess,zipfile
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');owner='characterize-phase-7e30b9b-v1'
old=repo/'docs/implementation-evidence/native-request-characterization-3f9b21c/characterize-3f9b21c-v3'
files={n:(old/n).read_bytes() for n in ['child-shim.cjs','request-profiler.cjs','supervisor.py']}
s=files['request-profiler.cjs'].decode()
s=s.replace('const now=()=>', '''const jsonStringify=JSON.stringify,jsonParse=JSON.parse;
function timedJSON(original,kind,receiver,args){const w=windows[windows.length-1];if(!w||w.endUs)return Reflect.apply(original,receiver,args);const start=now();try{return Reflect.apply(original,receiver,args);}finally{w.jsonTiming[kind+'Calls']++;w.jsonTiming[kind+'Us']+=now()-start;}}
JSON.stringify=function(...args){return timedJSON(jsonStringify,'stringify',this,args);};JSON.parse=function(...args){return timedJSON(jsonParse,'parse',this,args);};
const responseEnd=http.ServerResponse.prototype.end;http.ServerResponse.prototype.end=function(...args){const w=windows[windows.length-1];if(!w||w.endUs)return Reflect.apply(responseEnd,this,args);const start=now();w.responseEndStartUs=start;try{return Reflect.apply(responseEnd,this,args);}finally{w.responseEndCallUs=(w.responseEndCallUs||0)+now()-start;}};
const now=()=>''')
s=s.replace("kind:'native',startUs:now(),endUs:0", "kind:'native',startUs:now(),endUs:0,jsonTiming:{stringifyCalls:0,stringifyUs:0,parseCalls:0,parseUs:0}")
s=s.replace('durationMs:(w.endUs-w.startUs)/1000}', 'durationMs:(w.endUs-w.startUs)/1000,jsonTiming:w.jsonTiming,responseEndStartUs:w.responseEndStartUs,responseEndCallUs:w.responseEndCallUs}')
s=s.replace('reused:false,endUs:0}', 'reused:false,endUs:0,bodyFirstUs:0,bodyLastUs:0,bodyChunks:0,dataHandlerUs:0,endHandlerUs:0,endHandlersCompleteUs:0}')
s=s.replace("req.once('response',response=>{row.responseMs", """req.once('response',response=>{const originalEmit=response.emit;response.emit=function(event,...args){const start=now();if(event==='data'){if(!row.bodyFirstUs)row.bodyFirstUs=start;row.bodyLastUs=start;row.bodyChunks++;}try{return Reflect.apply(originalEmit,this,[event,...args]);}finally{if(event==='data')row.dataHandlerUs+=now()-start;if(event==='end'){row.endHandlerUs+=now()-start;row.endHandlersCompleteUs=now();}}};row.responseMs""")
files['request-profiler.cjs']=s.encode()
files['child-shim.cjs']+=b'''\nconst https=require('node:https'),fs=require('node:fs');const {AsyncLocalStorage}=require('node:async_hooks');const context=new AsyncLocalStorage(),fixtureRows=[],servers=new WeakMap();let serverSequence=0;const micros=()=>Number(process.hrtime.bigint()/1000n);const stringify=JSON.stringify;
JSON.stringify=function(...args){const row=context.getStore();if(!row)return Reflect.apply(stringify,this,args);const start=micros();try{return Reflect.apply(stringify,this,args);}finally{row.stringifyUs+=micros()-start;row.stringifyCalls++;}};
const emit=https.Server.prototype.emit;https.Server.prototype.emit=function(event,...args){if(event!=='request')return Reflect.apply(emit,this,[event,...args]);if(!servers.has(this))servers.set(this,++serverSequence);const row={server:servers.get(this),startUs:micros(),endUs:0,stringifyUs:0,stringifyCalls:0,responseEndStartUs:0,responseEndCallUs:0};fixtureRows.push(row);const res=args[1],end=res.end;res.end=function(...endArgs){row.responseEndStartUs=micros();try{return Reflect.apply(end,this,endArgs);}finally{row.responseEndCallUs+=micros()-row.responseEndStartUs;}};res.once('finish',()=>{row.endUs=micros();});return context.run(row,()=>Reflect.apply(emit,this,[event,...args]));};
process.once('exit',()=>fs.writeFileSync('/diagnostic-output/fixture-body-metadata.json',stringify({nonAcceptance:true,scope:'Owned synthetic HTTPS fixture requests only; numeric context/timing counters, no bodies/keys/URLs/headers/options retained; timer/body-generation/serialization interval is combined',rows:fixtureRows},null,2)+'\\n',{mode:0o600}));
'''
s=files['supervisor.py'].decode().replace('run-622cdf52624a','run-05381825cdec').replace('preparation-paired-3f9b21c-20261011-065856-3b80','preparation-paired-7e30b9b-20261011-083519-09a9').replace('3f9b21cd5beb568c8faddec75d6ba55ae889c310','7e30b9b428a66cd3f5e618cec5e694d5f03302ac')
s=s.replace("command=['docker'", "build_manifest=json.loads((p/'compiled-build-manifest.json').read_bytes())\nfor row in build_manifest['files']:assert hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256']\nrecord['compiledBuildManifestSHA256']=hashlib.sha256((p/'compiled-build-manifest.json').read_bytes()).hexdigest()\nrecord['compiledBuildFiles']=len(build_manifest['files'])\ncommand=['docker'")
s=s.replace("record['terminalAtUTC']=", "record['compiledBuildUnchanged']=all(hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256'] for row in build_manifest['files'])\nrecord['terminalAtUTC']=")
files['supervisor.py']=s.encode()
prep=base/owner;prep.mkdir(exist_ok=False)
for name,data in files.items():(prep/name).write_bytes(data)
(prep/'preparation.json').write_text(json.dumps({'sourceCommit':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','nonAcceptance':True,'instrumentationOverhead':True,'onlyMetadata':True,'combinedIntervalsExplicit':True,'files':{n:hashlib.sha256(d).hexdigest() for n,d in files.items()}},indent=2)+'\n')
print(json.dumps({'preparation':str(prep),'files':{n:hashlib.sha256(d).hexdigest() for n,d in files.items()}}))
