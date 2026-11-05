import pathlib,hashlib,json
base=pathlib.Path(__file__).parent;repo=pathlib.Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=base/'metadata-decode-diagnostic-v1';out.mkdir(exist_ok=False)
manifest=[]
for path in ['src/lib/secret-summary-json.ts','src/lib/secret-ascii-span.ts','src/lib/cluster-secrets.ts']:
    data=(repo/'k8s-rewrite/front-end'/path).read_bytes();(out/pathlib.Path(path).name).write_bytes(data);manifest.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
(out/'inputs.json').write_text(json.dumps({'commit':'962d127678c244578e4ad5c4907749745f408e66','productionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f','sources':manifest},indent=2)+'\n')
text=(base/'selected-object-diagnostic-v2/diagnostic.cjs').read_text()
start=text.index('const method=`');end=text.index('const exactMethod=',start)
replacement=r'''const method=`  metadata(parse: () => unknown): unknown {
    this.space(); this.peek(); const startIndex = this.index, startOffset = this.offset;
    parse(); // Existing full skip/string grammar has already validated every selected byte and depth.
    const pieces: Buffer[] = [];
    for (let i = startIndex; i <= this.index && i < this.chunks.length; i++) {
      const end = i === this.index ? this.offset : this.chunks[i].length;
      pieces.push(this.chunks[i].subarray(i === startIndex ? startOffset : 0, end));
    }
    const selected = pieces.length === 1 ? pieces[0] : Buffer.concat(pieces);
    return JSON.parse(selected.toString("utf8"));
  }
`;
let after=before.replace('  capture(parse: () => unknown, selectedString = false): unknown {',method+'  capture(parse: () => unknown, selectedString = false): unknown {');
let scopeReplacements=0;
after=after.replace(/const value = reader.capture\(\(\) => reader.skip\(([12])\)\);(\r?\n +if \(!value)/g,(_,depth,tail)=>{scopeReplacements++;return 'const value = reader.metadata(() => reader.skip('+depth+'));'+tail;});
if(scopeReplacements!==2)throw Error('Metadata scope markers mismatch');
'''
text=text[:start]+replacement+text[end:]
text=text.replace("['capture','  capture(parse:','  text():']", "['skip','  skip(depth','  metadata(parse:'],['capture','  capture(parse:','  text():']")
# The inserted metadata method changes only the end marker after skip. Compare
# the unchanged original skip body against its existing capture marker instead.
text=text.replace("const x=exactMethod(before,a,b),y=exactMethod(after,a,b);", "const x=exactMethod(before,a,name==='skip'?'  capture(parse:':b),y=exactMethod(after,a,b);")
text=text.replace('Pure selected-object parser equivalence/CPU diagnostic; no production behavior edit or endpoint acceptance','Selected metadata redundant UTF8 decode equivalence/CPU diagnostic; no production behavior edit or endpoint acceptance')
text=text.replace('Object boundary/depth scanner still performs original key grammar and unchanged fatal decode+JSON.parse, with pre-parse depth checks.','Metadata alone uses Buffer UTF8 conversion after unchanged complete skip/string grammar; original capture/fatal decoder remains for all keys/header/strings/boolean paths, and JSON.parse stays unchanged.')
needle="const publicCases=["
bom=r'''for(const raw of [page(itemMeta.replace('PUBLIC_ANNOTATION','\ufeffPUBLIC')),page(itemMeta.replace('PUBLIC_ANNOTATION','\\uFEFFPUBLIC'))]){for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],true);}
for(const raw of [Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),page()]),page('{\ufeff"namespace":"apps","name":"public"}'),page(itemMeta,'{\ufeff"continue":""}')]){for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],false);}
'''
assert text.count(needle)==1;text=text.replace(needle,bom+needle)
text=text.replace('counts={skip:0,string:0,capture:0,decode:0,jsonParse:0}', 'counts={skip:0,string:0,capture:0,metadata:0,decode:0,jsonParse:0}')
text=text.replace("class Observed extends TextDecoder", "const meta=proto.metadata;if(meta)proto.metadata=function(...a){counts.metadata++;return meta.apply(this,a)};\n class Observed extends TextDecoder")
text=text.replace('proto.capture=capture;ctx.TextDecoder=oldDecoder;', 'proto.capture=capture;if(meta)proto.metadata=meta;ctx.TextDecoder=oldDecoder;')
(out/'diagnostic.cjs').write_text(text)
(out/'launch.ps1').write_bytes((base/'selected-object-diagnostic-v2/launch.ps1').read_bytes())
print(json.dumps({'path':str(out),'diagnosticSha256':hashlib.sha256((out/'diagnostic.cjs').read_bytes()).hexdigest(),'sources':manifest}))
