'use strict';
const assert=require('node:assert/strict'),https=require('node:https'),http=require('node:http'),fs=require('node:fs');
const {AsyncLocalStorage}=require('node:async_hooks');
const {performance,PerformanceObserver}=require('node:perf_hooks');
function install(output){
 assert.equal(process.version,'v22.23.3');
 const als=new AsyncLocalStorage(),records=[],sockets=new WeakMap(),gc=[];let capped=false,socketSequence=0,openSockets=0,maxOpenSockets=0;
 const collectGC=list=>{for(const event of list.getEntries()){if(gc.length>=2048){capped=true;continue;}gc.push({start_ms:event.startTime,duration_ms:event.duration,kind:event.detail?.kind??null});}};
 const gcObserver=new PerformanceObserver(collectGC);gcObserver.observe({entryTypes:['gc']});
 const allowed=new Set(['native.factory','native.storeFactory','native.summary','native.list','native.queue','native.fetchHeaders','native.bodyText','native.objectValidation','native.sdkProcessor','native.bufferConcat','native.bufferToString','native.utf8Decode','native.jsonParse','native.jsonStringify','auth.jwt','auth.session','auth.headerSession','auth.currentSession','auth.middleware','auth.role','auth.authorize','auth.accountSQL','route.secrets','response.envelope','config.construct','config.loadFromDefault','config.loadFromCluster','config.loadFromFile','sdk.applyOptions','sdk.applyToHTTPSOptions','sdk.applySecurityAuthentication','sdk.makeApiClient']);
 function aggregate(container,label,duration,failed){
  if(!container[label]){if(Object.keys(container).length>=64){capped=true;return;}container[label]={calls:0,total_ms:0,max_ms:0,failed:0};}
  const stage=container[label];stage.calls++;stage.total_ms+=duration;stage.max_ms=Math.max(stage.max_ms,duration);stage.failed+=Number(failed);
 }
 function span(label,operation){
  assert(allowed.has(label),'Unknown diagnostic stage');const context=als.getStore();if(!context)return operation();
  const start=performance.now();
  const finish=(failed,result)=>{const duration=performance.now()-start;aggregate(context.record.stages,label,duration,failed);if(context.attempt){aggregate(context.attempt.stages,label,duration,failed);if(!failed&&['native.bodyText','native.utf8Decode'].includes(label)&&typeof result==='string')context.attempt.decoded_body_utf8_bytes=Buffer.byteLength(result);if(!failed&&label==='native.bufferConcat'&&Buffer.isBuffer(result))context.attempt.concat_output_bytes=(context.attempt.concat_output_bytes??0)+result.length;}};
  return als.run({...context,stage:label},()=>{try{const result=operation();if(result&&typeof result.then==='function')return result.then(value=>{finish(false,value);return value;},error=>{finish(true);throw error;});finish(false,result);return result;}catch(error){finish(true);throw error;}});
 }
 function attempt(operation,limit,continued){
  const context=als.getStore();if(!context)return operation();assert(Number.isSafeInteger(limit)&&limit>=1&&limit<=200&&typeof continued==='boolean');
  if(context.record.attempts.length>=128){capped=true;return operation();}
  const entry={id:context.record.attempts.length+1,limit,continued,start_ms:performance.now(),stages:{},delivered_body_bytes:0,finished:false};context.record.attempts.push(entry);
  const finish=failed=>{entry.finished=true;entry.failed=failed;entry.finish_ms=performance.now();};
  return als.run({...context,attempt:entry},()=>{try{const result=operation();if(result&&typeof result.then==='function')return result.then(value=>{finish(false);return value;},error=>{finish(true);throw error;});finish(false);return result;}catch(error){finish(true);throw error;}});
 }
 function counter(label,value){assert.equal(label,'native.deliveredBodyBytes');assert(Number.isSafeInteger(value)&&value>=0);const context=als.getStore();if(context?.attempt)context.attempt.delivered_body_bytes+=value;}
 const decorated=new WeakSet();
 function decorateConfig(config){
  if(decorated.has(config))return config;decorated.add(config);
  for(const name of ['loadFromDefault','loadFromCluster','loadFromFile','applyOptions','applyToHTTPSOptions','applySecurityAuthentication','makeApiClient']){
   assert.equal(typeof config[name],'function','Unexpected SDK config method');const original=config[name];
   config[name]=function(...args){return span((name.startsWith('load')?'config.':'sdk.')+name,()=>{
    const result=original.apply(this,args);
    if(name==='makeApiClient'){
     const processor=result?.api?.responseProcessor;assert(processor&&typeof processor.listNamespacedSecretWithHttpInfo==='function','Unexpected SDK response processor');
     const originalProcessor=processor.listNamespacedSecretWithHttpInfo;
     processor.listNamespacedSecretWithHttpInfo=function(...processorArgs){return span('native.sdkProcessor',()=>originalProcessor.apply(this,processorArgs));};
    }
    return result;
   });};
  }
  return config;
 }
 function begin(id,operation){
  assert(/^native-diag-\d{1,4}$/.test(id));if(records.length>=64){capped=true;return operation();}
  const record={id,start_ms:performance.now(),stages:{},attempts:[],finished:false};records.push(record);return als.run({record},()=>operation(record));
 }
 const restorations=[];
 function replace(object,name,wrapped){const original=object[name];object[name]=wrapped(original);restorations.push(()=>{object[name]=original;});}
 for(const [object,name,label]of [[Buffer,'concat','native.bufferConcat'],[Buffer.prototype,'toString','native.bufferToString'],[TextDecoder.prototype,'decode','native.utf8Decode'],[JSON,'parse','native.jsonParse'],[JSON,'stringify','native.jsonStringify']]){
  replace(object,name,original=>function(...args){const context=als.getStore();return context?.attempt?span(label,()=>original.apply(this,args)):original.apply(this,args);});
 }
 replace(https,'request',original=>function(...args){
  const context=als.getStore(),request=original.apply(this,args);if(!context?.attempt)return request;const entry=context.attempt;
  entry.https_start_ms=performance.now();
  request.once('socket',socket=>{
   entry.socket_assigned_ms=performance.now();entry.reused_socket=!!request.reusedSocket;
   if(!sockets.has(socket)){
    sockets.set(socket,++socketSequence);openSockets++;maxOpenSockets=Math.max(maxOpenSockets,openSockets);
    socket.once('close',()=>{openSockets--;});
    socket.once('secureConnect',()=>{entry.tls_complete_ms=performance.now();entry.tls_session_resumed=socket.isSessionReused();});
   }
   entry.socket_id=sockets.get(socket);
  });
  request.once('response',response=>{entry.headers_ms=performance.now();entry.status=response.statusCode;response.once('end',()=>{entry.body_end_ms=performance.now();entry.body_complete=true;});response.once('close',()=>{entry.response_closed=true;});});
  return request;
 });
 replace(http.Server.prototype,'emit',original=>function(name,...args){
  if(name!=='request')return original.call(this,name,...args);
  const [request,response]=args,id=request.headers['x-bortus-diagnostic-id'];
  if(request.url!=='/api/secrets'||typeof id!=='string'||!/^native-diag-\d{1,4}$/.test(id))return original.call(this,name,...args);
  return begin(id,record=>{const cpu=process.cpuUsage(),elu=performance.eventLoopUtilization();record.memory_before=process.memoryUsage();response.once('finish',()=>{record.finished=true;record.finish_ms=performance.now();record.status=response.statusCode;record.process_cpu_delta_us=process.cpuUsage(cpu);record.event_loop_utilization_delta=performance.eventLoopUtilization(elu);record.memory_after=process.memoryUsage();});return original.call(this,name,...args);});
 });
 const api=Object.freeze({span,attempt,counter,decorateConfig});globalThis.__bortusNativeDiag=api;
 const snapshot=()=>({scope:'Native stage diagnostic only; never acceptance',node:process.version,request_records:records,gc,capped,tls:{connections:socketSequence,open:openSockets,max_open:maxOpenSockets},limitations:['Inclusive nested stages and observer overhead','SDK processor includes body/parse/deserialization; residual is not causal attribution','Process CPU/ELU/memory deltas and GC overlap do not establish stage causality','No arguments, URLs, cursors, cookies, auth identifiers, values, bodies or errors recorded']});
 const persist=()=>{gcObserver.disconnect();if(output)fs.writeFileSync(output,JSON.stringify(snapshot(),null,2)+'\n',{mode:0o600});};process.once('exit',persist);
 return {api,begin,snapshot,restore(){process.removeListener('exit',persist);gcObserver.disconnect();for(const restore of restorations.reverse())restore();delete globalThis.__bortusNativeDiag;}};
}
module.exports={install};
