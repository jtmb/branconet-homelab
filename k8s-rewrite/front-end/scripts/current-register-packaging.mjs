import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const digest=b=>createHash('sha256').update(b).digest('hex');
export const registerMetadataDispatch=Object.freeze({
 "original": "tests/auth-register-current-unit-plan.test.mjs",
 "current": "tests/auth-login-current-packaging.test.mjs",
 "metadata": "tests/current-login-packaging.test.mjs",
 "sourceSHA256": "6df4158119fdd879d3646cb4a818578c72f01d483cf26e62a22ce46f63847543",
 "spans": [
 {
  "label": "M03",
  "start": 2670,
  "end": 2999,
  "sha256": "4932cb352514e2aa46e9bba70e4162cdab43a99b4b19250e59b7a51750ef6d88"
 },
  {
   "label": "M14",
   "start": 8736,
   "end": 9193,
   "sha256": "811c4b083f1b48683543e27fd10e887c24e453b7aa254077ea101fd4280b39da"
  },
  {
   "label": "M15",
   "start": 9193,
   "end": 10385,
   "sha256": "8d85993acda68caa5369881c36b65ff73ce41f5d5370a1a365a69b2ffb10e7ef"
  }
 ]
});
export const registerPackagingAuthority=Object.freeze({
 "publicCommit": "5ae13f6107d1efe03b348665c729d9511ef046e5",
 "files": 992,
 "inventorySHA256": "a25c3c5af5a92575353f852f81a32baba7b66d6fdd49de9b7ef8c9f70097642c",
 "historicalCommit": "206e0a5191e3d8edd6856619668e70326aa92fff",
 "historicalInventorySHA256": "5e4883f6092fe15a8cdc03b83ecb9c54bedacae1038a1ddcde76be095f064dd2",
 "historicalFiles": 782,
 "currentRunner": "58a9c7af28929f0019e37660532d1f922f4d8f6ba3857ddbc0db07bafe370db4",
 "preDispatchRunner": "7b0bfc65544df736741df84785c347bbf678926ddc5ba3db4c0d329fd5960ad9",
 "historicalRunner": "7b0bfc65544df736741df84785c347bbf678926ddc5ba3db4c0d329fd5960ad9"
});
export function readRegisterSnapshot(gitDir,commit=registerPackagingAuthority.publicCommit){
 assert.ok(typeof gitDir==='string'&&gitDir.length,'Explicit readonly PUBLIC Git object authority required');
 assert.ok([registerPackagingAuthority.publicCommit,registerPackagingAuthority.historicalCommit].includes(commit),'Unknown public checkpoint');
 const git=(args,input)=>{const r=spawnSync('git',['-c','safe.directory='+gitDir,'--git-dir='+gitDir,...args],{input,maxBuffer:128*1024*1024,timeout:20000});assert.equal(r.error,undefined,'PUBLIC Git read failed');assert.equal(r.status,0,'PUBLIC Git unavailable');return r.stdout;};
 const rows=git(['ls-tree','-r','-z',commit,'--','k8s-rewrite/front-end/']).toString().split('\0').filter(Boolean).map(line=>{const [meta,p]=line.split('\t'),[mode,kind,blob]=meta.split(' ');assert.equal(kind,'blob');return [p.slice('k8s-rewrite/front-end/'.length),mode,blob];});
 const historical=commit===registerPackagingAuthority.historicalCommit;
 assert.equal(rows.length,historical?registerPackagingAuthority.historicalFiles:registerPackagingAuthority.files,'Complete public inventory required');
 assert.equal(digest(JSON.stringify(rows)),historical?registerPackagingAuthority.historicalInventorySHA256:registerPackagingAuthority.inventorySHA256,'Public inventory changed');
 const batch=git(['cat-file','--batch'],rows.map(r=>r[2]).join('\n')+'\n');let offset=0;const inputs=new Map();
 for(const [path,mode,oid] of rows){const end=batch.indexOf(10,offset);assert.ok(end>=offset);const [blob,kind,size]=batch.subarray(offset,end).toString().split(' ');assert.equal(blob,oid);assert.equal(kind,'blob');const length=Number(size);assert.ok(Number.isSafeInteger(length)&&length>=0);offset=end+1;const bytes=Buffer.from(batch.subarray(offset,offset+length));assert.equal(bytes.length,length);offset+=length;assert.equal(batch[offset++],10);assert.equal(createHash('sha1').update(Buffer.from('blob '+length+'\0')).update(bytes).digest('hex'),oid,'Raw Git object integrity');inputs.set(path,{mode,bytes});}
 assert.equal(offset,batch.length);return Object.freeze({commit,names:Object.freeze(rows.map(r=>r[0])),read(path){assert.ok(inputs.has(path),'Outside public inventory');return Buffer.from(inputs.get(path).bytes);},mode(path){assert.ok(inputs.has(path),'Outside public inventory');return inputs.get(path).mode;}});
}
export function projectRegisterRegistrations(bytes){
 assert.ok(Buffer.isBuffer(bytes),'Raw Buffer required');assert.equal(digest(bytes),registerMetadataDispatch.sourceSHA256,'Historical registration metadata changed');let result=Buffer.from(bytes);
 for(const span of [...registerMetadataDispatch.spans].reverse()){
  assert.equal(digest(bytes.subarray(span.start,span.end)),span.sha256,'Historical registration changed');
  result=Buffer.concat([result.subarray(0,span.start),Buffer.from('/* '+span.label+' dispatched to '+registerMetadataDispatch.current+' */\n'),result.subarray(span.end)]);
 }return result;
}
export function assertCurrentRegisterRunnerInverse(bytes,historical){
 assert.ok(Buffer.isBuffer(bytes)&&Buffer.isBuffer(historical),'Raw Buffer required');assert.equal(digest(bytes),registerPackagingAuthority.currentRunner,'Current runner changed');assert.equal(digest(historical),registerPackagingAuthority.historicalRunner,'Historical runner changed');
 // Exact raw inverse of the reviewed dispatcher delta, then register import.
 let inverse=bytes.toString().replace('assertArtifactState,dispatchForBatch}','assertArtifactState}').replace("from './current-packaging-unit-plan.mjs'","from './auth-register-current-unit-plan.mjs'").replace('packagingDispatch:plan.packagingDispatch,publicAuthority:plan.publicAuthority,','').replace(' const dispatch=dispatchForBatch(root,batch.files);\r\n','').replace("'tsx',...dispatch.flags,'--test'","'tsx','--test'").replace('env:{...process.env,...dispatch.env},','');
 assert.equal(digest(Buffer.from(inverse)),registerPackagingAuthority.preDispatchRunner,'Exact dispatcher raw inverse');assert.deepEqual(Buffer.from(inverse),historical,'Exact pre-dispatch registration runner raw inverse');
 // Original M14 explicitly used this derived LF projection. Raw pins above do not.
 const canonical=historical.toString().replace("from './auth-register-current-unit-plan.mjs'","from './auth-login-current-unit-plan.mjs'").replaceAll('\r\n','\n');assert.equal(digest(canonical),'bdd0fbb9def1b6a62f397b196d0564897a58d4dc508f3d55b6766193c654892a','Original registration M14 historical inverse retained');
 return true;
}
