'use strict';
const assert=require('node:assert/strict');
const {install}=require('./observer.cjs');
(async()=>{
 const observer=install();
 try{
  const hidden={annotation:'PUBLIC_DIAGNOSTIC_SENTINEL'};
  const value=await observer.begin('native-diag-1',async()=>observer.api.attempt(async()=>{
   const parsed=JSON.parse('{"items":[]}');assert.deepEqual(parsed,{items:[]});
   for(let i=0;i<10000;i++)observer.api.span('native.summary',()=>hidden);
   observer.api.counter('native.deliveredBodyBytes',19);
   return observer.api.span('auth.jwt',async()=>hidden);
  },200,false));assert.equal(value,hidden);
  const rejected=new Error('PUBLIC_DIAGNOSTIC_ERROR_SENTINEL');
  await assert.rejects(observer.begin('native-diag-2',()=>observer.api.attempt(()=>observer.api.span('sdk.applyOptions',()=>Promise.reject(rejected)),10,true)),error=>error===rejected);
  const sdk={};let thisChecks=0;
  for(const name of ['loadFromDefault','loadFromCluster','loadFromFile','applyOptions','applyToHTTPSOptions','applySecurityAuthentication','makeApiClient'])sdk[name]=function(){assert.equal(this,sdk);thisChecks++;return name==='makeApiClient'?{api:{responseProcessor:{listNamespacedSecretWithHttpInfo:async()=>hidden}}}:hidden;};
  observer.api.decorateConfig(sdk);observer.api.decorateConfig(sdk);
  const sdkValue=await observer.begin('native-diag-3',()=>sdk.applyOptions());assert.equal(sdkValue,hidden);assert.equal(thisChecks,1);
  const snapshot=observer.snapshot();assert.equal(snapshot.capped,false);assert.equal(snapshot.request_records[0].stages['native.summary'].calls,10000);assert.equal(snapshot.request_records[0].attempts.length,1);assert.equal(snapshot.request_records[0].attempts[0].delivered_body_bytes,19);assert.equal(snapshot.request_records[1].attempts[0].failed,true);assert.equal(snapshot.request_records[2].stages['sdk.applyOptions'].calls,1);
  const serialized=JSON.stringify(snapshot);assert(!serialized.includes('PUBLIC_DIAGNOSTIC_SENTINEL'));assert(!serialized.includes('PUBLIC_DIAGNOSTIC_ERROR_SENTINEL'));
  assert.throws(()=>observer.api.span('arbitrary-caller-label',()=>null));assert.throws(()=>observer.begin('unsafe-id',()=>null));
  if(process.argv[2]){
   const {createRequire}=require('node:module'),path=require('node:path');
   const client=createRequire(path.join(process.argv[2],'package.json'))('@kubernetes/client-node');
   const config=new client.KubeConfig();config.loadFromOptions({clusters:[{name:'fixture',server:'https://example.invalid'}],users:[{name:'fixture'}],contexts:[{name:'fixture',user:'fixture',cluster:'fixture'}],currentContext:'fixture'});
   const api=observer.api.decorateConfig(config).makeApiClient(client.CoreV1Api);assert.equal(typeof api.api.responseProcessor.listNamespacedSecretWithHttpInfo,'function');
  }
  console.log(JSON.stringify({passed:true,tests:['generic return/error identity','10000 stage aggregation uncapped','fresh SDK wrapper preserves this and no double decoration','metadata excludes results/errors','unknown IDs/labels refused','actual SDK1.4.0 config/processor shape, no request']}));
 }finally{observer.restore();}
})().catch(()=>{process.exitCode=1;});
