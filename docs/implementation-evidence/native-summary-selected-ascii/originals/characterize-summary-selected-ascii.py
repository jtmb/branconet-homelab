from pathlib import Path
import subprocess
base=Path(__file__).parent
s=(base/'characterize-summary-decoder.py').read_text()
s=s.replace("out=base/'summary-decoder-characterization-v2'","out=base/'summary-selected-ascii-characterization-v1'")
s=s.replace('dafb41c3c226ef03913df2ab6c113a9820a709c6','8f1a1b8e8745bf90d0c9bbcb8b778117ea25302f')
s=s.replace("Array.from(b,(_,i)=>b.subarray(i,i+1)).slice(0,0).concat([b.subarray(0,17),b.subarray(17)])","[b.subarray(0,17),b.subarray(17)]")
start=s.index('const Original=TextDecoder;');end=s.index('const rows=[];',start)
s=s[:start]+'''const decode=TextDecoder.prototype.decode;let decodes=0;TextDecoder.prototype.decode=function(...args){decodes++;return Reflect.apply(decode,this,args);};const counts:any={};try{for(const [name,parser] of [['before',before],['after',after]] as const){decodes=0;parser([workloads[0].chunks[0]],'apps',200);counts[name]=decodes;}}finally{TextDecoder.prototype.decode=decode;}assert.ok(counts.after<counts.before);
// Same public metadata oracles at every split, including escaped member/key names,
// multibyte/escaped/control characters and prototype-like/empty key identities.
let splitOracles=0;const publicVariants=[valid,Buffer.from(valid.toString().replace('"kind"','"k\\\\u0069nd"').replace('"public"','"p\\\\u0075blic"')),Buffer.from(valid.toString().replace('"public"','"snow-雪😀\\\\n\\\\\\\\\\\\\\""'))];
for(const b of publicVariants){const expected=before([b],'apps',200);for(let i=0;i<=b.length;i++){const chunks=[b.subarray(0,i),Buffer.alloc(0),b.subarray(i)];assert.deepEqual(after(chunks,'apps',200),expected);assert.deepEqual(before(chunks,'apps',200),expected);splitOracles++;}}
''' +s[end:]
s=s.replace('decoderConstructionsPer200ObjectDocument:counts','selectedDecodesPer200ObjectDocument:counts,splitOracles')
s=s.replace('decoderConstructionsPerDocument:counts','selectedDecodesPerDocument:counts,splitOracles')
# Keep the script itself retained; execute the exact generated characterization.
target=base/'run-summary-selected-ascii-characterization.py';target.write_text(s,encoding='utf-8')
r=subprocess.run([__import__('sys').executable,'-B',str(target)]);raise SystemExit(r.returncode)
