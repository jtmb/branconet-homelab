from pathlib import Path
import hashlib,json,subprocess
b=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
source=repo/'k8s-rewrite/front-end/src/lib/secret-summary-json.ts'
before=source.read_bytes();after=(b/'fixed-field-diagnostic-v1/candidate-summary.ts').read_bytes()
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(before)=='791e5dad01ec4c5ccd5f0948b234a21bea99989105d98a04eea9110ab2153aad'
methods=[]
for name,first,last in [('string',b'  string(): boolean {',b'  private longString(): boolean {'),('skip',b'  skip(depth',b'  capture(parse:'),('capture',b'  capture(parse:',b'  text():'),('text',b'  text():',b'  members(')]:
 x=before[before.index(first):before.index(last,before.index(first))];y=after[after.index(first):after.index(last,after.index(first))];assert x==y
 methods.append({'name':name,'beforeSHA256':sha(x),'afterSHA256':sha(y),'exact':True})
source.write_bytes(after)
note='Known-field duplicate guards in the metadata-summary parser now use scalar bits for the four root schema fields and seven Secret schema fields. This removes per-item/root duplicate-guard Sets and repeated fixed-name membership arrays; it preserves refusal of literal/escaped recognized duplicates, acceptance and complete validation of repeated unknown/prototype-like names, and the exact Reader string/skip/capture/text methods, fatal decoding and JSON parsing. Keys still use their existing Set and preserve exact spelling. Namespace authorization, four-request/same-options operation pool, metadata/value boundaries, byte/item/depth/deadline ceilings and retry charges are unchanged. The prior public differential diagnostic supports reduced allocation and typical median CPU savings, with mixed p95 regressions and a0.149ms56-object/16KiB saving retained explicitly; this does not close the34ms endpoint gap. Fresh functional qualification of this draft remains pending; no paired comparison or image/live acceptance is claimed.'
review=[]
affected={'API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-IMPLEMENTATION.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-CONTROLLED-PERFORMANCE.md','README.md'}
old='The retained isolated diagnostic supports a CPU optimization for large ASCII values, with small-case and p95 variability recorded separately. It does not establish endpoint latency or A07/A21 acceptance. Windows functional qualification passed as recorded below; Linux qualification and the unchanged frozen performance comparison remain pending for this source.'
new='The retained isolated diagnostic supports a CPU optimization for large ASCII values, with small-case and p95 variability recorded separately. Exact4668 source subsequently passed Windows and Linux211-unit/four-HTTP functional qualification, but the unchanged three-pair comparison still failed A07/A21. These results qualify that earlier source only; the later known-field duplicate-guard draft requires its own functional proof. No endpoint, final image or live acceptance is inferred from parser microtiming.'
for path in sorted((repo/'docs').rglob('*.md')):
 raw=path.read_bytes();text=raw.decode('utf-8-sig');update=(path.parent==repo/'docs' and path.name in affected) or path==repo/'docs/implementation-evidence/README.md'
 review.append({'path':path.relative_to(repo).as_posix(),'beforeSHA256':sha(raw),'updated':update})
 if update:
  eol='\r\n' if b'\r\n' in raw else '\n'
  text=text.replace('### Distinct long native value scan (qualification pending)','### Distinct long native value scan').replace(old,new)
  path.write_bytes((text+eol+eol+note+eol).encode())
record={'sourceBeforeSHA256':sha(before),'sourceAfterSHA256':sha(after),'originalMethods':methods,'docs':review,'sourceBase':'08304d8d8b695f827af347ebcc9b294e4d93fed8','performanceAcceptance':False}
(b/'fixed-field-candidate-applied.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
print(json.dumps({'sourceSHA256':sha(after),'docsChecked':len(review),'docsUpdated':sum(x['updated'] for x in review),'methodsExact':True}))
