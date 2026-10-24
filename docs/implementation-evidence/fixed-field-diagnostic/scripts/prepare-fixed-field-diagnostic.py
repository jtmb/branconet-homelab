from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).parent
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=b/'fixed-field-diagnostic-v1';out.mkdir(exist_ok=False)
manifest=[]
for rel in ['src/lib/secret-summary-json.ts','src/lib/secret-ascii-span.ts','src/lib/cluster-secrets.ts']:
 raw=(repo/'k8s-rewrite/front-end'/rel).read_bytes();(out/Path(rel).name).write_bytes(raw)
 manifest.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
assert subprocess.check_output(['git','diff','--exit-code','4668ceb40c3120c7e4053d94edff31f57b7e1f7f','HEAD','--','k8s-rewrite/front-end'],cwd=repo)==b''
(out/'inputs.json').write_text(json.dumps({'commit':'cd25c6bf46577acf4b3e08e725f2e8a35aa19609','productionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f','sources':manifest},indent=2)+'\n')
text=(b/'metadata-decode-diagnostic-v2/diagnostic.cjs').read_text()
start=text.index('const method=`');end=text.index('const exactMethod=',start)
replacement=r'''let after=before;
const sourceChanges=[];
function once(from,to){if(after.split(from).length!==2)throw Error('Fixed-field source marker');after=after.replace(from,to);sourceChanges.push({fromSha256:sha(Buffer.from(from)),toSha256:sha(Buffer.from(to))});}
once('const reader = new Reader(chunks), items: NativeSecretSummary[] = [], seen = new Set<string>();','const reader = new Reader(chunks), items: NativeSecretSummary[] = []; let seen = 0;');
once('const fields = new Set<string>(); let apiVersion:','let fields = 0; let apiVersion:');
once('if (["apiVersion", "kind", "metadata", "data", "stringData", "type", "immutable"].includes(key)) {','const bit = key === "apiVersion" ? 1 : key === "kind" ? 2 : key === "metadata" ? 4 : key === "data" ? 8 : key === "stringData" ? 16 : key === "type" ? 32 : key === "immutable" ? 64 : 0;\n        if (bit) {');
once('if (fields.has(key)) throw invalid(); fields.add(key);','if (fields & bit) throw invalid(); fields |= bit;');
once('if (["apiVersion", "kind", "metadata", "items"].includes(key)) { if (seen.has(key)) throw invalid(); seen.add(key); }','const bit = key === "apiVersion" ? 1 : key === "kind" ? 2 : key === "metadata" ? 4 : key === "items" ? 8 : 0;\n      if (bit) { if (seen & bit) throw invalid(); seen |= bit; }');
'''
text=text[:start]+replacement+text[end:]
text=text.replace("['skip','  skip(depth','  metadata(parse:']", "['skip','  skip(depth','  capture(parse:']")
text=text.replace("const x=exactMethod(before,a,name==='skip'?'  capture(parse:':b),y=exactMethod(after,a,b);", "const x=exactMethod(before,a,b),y=exactMethod(after,a,b);")
text=text.replace('Selected metadata redundant UTF8 decode equivalence/CPU diagnostic; no production behavior edit or endpoint acceptance','Known-field Set/includes allocation differential diagnostic; no production behavior edit or endpoint acceptance')
text=text.replace('structural,originalMetadataCaptureScopesOnly:true,', 'structural,sourceChanges,originalMetadataCaptureScopesOnly:true,')
text=text.replace('Metadata alone uses Buffer UTF8 conversion after unchanged complete skip/string grammar; original capture/fatal decoder remains for all keys/header/strings/boolean paths, and JSON.parse stays unchanged.', 'Only fixed-known-field duplicate detection changes to scalar bits; complete Reader grammar/capture/fatal decoding/JSON.parse, unknown fields and selected metadata remain unchanged.')
# Capture a concrete allocation counter only in the separate causal observation.
# Timing contexts retain normal native Set; no global monkeypatch affects them.
text=text.replace('metadata:0,decode:0,jsonParse:0}', 'metadata:0,decode:0,jsonParse:0,setConstructors:0}')
needle='const oldDecoder=ctx.TextDecoder,oldJSON=ctx.JSON;'
assert text.count(needle)==1
text=text.replace(needle,'const oldSet=ctx.Set;ctx.Set=class extends Set {constructor(...args){super(...args);counts.setConstructors++;}};'+needle)
text=text.replace('ctx.TextDecoder=oldDecoder;if(oldJSON===undefined)', 'ctx.TextDecoder=oldDecoder;if(oldSet===undefined)delete ctx.Set;else ctx.Set=oldSet;if(oldJSON===undefined)')
marker='// Observe only counts/content-refusal booleans, never retain decoded strings.'
extra=r'''// Every recognized duplicate must be refused, including escaped key spelling.
const rootValues={apiVersion:'"v1"',kind:'"SecretList"',metadata:'{}',items:'[]'};
for(const [key,value] of Object.entries(rootValues))for(const spelling of [key,key.slice(0,1)+'\\u'+key.charCodeAt(1).toString(16).padStart(4,'0')+key.slice(2)]){
 const raw=Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{},"items":[],"'+spelling+'":'+value+'}');
 for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],false);
}
const itemValues={apiVersion:'"v1"',kind:'"Secret"',metadata:itemMeta,data:'{}',stringData:'{}',type:'"Opaque"',immutable:'false'};
for(const [key,value] of Object.entries(itemValues))for(const spelling of [key,key.slice(0,1)+'\\u'+key.charCodeAt(1).toString(16).padStart(4,'0')+key.slice(2)]){
 const raw=page();const at=raw.indexOf(Buffer.from('"type":"Opaque","immutable":true}'))+'"type":"Opaque","immutable":true'.length;
 const changed=Buffer.concat([raw.subarray(0,at),Buffer.from(',"'+spelling+'":'+value),raw.subarray(at)]);
 for(const cut of [0,at,at+1,at+2,changed.length])equivalent([changed.subarray(0,cut),changed.subarray(cut)],false);
}
// Unknown prototype-like names and their duplicates remain accepted and skipped.
for(const key of ['__proto__','constructor','toString','has','add','fields','seen']){
 const raw=Buffer.concat([page().subarray(0,page().length-1),Buffer.from(',"'+key+'":0,"'+key+'":{"public":true}}')]);
 for(const chunks of [[raw],split(raw,1),split(raw,64)])equivalent(chunks,true);
}
'''
assert text.count(marker)==1;text=text.replace(marker,extra+marker)
(out/'diagnostic.cjs').write_text(text)
(out/'launch.ps1').write_bytes((b/'metadata-decode-diagnostic-v2/launch.ps1').read_bytes())
(out/'preparation.json').write_text(json.dumps({'diagnosticSha256':hashlib.sha256((out/'diagnostic.cjs').read_bytes()).hexdigest(),'oneCPU':True,'maxSeconds':60,'sourceUnchanged':True,'hypothesis':'Per-item/root fixed-field Sets and transient known-name includes arrays can be replaced by scalar duplicate bits without altering grammar or capture; benefit is unmeasured until this diagnostic.'},indent=2)+'\n')
print(json.dumps({'path':str(out),'diagnosticSHA256':hashlib.sha256((out/'diagnostic.cjs').read_bytes()).hexdigest()}))
