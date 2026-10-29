import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {packagingLineage,compatibilityRevision,sensitivityRevision,compatibleInputHash,assertRawPackagingInputs,maintainedPackagingAuthority as authority} from '../scripts/current-maintained-packaging-provenance.mjs';
const digest=b=>createHash('sha256').update(b).digest('hex'),gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
assert.ok(gitDir,'Explicit readonly PUBLIC Git authority required');
const git=(args,input)=>{const r=spawnSync('git',['-c','safe.directory='+gitDir,'--git-dir='+gitDir,...args],{input,maxBuffer:128*1024*1024,timeout:20000});assert.equal(r.status,0,'Raw PUBLIC Git unavailable');return r.stdout;};
const prefix='k8s-rewrite/front-end/',inventory=git(['ls-tree','-r','-z',authority.publicSource,'--',prefix]).toString().split('\0').filter(Boolean).map(line=>{const [meta,path]=line.split('\t'),[mode,kind,oid]=meta.split(' ');assert.equal(kind,'blob');return [path.slice(prefix.length),mode,oid];});
assert.equal(inventory.length,993);assert.equal(digest(JSON.stringify(inventory)),"32a857d1a31f468781a26a2cc3bd7ef05d251a4062f11637ab9052345413f677");
const batch=git(['cat-file','--batch'],inventory.map(r=>r[2]).join('\n')+'\n');let offset=0;const publicInputs=new Map();
for(const [name,mode,oid] of inventory){const end=batch.indexOf(10,offset),[id,kind,size]=batch.subarray(offset,end).toString().split(' ');assert.equal(id,oid);assert.equal(kind,'blob');offset=end+1;const bytes=Buffer.from(batch.subarray(offset,offset+Number(size)));offset+=Number(size);assert.equal(batch[offset++],10);assert.equal(createHash('sha1').update(Buffer.from('blob '+size+'\0')).update(bytes).digest('hex'),oid);publicInputs.set(name,{mode,bytes});}assert.equal(offset,batch.length);
const importer=new URL('file:///qualification/tests/caller.mjs');
const reader=url=>{assert.ok(url instanceof URL&&url.href.startsWith('file:///qualification/'),'Outside current source scope');const n=decodeURIComponent(url.pathname.slice('/qualification/'.length));assert.ok(publicInputs.has(n),'Outside exact PUBLIC inventory');return Buffer.from(publicInputs.get(n).bytes);};
const original=readFileSync(new URL('../scripts/packaging-provenance.mjs',import.meta.url)),derived=readFileSync(new URL('../scripts/current-maintained-packaging-provenance.mjs',import.meta.url));
const ts=createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
const parse=b=>{const ast=ts.createSourceFile('helper.mjs',b.toString(),ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);assert.equal(ast.parseDiagnostics.length,0);return ast;};
const tables=b=>{const ast=parse(b),result={};for(const s of ast.statements)if(ts.isVariableStatement(s))for(const d of s.declarationList.declarations){if(['localPins','publicPins','implementationPins','metadataPins','sensitivityPins'].includes(d.name.getText(ast)))result[d.name.getText(ast)]=JSON.parse(d.initializer.arguments[0].getText(ast));}return result;};
const oldTables=tables(original),currentTables=tables(derived);
const frozen=()=>({...oldTables.localPins,...Object.fromEntries(Object.entries(oldTables.implementationPins).map(([k,v])=>[k,v.historical])),...Object.fromEntries(Object.entries(oldTables.metadataPins).map(([k,v])=>[k,v.historical])),...Object.fromEntries(Object.entries(oldTables.sensitivityPins).map(([k,v])=>[k,v.baseline]))});
const tamper=name=>url=>{const b=reader(url);return decodeURIComponent(url.pathname).endsWith('/'+name)?Buffer.concat([b,Buffer.from('\n')]):b;};
test('H01 whole raw inverse retains original helper including final newline',()=>{
 assert.equal(digest(original),authority.originalHelperSHA256);let inverse=derived.toString().split('\n').slice(1).join('\n').split('\nexport const maintainedPackagingAuthority=',1)[0];
 inverse=inverse.replace("const digest = bytes => { assert.ok(Buffer.isBuffer(bytes), 'Raw Buffer reader required'); return createHash('sha256').update(bytes).digest('hex'); };","const digest = bytes => createHash('sha256').update(bytes).digest('hex');").replace(authority.currentDockerfile,authority.oldDockerfile).replace(authority.currentApprovedPackage,authority.oldApprovedPackage);
 assert.deepEqual(Buffer.from(inverse),original);
});
test('H02 all five exported function bodies and unchanged guard tables retain exact AST text',()=>{
 const a=parse(original),b=parse(derived),functions=x=>x.statements.filter(ts.isFunctionDeclaration).map(n=>[n.name.text,n.getText(x)]);assert.deepEqual(functions(b),functions(a));assert.equal(functions(a).length,5);
 for(const name of ['localPins','metadataPins','sensitivityPins'])assert.deepEqual(currentTables[name],oldTables[name]);
 const expected=structuredClone(oldTables);expected.publicPins.Dockerfile=authority.currentDockerfile;expected.implementationPins['package.json'].approved=authority.currentApprovedPackage;assert.deepEqual(currentTables,expected);assert.deepEqual(Object.values(currentTables).map(x=>Object.keys(x).length),[4,4,3,32,3]);
});
test('H03 exact actual PUBLIC source is classified by the maintained raw tuple',()=>{
 assert.equal(packagingLineage(importer,reader),'public');assert.equal(compatibilityRevision(importer,reader),'approved');
 assert.equal(sensitivityRevision(importer,reader),"maintained");
});
test('H04 every packaging and implementation component rejects raw drift',()=>{
 for(const n of Object.keys(currentTables.publicPins))assert.throws(()=>packagingLineage(importer,tamper(n)),/Unknown or mixed packaging/);
 for(const n of Object.keys(currentTables.implementationPins))assert.throws(()=>compatibilityRevision(importer,tamper(n)),/Unknown or mixed implementation/);
});
test('H05 every sensitivity component rejects mixed manifests',()=>{
 for(const n of Object.keys(currentTables.sensitivityPins))assert.throws(()=>sensitivityRevision(importer,tamper(n)),/Unknown or mixed sensitivity/);
});
test('H06 complete original historical map authority remains meaningful in current raw context',()=>{
 assertRawPackagingInputs(importer,frozen(),reader);
 for(const [n,v] of Object.entries(oldTables.implementationPins))assert.equal(compatibleInputHash(importer,n,v.historical,reader),digest(reader(new URL('../'+n,importer))));
 for(const [n,v] of Object.entries(oldTables.metadataPins))assert.equal(compatibleInputHash(importer,n,v.historical,reader),digest(reader(new URL('../'+n,importer))));
});
test('H07 tampered historical package implementation metadata and sensitivity pins refuse',()=>{
 for(const n of Object.keys(frozen()))assert.throws(()=>assertRawPackagingInputs(importer,{...frozen(),[n]:'0'.repeat(64)},reader),/Historical/);
});
test('H08 observed metadata drift refuses with historical authority intact',()=>{
 for(const n of Object.keys(oldTables.metadataPins))assert.throws(()=>assertRawPackagingInputs(importer,frozen(),tamper(n)));
});
test('H09 string and typed-array readers cannot masquerade as raw Buffer inputs',()=>{
 for(const convert of [b=>b.toString(),b=>new Uint8Array(b)]){
  const nonraw=url=>convert(reader(url));assert.throws(()=>packagingLineage(importer,nonraw),/Raw Buffer reader required/);assert.throws(()=>compatibilityRevision(importer,nonraw),/Raw Buffer reader required/);assert.throws(()=>assertRawPackagingInputs(importer,frozen(),nonraw),/Raw Buffer reader required/);
 }
});
test('H10 original source remains unchanged and flat authority is immutable',()=>{
 assert.equal(Object.isFrozen(authority),true);assert.ok(Object.values(authority).every(v=>typeof v==='string'));assert.throws(()=>{authority.currentDockerfile='0'.repeat(64);},TypeError);assert.equal(digest(readFileSync(new URL('../scripts/packaging-provenance.mjs',import.meta.url))),authority.originalHelperSHA256);
});
