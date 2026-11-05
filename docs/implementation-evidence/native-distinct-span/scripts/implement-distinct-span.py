from pathlib import Path
import hashlib,json,datetime
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
out=Path(__file__).parent/'native-distinct-span-preparation'
out.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
docs=[]
for p in sorted((repo/'docs').rglob('*.md')):
 b=p.read_bytes(); text=b.decode('utf-8-sig');docs.append({'path':p.relative_to(repo).as_posix(),'sha256':sha(b),'bytes':len(b)})
paths=['src/lib/secret-summary-json.ts','src/lib/secret-client.ts']
front=repo/'k8s-rewrite/front-end'
sources={}
for p in paths:
 b=(front/p).read_bytes();sources[p]=b.decode();(out/Path(p).name).write_bytes(b)
r=sources[paths[0]];p=sources[paths[1]]
original=r[r.index('  string(): boolean {'):r.index('  private literal(')]
prefix=p[p.index('  const string = (): number => {'):p.index('  const literal = ')]
assert sha(original.encode())=='067e12160604549fc94fde2c3579a9a26c3f2697d4ab3d05907e5a9bc2adb4a6'
assert sha(prefix.encode())=='3dbd92deab8549e873b2c82a3995a29c49d60ad3e4a2d33c8fb0f531de353c74'
helper='''import { isAscii } from "node:buffer";

// A bounded view of unselected native value bytes; never decode or copy them.
// A quote, escape, raw control or high byte leaves the scalar grammar in charge.
export function nativeAsciiValueSpan(chunk: Buffer, start: number): number {
  if (chunk.length - start < 4096) return 0;
  const window = chunk.subarray(start, start + 4096);
  let end = window.indexOf(34);
  if (end < 0) end = window.length;
  if (end < 256) return 0;
  const escape = window.subarray(0, end).indexOf(92);
  if (escape >= 0) end = escape;
  if (end < 256) return 0;
  const span = window.subarray(0, end);
  if (!isAscii(span)) return 0;
  for (let control = 0; control < 32; control++) if (span.indexOf(control) >= 0) return 0;
  return end;
}
'''
(front/'src/lib/secret-ascii-span.ts').write_bytes(helper.replace('\n','\r\n').encode())
long=original.replace('  string(): boolean {','  private longString(): boolean {').replace('      const chunk = this.chunks[this.index];','      const chunk = this.chunks[this.index];\r\n      const advanced = nativeAsciiValueSpan(chunk, this.offset);\r\n      if (advanced) { this.offset += advanced; continue; }')
dispatch='''  valueString(): boolean {
    this.peek(); const chunk = this.chunks[this.index];
    return chunk && chunk.length - this.offset >= 4096 ? this.longString() : this.string();
  }
'''.replace('\n','\r\n')
r=r.replace(original,original+long+dispatch)
r='import { nativeAsciiValueSpan } from "./secret-ascii-span";\r\n'+r
r=r.replace('skip(depth = 0)', 'skip(depth = 0, nativeValues = false)').replace('if (byte === 34) { this.string(); return; }','if (byte === 34) { if (nativeValues) this.valueString(); else this.string(); return; }').replace('this.skip(depth + 1);','this.skip(depth + 1, nativeValues);').replace('reader.members(name => { reader.string();','reader.members(name => { reader.valueString();').replace('} else reader.skip(2);','} else reader.skip(2, true);').replace('} else reader.skip(1);','} else reader.skip(1, true);')
assert r[r.index('  string(): boolean {'):r.index('  private longString(): boolean {')]==original
long=prefix.replace('  const string = (): number => {','  const longString = (): number => {').replace('      const chunk = chunks[chunkIndex];','      const chunk = chunks[chunkIndex];\r\n      const advanced = nativeAsciiValueSpan(chunk, offset);\r\n      if (advanced) { offset += advanced; continue; }')
p=p.replace(prefix,prefix+long).replace('    if (byte === 34) return string();','    if (byte === 34) return chunks[chunkIndex].length - offset >= 4096 ? longString() : string();')
p='import { nativeAsciiValueSpan } from "./secret-ascii-span";\r\n'+p
assert p[p.index('  const string = (): number => {'):p.index('  const longString = (): number => {')]==prefix
(front/paths[0]).write_bytes(r.encode());(front/paths[1]).write_bytes(p.encode())
note='''

### Distinct long native value scan (qualification pending)

The native summary and rejected-prefix grammars use a distinct long-value method only when the current chunk has at least 4 KiB remaining. It checks bounded 4 KiB Buffer views using numeric quote/backslash searches, native ASCII validation and all raw control bytes 0–31 before advancing. Short spans, escapes, multibyte UTF-8 and chunk boundaries retain the existing scalar grammar. Selected keys, headers and text keep the original string method; captured metadata retains its complete fatal decoding and JSON parsing. No native value string is decoded, copied or cached by this path. Complete schema/UTF-8 validation, prefix-only sizing hints, received-byte charging, four active requests, 64 queued requests and all existing size/item/deadline/permission bounds remain unchanged.

The retained isolated diagnostic supports a CPU optimization for large ASCII values, with small-case and p95 variability recorded separately. It does not establish endpoint latency or A07/A21 acceptance. Fresh functional qualification and the unchanged frozen performance comparison are pending for this source.
'''
affected=['API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-CONTROLLED-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md','implementation-evidence/README.md']
for name in affected:
 path=repo/'docs'/name;b=path.read_bytes();eol='\r\n' if b'\r\n' in b else '\n';path.write_bytes(b+note.replace('\n',eol).encode())
record={'base':'7524a9633eecea6a11d73b763451030e07ea7af4','originalReaderStringSha256':sha(original.encode()),'originalPrefixStringSha256':sha(prefix.encode()),'preservedExactly':True,'docsReviewed':docs,'docsAffected':affected,'sources':[{'path':x,'beforeSha256':sha(sources[x].encode()),'afterSha256':sha((front/x).read_bytes())} for x in paths],'qualification':'pending','performanceAcceptance':False}
(out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'preservedExactly':True,'docsReviewed':len(docs),'docsUpdated':len(affected)}))
