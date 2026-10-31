import pathlib,hashlib
root=pathlib.Path(r'C:\Users\james\AppData\Local\BORTUS\handoffs\app-freshness-20261010-205744-da6552cf')
out=root/'parser-native-span-7e30-20261011-v3'
code=(root/'parser-native-span-7e30-20261011-v2/diagnostic.cjs').read_text()
def change(old,new):
 global code
 assert code.count(old)==1,old[:80]
 code=code.replace(old,new)
start=code.index('const candidateReader=')
end=code.index('const report=',start)
new=r'''function guardedReader(threshold){let r=reader.replace('string(): boolean {','string(scanLong = false): boolean {').replace('if (byte === 34) { this.string(); return; }','if (byte === 34) { this.string(true); return; }');return r.replace(markerReader,markerReader+'\n      if (scanLong && chunk.length-this.offset >= '+threshold+') { const advanced = advanceAscii(chunk,this.offset); if (advanced) { this.offset += advanced; continue; } }');}
function guardedPrefix(threshold){let p=prefix.replace('const string = (): number => {','const string = (scanLong = false): number => {').replace('if (byte === 34) return string();','if (byte === 34) return string(true);');return p.replace(markerPrefix,markerPrefix+'\n      if (scanLong && chunk.length-offset >= '+threshold+') { const advanced = advanceAscii(chunk,offset); if (advanced) { offset += advanced; continue; } }');}
function compile(r,p,threshold){const input=(threshold?nativeHelper:'')+'const invalid=()=>new Error("Invalid summary");\n'+r+'\n'+p+'\nglobalThis.Reader=Reader;globalThis.prefix=rejectedSecretListItemCount;';const js=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;fs.writeFileSync(path.join(out,threshold?'candidate-'+threshold+'-functions.js':'baseline-functions.js'),js,{flag:'wx'});const ctx={Buffer,TextDecoder,Error,isAscii,exports:{}};vm.createContext(ctx);vm.runInContext(js,ctx);return ctx;}
const before=compile(reader,prefix,0),variants=[1024,4096].map(threshold=>({threshold,ctx:compile(guardedReader(threshold),guardedPrefix(threshold),threshold)}));
'''
code=code[:start]+new+code[end:]
change('nativeWindow:4096,longSpanThreshold:256,','nativeWindow:4096,longSpanThreshold:256,remainingChunkThresholds:[1024,4096],unselectedValueOnly:true,')
change('r.string();return','r.string(true);return')
change("function equivalent(mode,chunks){checked();const a=JSON.stringify(outcome(before,mode,chunks)),b=JSON.stringify(outcome(after,mode,chunks));if(a!==b)throw Error('Differential mismatch '+report.cases);report.cases++;}","function equivalent(mode,chunks){checked();const a=JSON.stringify(outcome(before,mode,chunks));for(const variant of variants){const b=JSON.stringify(outcome(variant.ctx,mode,chunks));if(a!==b)throw Error('Differential mismatch '+report.cases+' threshold '+variant.threshold);report.cases++;}}")
start=code.index('function timing(')
end=code.index("for(const value of ['public-key'",start)
new=r'''const percentile95=a=>a.slice().sort((a,b)=>a-b)[Math.ceil(a.length*.95)-1];
function timing(label,mode,raw,size){checked();const chunks=split(raw,size);equivalent(mode,chunks);for(const variant of variants){const after=variant.ctx;for(let i=0;i<8;i++){outcome(before,mode,chunks);outcome(after,mode,chunks);}const one=measure(before,mode,chunks,1);const n=Math.max(1,Math.min(2000,Math.ceil(8/Math.max(one,0.001))));const a=[],b=[];for(let pair=0;pair<15;pair++){checked();if(pair%2===0){a.push(measure(before,mode,chunks,n));b.push(measure(after,mode,chunks,n));}else{b.push(measure(after,mode,chunks,n));a.push(measure(before,mode,chunks,n));}}report.timings.push({label,threshold:variant.threshold,mode,bytes:raw.length,chunkSize:size,chunks:chunks.length,iterationsPerObservation:n,observations:15,beforeMs:a,afterMs:b,beforeMedianMs:median(a),afterMedianMs:median(b),ratio:median(b)/median(a),beforeP95Ms:percentile95(a),afterP95Ms:percentile95(b),p95Ratio:percentile95(b)/percentile95(a),beforeMinMs:Math.min(...a),beforeMaxMs:Math.max(...a),afterMinMs:Math.min(...b),afterMaxMs:Math.max(...b)});}}
'''
code=code[:start]+new+code[end:]
change("report.functionHashes={before:sha(fs.readFileSync(path.join(out,'baseline-functions.js'))),after:sha(fs.readFileSync(path.join(out,'candidate-functions.js')))};","report.functionHashes={before:sha(fs.readFileSync(path.join(out,'baseline-functions.js'))),variants:variants.map(v=>({threshold:v.threshold,sha256:sha(fs.readFileSync(path.join(out,'candidate-'+v.threshold+'-functions.js')))}))};")
change("for(const value of ['public-key','A'.repeat(512)","for(const size of [1023,1024,1025,4095,4096,4097])testRaw(Buffer.from(JSON.stringify('A'.repeat(size))));\nfor(const value of ['public-key','A'.repeat(512)")
change("for(const [label,value] of [['escaped'","timing('selected-short-key','text',Buffer.from(JSON.stringify('public-key')),16384);\ntiming('selected-long-key','text',Buffer.from(JSON.stringify('A'.repeat(4096))),16384);\nfor(const [label,value] of [['escaped'")
(out/'diagnostic.cjs').write_bytes(code.encode())
(out/'launch.ps1').write_bytes((root/'parser-native-span-7e30-20261011-v2/launch.ps1').read_bytes())
print(hashlib.sha256(code.encode()).hexdigest())