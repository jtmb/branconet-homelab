import https from 'node:https';
import { once } from 'node:events';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { performance } from 'node:perf_hooks';
import assert from 'node:assert/strict';
const { KubeConfig } = await import(process.env.BORTUS_DIAGNOSTIC_SDK_URL);
const dir = await mkdtemp(join(tmpdir(), 'bortus-agent-diagnostic-'));
const key = join(dir, 'key.pem'), cert = join(dir, 'cert.pem');
execFileSync('openssl', ['req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'], {stdio:'ignore'});
let connections=0, resumed=0, received=0;
const server = https.createServer({key:await readFile(key),cert:await readFile(cert)},(req,res)=>{
  const id = Number(new URL(req.url,'https://127.0.0.1').searchParams.get('id'));
  if(req.headers.authorization !== 'Bearer synthetic-'+id) {res.writeHead(403);res.end();return;}
  received++;
  setTimeout(()=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({apiVersion:'v1',kind:'SecretList',metadata:{continue:''},items:[{apiVersion:'v1',kind:'Secret',metadata:{namespace:'scope-'+id,name:'object-'+id,resourceVersion:String(id+1)},type:'Opaque',data:JSON.parse('{"__proto__":"","constructor":"","binary":"/wA=","empty":""}')}]}));},12);
});
server.on('secureConnection',socket=>{connections++;if(socket.isSessionReused())resumed++;});
server.listen(0,'127.0.0.1');await once(server,'listening');
const base='https://127.0.0.1:'+server.address().port;
const results=[];
try {
  for(const [run,order] of [[1,['per-request','sessions','keepalive']],[2,['sessions','per-request','keepalive']],[3,['keepalive','sessions','per-request']]]) {
    for(const variant of order) {
      const config=new KubeConfig();
      config.loadFromString(JSON.stringify({apiVersion:'v1',kind:'Config',clusters:[{name:'fixture',cluster:{server:base,'certificate-authority':cert}}],users:[{name:'fixture',user:{}}],contexts:[{name:'fixture',context:{cluster:'fixture',user:'fixture'}}],'current-context':'fixture'}));
      const agents=new Set();let pooled, next=0, authCalls=0, inFlight=0, maxActive=0;
      const observed=[];const before={connections,resumed,received},cpu=process.cpuUsage(),started=performance.now();
      const request=async id=>{
        inFlight++;maxActive=Math.max(maxActive,inFlight);
        try {
          config.getCurrentUser().token='synthetic-'+id;
          const options={method:'GET',rejectUnauthorized:true,headers:{Accept:'application/json'}};
          await config.applyToHTTPSOptions(options);authCalls++;
          const fresh=options.agent;agents.add(fresh);
          assert(fresh.constructor===https.Agent);assert.equal(options.rejectUnauthorized,true);
          if(variant!=='per-request') {
            if(!pooled){pooled=fresh;if(variant==='keepalive'){pooled.keepAlive=true;pooled.maxSockets=4;pooled.maxFreeSockets=4;}}
            else {assert(isDeepStrictEqual(pooled.options,fresh.options));fresh.destroy();options.agent=pooled;}
          }
          options.signal=AbortSignal.timeout(8000);
          const row=await new Promise((resolve,reject)=>{
            const request=https.request(base+'/?id='+id,options,response=>{
              if(response.statusCode!==200){response.destroy();reject(new Error('Fixed diagnostic status failure'));return;}
              const chunks=[];let bytes=0;
              response.on('data',chunk=>{bytes+=chunk.length;if(bytes>4*1024*1024){response.destroy();reject(new Error('Fixed diagnostic byte limit'));return;}chunks.push(chunk);});
              response.once('error',reject);response.once('end',()=>{try{resolve(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks))));}catch{reject(new Error('Fixed diagnostic parse failure'));}});
            });request.once('error',reject);request.end();
          });
          assert.equal(row.kind,'SecretList');assert.equal(row.items.length,1);
          const item=row.items[0];assert.equal(item.metadata.namespace,'scope-'+id);assert.equal(item.metadata.name,'object-'+id);
          assert.deepEqual(Object.keys(item.data).sort(),['__proto__','binary','constructor','empty']);observed.push(id);
        } finally {inFlight--;}
      };
      const worker=async()=>{while(next<18){const id=next++;await request(id);}};
      try{await Promise.all(Array.from({length:4},worker));}
      finally{for(const agent of agents)agent.destroy();}
      assert.deepEqual(observed.sort((a,b)=>a-b),Array.from({length:18},(_,i)=>i));
      assert.equal(authCalls,18);assert.equal(received-before.received,18);assert(maxActive<=4);assert.equal(inFlight,0);
      const used=process.cpuUsage(cpu);
      results.push({run,variant,elapsed_ms:performance.now()-started,whole_diagnostic_process_cpu_ms:(used.user+used.system)/1000,sdk_auth_calls:authCalls,requests:18,maximum_active:maxActive,tls_connections:connections-before.connections,tls_resumed_connections:resumed-before.resumed,exact_public_inventory_passed:true,owned_agents_destroyed:true});
    }
  }
  console.log(JSON.stringify({scope:'separate synthetic direct-TLS Agent diagnostic; not frozen acceptance',node:process.version,platform:process.platform,arch:process.arch,producer_delay_ms:12,limits:{maximum_active:4,request_deadline_ms:8000,maximum_response_bytes:4194304},observations:results,limitations:['Transport microdiagnostic only; no Next/middleware/Prisma path, large-page retries or proxy/mTLS behavior measured.','Every request refreshes SDK authentication and exact Agent security options; transient synthetic auth/CA material never enters output.','CPU covers client plus producer in the same diagnostic process; physical/background isolation is not claimed.']},null,2));
} finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}