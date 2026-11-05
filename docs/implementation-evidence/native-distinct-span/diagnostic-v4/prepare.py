import pathlib,hashlib
root=pathlib.Path(r'C:\Users\james\AppData\Local\BORTUS\handoffs\app-freshness-20261010-205744-da6552cf');out=root/'parser-native-span-7e30-20261011-v4'
code=(root/'parser-native-span-7e30-20261011-v3/diagnostic.cjs').read_text()
def change(old,new):
 global code
 assert code.count(old)==1,old[:100]
 code=code.replace(old,new)
a=code.index('function guardedReader(');b=code.index('function compile(',a)
new=r'''const originalReaderString=reader.slice(reader.indexOf('  string(): boolean {'),reader.indexOf('  private literal('));
const originalPrefixString=prefix.slice(prefix.indexOf('  const string = (): number => {'),prefix.indexOf('  const literal = '));
const structural=[];
function guardedReader(threshold){const long=originalReaderString.replace('  string(): boolean {','  private longString(): boolean {').replace(markerReader,markerReader+'\n      if (chunk.length-this.offset >= '+threshold+') { const advanced = advanceAscii(chunk,this.offset); if (advanced) { this.offset += advanced; continue; } }');const dispatch='  valueString(): boolean { this.peek(); const chunk=this.chunks[this.index]; return chunk && chunk.length-this.offset >= '+threshold+' ? this.longString() : this.string(); }\n';let r=reader.replace(originalReaderString,originalReaderString+long+dispatch).replace('if (byte === 34) { this.string(); return; }','if (byte === 34) { this.valueString(); return; }');const preserved=r.slice(r.indexOf('  string(): boolean {'),r.indexOf('  private longString(): boolean {'));if(preserved!==originalReaderString)throw Error('Reader structural equality');structural.push({threshold,method:'Reader.string',sourceSha256:sha(Buffer.from(originalReaderString)),candidateSourceSha256:sha(Buffer.from(preserved)),equal:true});return r;}
function guardedPrefix(threshold){const long=originalPrefixString.replace('  const string = (): number => {','  const longString = (): number => {').replace(markerPrefix,markerPrefix+'\n      if (chunk.length-offset >= '+threshold+') { const advanced = advanceAscii(chunk,offset); if (advanced) { offset += advanced; continue; } }');let p=prefix.replace(originalPrefixString,originalPrefixString+long).replace('if (byte === 34) return string();','if (byte === 34) return chunks[chunkIndex].length-offset >= '+threshold+' ? longString() : string();');const preserved=p.slice(p.indexOf('  const string = (): number => {'),p.indexOf('  const longString = (): number => {'));if(preserved!==originalPrefixString)throw Error('Prefix structural equality');structural.push({threshold,method:'prefix.string',sourceSha256:sha(Buffer.from(originalPrefixString)),candidateSourceSha256:sha(Buffer.from(preserved)),equal:true});return p;}
'''
code=code[:a]+new+code[b:]
change('variants=[1024,4096]','variants=[4096,16384]')
change('remainingChunkThresholds:[1024,4096],unselectedValueOnly:true,','remainingChunkThresholds:[4096,16384],unselectedValueOnly:true,originalStringMethodsUnchanged:structural,structuralEqualityOnlyNotJitEquivalence:true,')
change('r.string(true);return','(ctx===before?r.string():r.valueString());return')
change('[1023,1024,1025,4095,4096,4097]','[1023,1024,1025,4095,4096,4097,16383,16384,16385]')
(out/'diagnostic.cjs').write_bytes(code.encode());(out/'launch.ps1').write_bytes((root/'parser-native-span-7e30-20261011-v2/launch.ps1').read_bytes())
print(hashlib.sha256(code.encode()).hexdigest())