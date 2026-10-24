from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).parent;r=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');out=b/'lexical-metadata-diagnostic-v1';out.mkdir(exist_ok=False);commit='c29fc8c44847172e040e83df11c51ad42f1da51e';sha=lambda d:hashlib.sha256(d).hexdigest();rows=[]
for rel in ['src/lib/secret-summary-json.ts','src/lib/secret-ascii-span.ts','src/lib/cluster-secrets.ts']:
 path='k8s-rewrite/front-end/'+rel;entry=subprocess.check_output(['git','ls-tree',commit,'--',path],cwd=r).decode().strip();meta,name=entry.split('\t');mode,kind,blob=meta.split();raw=subprocess.check_output(['git','cat-file','blob',blob],cwd=r);assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob;(out/Path(rel).name).write_bytes(raw);working=(r/path).read_bytes();rows.append({'path':rel,'sha256':sha(raw),'bytes':len(raw),'mode':mode,'blob':blob,'workingSHA256':sha(working),'workingBytes':len(working)})
old=b/'selected-object-diagnostic-v2/diagnostic.cjs';original=old.read_bytes();text=original.decode('utf-8');start=text.index('const method=`');end=text.index('`;',start)+2
method='''const method=`  object(depth: number) {
    if (depth > 32) throw invalid();
    this.expect(123);
    let nesting = 1, quoted = false, escaped = false;
    while (this.peek() >= 0) {
      const chunk = this.chunks[this.index];
      for (let offset = this.offset; offset < chunk.length; offset++) {
        const byte = chunk[offset];
        if (quoted) {
          if (escaped) { escaped = false; continue; }
          if (byte === 92) escaped = true;
          else if (byte === 34) quoted = false;
          continue;
        }
        if (byte === 125 || byte === 93) {
          nesting--;
          if (!nesting) { this.offset = offset + 1; return; }
          continue;
        }
        if (byte === 32 || byte === 9 || byte === 10 || byte === 13) continue;
        // A nonempty depth32 container has a depth33 value. Check raw tokens
        // before JSON.parse can discard an overwritten duplicate-key subtree.
        if (depth + nesting > 32) throw invalid();
        if (byte === 34) quoted = true;
        else if (byte === 123 || byte === 91) nesting++;
      }
      this.offset = chunk.length;
    }
    throw invalid();
  }
`;'''
text=text[:start]+method+text[end:]
oldread="const raw=fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',row.path));if(sha(raw)!==row.sha256)throw Error('Source mismatch');source[path.basename(row.path)]=raw.toString('utf8');"
newread="const raw=fs.readFileSync(path.join(out,path.basename(row.path)));if(sha(raw)!==row.sha256)throw Error('Frozen raw Git source mismatch');if(sha(fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',row.path)))!==row.workingSHA256)throw Error('Working source mismatch');source[path.basename(row.path)]=raw.toString('utf8');"
assert text.count(oldread)==1;text=text.replace(oldread,newread)
text=text.replace("['string','  string(): boolean {','  private longString(): boolean {'],['capture'","['string','  string(): boolean {','  private longString(): boolean {'],['longString','  private longString(): boolean {','  valueString(): boolean {'],['valueString','  valueString(): boolean {','  private literal('],['skip','  skip(depth =','  capture(parse:'],['capture'")
# The added boundary method sits immediately before capture; exclude only that
# method when comparing the complete original skip method region.
text=text.replace("const x=exactMethod(before,a,b),y=exactMethod(after,a,b);","const x=exactMethod(before,a,b),y=exactMethod(after,a,b).replace(method,'');")
text=text.replace("Object boundary/depth scanner still performs original key grammar and unchanged fatal decode+JSON.parse, with pre-parse depth checks.","Selected metadata only uses lexical quote/escape/container boundary and raw depth checks, then unchanged fatal decode+JSON.parse validates all grammar/UTF8; original selected key/header/native value methods remain exact.")
text=text.replace("sha(fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',r.path)))===r.sha256","sha(fs.readFileSync(path.join(repo,'k8s-rewrite/front-end',r.path)))===r.workingSHA256")
marker='// Observe only counts/content-refusal booleans, never retain decoded strings.'
extra=r'''// Lexical-specific quote/backslash parity, BOM, Unicode and malformed boundary
// cases use unchanged public-only baseline oracles and every raw split.
for (const tail of [JSON.stringify({literal:'{}[]\\\"',unicode:'雪😀\uFEFF',empty:{},array:[]}),'{"x":"\\\\\\\"}[]","x":{"last":1}}','{"x":"\\u007b\\u005b\\u0022"}','{"x":"\\uD800","x":"\\uDC00"}']) {
 const raw=page(itemMeta.slice(0,-1)+',"extra":'+tail+'}');for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),Buffer.alloc(0),raw.subarray(at)]);equivalent(split(raw,1));
}
for (const bad of ['{[1]}','{"x":{]}','{"x":]}','{"x":"}','{"x":NaN}','{"x":Infinity}','{"x":+1}','{"x":.1}','{"x":1.}','{"x":0x10}','{"x":true,"x":[[[}']) {
 const raw=page(itemMeta.slice(0,-1)+',"extra":'+bad+'}');for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],false);
}
const bom=Buffer.from([0xef,0xbb,0xbf]);for(const raw of [Buffer.concat([bom,page()]),page(itemMeta.slice(0,-1)+',"extra":'+bom.toString('utf8')+'0}')])equivalent([raw],false);
'''
assert text.count(marker)==1;text=text.replace(marker,extra+'\n'+marker)
(out/'diagnostic.cjs').write_bytes(text.encode('utf-8'));(out/'launch.ps1').write_bytes((b/'selected-object-diagnostic-v2/launch.ps1').read_bytes());inputs={'commit':commit,'scope':'Only public exact c29fc raw Git selected metadata traversal differential; no production behavior edit','sources':rows,'templateSHA256':sha(original),'newDiagnosticSHA256':sha(text.encode()),'compilerSHA256':sha((r/'k8s-rewrite/front-end/node_modules/typescript/lib/typescript.js').read_bytes()),'nodeSHA256':sha(Path(r'C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe').read_bytes()),'controls':'Same public corpus plus lexical edge cases;15 alternating untrimmed arrays/row,one CPU,50s child deadline/60s owned launcher'}
(out/'inputs.json').write_bytes((json.dumps(inputs,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'diagnosticSHA256':sha(text.encode()),'rawSources':len(rows),'reference':commit}))
