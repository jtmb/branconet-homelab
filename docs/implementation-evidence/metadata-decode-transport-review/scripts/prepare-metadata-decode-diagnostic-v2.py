import pathlib,hashlib,json
base=pathlib.Path(__file__).parent;first=base/'metadata-decode-diagnostic-v1';out=base/'metadata-decode-diagnostic-v2';out.mkdir(exist_ok=False)
for name in ['secret-summary-json.ts','secret-ascii-span.ts','cluster-secrets.ts','inputs.json','launch.ps1']:(out/name).write_bytes((first/name).read_bytes())
text=(first/'diagnostic.cjs').read_text()
extra='''for(const raw of [page(itemMeta.replace('PUBLIC_ANNOTATION',String.fromCharCode(0xfeff)+'PUBLIC'))])for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],true);
for(const raw of [page('{'+String.fromCharCode(0xfeff)+'"namespace":"apps","name":"public"}'),page(itemMeta,'{'+String.fromCharCode(0xfeff)+'"continue":""}')])for(let at=0;at<=raw.length;at++)equivalent([raw.subarray(0,at),raw.subarray(at)],false);
'''
assert text.count('const publicCases=[')==1;text=text.replace('const publicCases=[',extra+'const publicCases=[')
(out/'diagnostic.cjs').write_text(text)
(out/'preparation.json').write_text(json.dumps({'unrunOriginalPreparation':str(first),'reason':'Add explicit actual U+FEFF inside and outside strings, retaining escaped BOM oracles as well. No earlier runtime launched.','diagnosticSha256':hashlib.sha256((out/'diagnostic.cjs').read_bytes()).hexdigest()},indent=2)+'\n')
print(json.dumps({'path':str(out),'diagnosticSha256':hashlib.sha256((out/'diagnostic.cjs').read_bytes()).hexdigest()}))
