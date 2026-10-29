import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const digest=b=>createHash('sha256').update(b).digest('hex');
export const loginMetadataDispatch=Object.freeze({
 "original": "tests/auth-login-current-unit-plan.test.mjs",
 "current": "tests/auth-login-current-packaging.test.mjs",
 "metadata": "tests/current-login-packaging.test.mjs",
 "sourceSHA256": "929c448d836dbfe3e586ccc167e5cac2160a69e34a7272395b081e90fe6d1d6c",
 "spans": [
  {
   "label": "M14",
   "start": 7720,
   "end": 8194,
   "sha256": "95013b19905d8248163fc0982930fc8e462a99590e7ffd9406923f839432956b"
  },
  {
   "label": "M15",
   "start": 8194,
   "end": 9488,
   "sha256": "2f9124b7e0e043994e961337bc85ad4e83b672299dbd9b3b188f38694eb14e30"
  }
 ]
});
export const loginPackagingAuthority=Object.freeze({
 "publicCommit": "075b74d22965e59594b23e4cd6750beec956070c",
 "files": 989,
 "inventorySHA256": "b2a7cb4242a655e82b4b60d3c0da7d7554e91f23dc03c680dda9be428feb70f7",
 "historicalCommit": "02a9e1fc6f4cb8ba50f6ee7f6d36ac15a3aecde6",
 "historicalInventorySHA256": "67567274ff3f5001e0bd30718549e52cf87d3cf289a3a2f18a5057fc218a1295",
 "historicalFiles": 779,
 "currentRunner": "58a9c7af28929f0019e37660532d1f922f4d8f6ba3857ddbc0db07bafe370db4",
 "preDispatchRunner": "7b0bfc65544df736741df84785c347bbf678926ddc5ba3db4c0d329fd5960ad9",
 "historicalRunner": "bdd0fbb9def1b6a62f397b196d0564897a58d4dc508f3d55b6766193c654892a"
});
export function readPublicSnapshot(gitDir,commit=loginPackagingAuthority.publicCommit){
 assert.ok(typeof gitDir==='string'&&gitDir.length,'Explicit readonly PUBLIC Git object authority required');
 assert.ok([loginPackagingAuthority.publicCommit,loginPackagingAuthority.historicalCommit].includes(commit),'Unknown public checkpoint');
 const git=(args,input)=>{const r=spawnSync('git',['-c','safe.directory='+gitDir,'--git-dir='+gitDir,...args],{input,maxBuffer:128*1024*1024,timeout:20000});assert.equal(r.error,undefined,'PUBLIC Git read failed');assert.equal(r.status,0,'PUBLIC Git unavailable');return r.stdout;};
 const rows=git(['ls-tree','-r','-z',commit,'--','k8s-rewrite/front-end/']).toString().split('\0').filter(Boolean).map(line=>{const [meta,p]=line.split('\t'),[mode,kind,blob]=meta.split(' ');assert.equal(kind,'blob');return [p.slice('k8s-rewrite/front-end/'.length),mode,blob];});
 const historical=commit===loginPackagingAuthority.historicalCommit;
 assert.equal(rows.length,historical?loginPackagingAuthority.historicalFiles:loginPackagingAuthority.files,'Complete public inventory required');
 assert.equal(digest(JSON.stringify(rows)),historical?loginPackagingAuthority.historicalInventorySHA256:loginPackagingAuthority.inventorySHA256,'Public inventory changed');
 const batch=git(['cat-file','--batch'],rows.map(r=>r[2]).join('\n')+'\n');let offset=0;const inputs=new Map();
 for(const [path,mode,oid] of rows){const end=batch.indexOf(10,offset);assert.ok(end>=offset);const [blob,kind,size]=batch.subarray(offset,end).toString().split(' ');assert.equal(blob,oid);assert.equal(kind,'blob');const length=Number(size);assert.ok(Number.isSafeInteger(length)&&length>=0);offset=end+1;const bytes=Buffer.from(batch.subarray(offset,offset+length));assert.equal(bytes.length,length);offset+=length;assert.equal(batch[offset++],10);assert.equal(createHash('sha1').update(Buffer.from('blob '+length+'\0')).update(bytes).digest('hex'),oid,'Raw Git object integrity');inputs.set(path,{mode,bytes});}
 assert.equal(offset,batch.length);return Object.freeze({commit,names:Object.freeze(rows.map(r=>r[0])),read(path){assert.ok(inputs.has(path),'Outside public inventory');return Buffer.from(inputs.get(path).bytes);},mode(path){assert.ok(inputs.has(path),'Outside public inventory');return inputs.get(path).mode;}});
}
export function projectLoginRegistrations(bytes){
 assert.ok(Buffer.isBuffer(bytes),'Raw Buffer required');assert.equal(digest(bytes),loginMetadataDispatch.sourceSHA256,'Historical login metadata changed');let result=Buffer.from(bytes);
 for(const span of [...loginMetadataDispatch.spans].reverse()){
  assert.equal(digest(bytes.subarray(span.start,span.end)),span.sha256,'Historical login registration changed');
  result=Buffer.concat([result.subarray(0,span.start),Buffer.from('/* '+span.label+' dispatched to '+loginMetadataDispatch.current+' */\n'),result.subarray(span.end)]);
 }return result;
}
export function assertCurrentRunnerInverse(bytes,historical){
 assert.ok(Buffer.isBuffer(bytes)&&Buffer.isBuffer(historical),'Raw Buffer required');assert.equal(digest(bytes),loginPackagingAuthority.currentRunner,'Current runner changed');assert.equal(digest(historical),loginPackagingAuthority.historicalRunner,'Historical runner changed');
 // Exact raw inverse of the reviewed dispatcher delta, then register import.
 let inverse=bytes.toString().replace('assertArtifactState,dispatchForBatch}','assertArtifactState}').replace("from './current-packaging-unit-plan.mjs'","from './auth-register-current-unit-plan.mjs'").replace('packagingDispatch:plan.packagingDispatch,publicAuthority:plan.publicAuthority,','').replace(' const dispatch=dispatchForBatch(root,batch.files);\r\n','').replace("'tsx',...dispatch.flags,'--test'","'tsx','--test'").replace('env:{...process.env,...dispatch.env},','');
 assert.equal(digest(Buffer.from(inverse)),loginPackagingAuthority.preDispatchRunner,'Exact dispatcher raw inverse');inverse=inverse.replace("from './auth-register-current-unit-plan.mjs'","from './auth-login-current-unit-plan.mjs'");assert.deepEqual(Buffer.from(inverse),historical,'Exact registration-chain raw inverse');
 // Original M14 explicitly used this derived LF projection. Raw pins above do not.
 const canonical=historical.toString().replace("from './auth-login-current-unit-plan.mjs'","from './aggregate-unit-plan.mjs'").replaceAll('\r\n','\n');assert.equal(digest(canonical),'07b33c7d19fa6d180b7322035481750ca35ece8d55b4a27200d54ce1a336e868','Original M14 historical inverse retained');
 return true;
}
