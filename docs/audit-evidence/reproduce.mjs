import {execFileSync,spawn} from 'node:child_process';
import {mkdtemp,writeFile,readFile,mkdir,rm} from 'node:fs/promises';
import {createServer,request as httpRequest} from 'node:http';
import path from 'node:path';
import {randomBytes} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(path.resolve(process.cwd(),'package.json'));
const {PrismaClient}=require('@prisma/client');
const {SignJWT}=await import(pathToFileURL(require.resolve('jose')).href);
if(process.platform!=='win32')throw Error('This fixture uses the Windows .NET C# compiler; port the fake CLI for other hosts.');
const packageInfo=JSON.parse(await readFile('package.json','utf8'));
if(packageInfo.name!=='botrus-k8s-manager')throw Error('Run from k8s-rewrite/front-end.');
for(const port of [4206,4207,4208]){
  const probe=createServer();
  await new Promise((resolve,reject)=>{probe.once('error',()=>reject(Error('Audit port '+port+' is already in use; stop the fixture or choose a separate environment.')));probe.listen(port,'127.0.0.1',resolve);});
  await new Promise(resolve=>probe.close(resolve));
}
const root=process.cwd(); await mkdir(path.join(root,'tmp'),{recursive:true});
const dir=await mkdtemp(path.join(root,'tmp','audit-'));
const fixture=path.join(dir,'bin'); await mkdir(fixture);
const created='2026-10-01T00:00:00Z';
const pod=(name,ns,restarts)=>({metadata:{name,namespace:ns,uid:name,creationTimestamp:created,ownerReferences:[{kind:'ReplicaSet',name:'api-worker-rs'}]},spec:{nodeName:'audit-node',containers:[{name:'app',image:'example.invalid/audit:v1'}]},status:{phase:'Running',containerStatuses:[{name:'app',ready:true,restartCount:restarts}],podIP:'10.0.0.1'}});
const node={metadata:{name:'audit-node',creationTimestamp:created},status:{conditions:[{type:'Ready',status:'True'}],nodeInfo:{kubeletVersion:'v1.34.1'},capacity:{cpu:'2',memory:'2Gi'},allocatable:{cpu:'2',memory:'2Gi'}}};
const dep=(name)=>({metadata:{name,namespace:'apps',creationTimestamp:created},spec:{replicas:1,template:{spec:{containers:[{image:'example.invalid/audit:v1'}]}}},status:{replicas:1,readyReplicas:1,updatedReplicas:1,availableReplicas:1,conditions:[{type:'Available',status:'True'}]}});
const data={nodes:{items:[node]},pods:{items:[pod('api-worker-rs-0','apps',7),pod('system-pod','kube-system',12),pod('second-app','apps',2)]},deployments:{items:[dep('api'),dep('api-worker')]},namespaces:{items:[{metadata:{name:'apps',creationTimestamp:created},status:{phase:'Active'}}]},services:{items:[]},ingress:{items:[]},pv:{items:[]},pvc:{items:[]},sc:{items:[]},'volumes.longhorn.io':{items:[]}};
for(const [key,value] of Object.entries(data)) await writeFile(path.join(fixture,key+'.json'),JSON.stringify(value));
const cs=`using System; using System.IO; using System.Threading;
class AuditKubectl { static int Main(string[] args) {
 string d=Environment.GetEnvironmentVariable("AUDIT_FIXTURE_DIR"); if(String.IsNullOrEmpty(d)||!Directory.Exists(d)) return 90;
 int p=Array.IndexOf(args,"get"); string r=p>=0&&args.Length>p+1?args[p+1]:"mutation";
 using(Mutex m=new Mutex(false,"Local\\\\BortusAuditLog")) { m.WaitOne(); try {File.AppendAllText(Path.Combine(d,"calls.log"),r+"\\n");}finally{m.ReleaseMutex();} }
 Thread.Sleep(50);
 string failure=Path.Combine(d,"fail.txt"); if(File.Exists(failure)&&(File.ReadAllText(failure).Trim()=="all"||File.ReadAllText(failure).Trim()==r)){Console.Error.Write("simulated kubectl failure");return 1;}
 if(p<0){Console.Error.Write("simulated kubectl failure"); return 1;}
 foreach(string a in args) if(a.StartsWith("--raw=")){ Console.Write("{\\"kind\\":\\"AuditRawResponse\\",\\"items\\":[]}"); return 0;}
 string f=Path.Combine(d,r+".json"); Console.Write(File.Exists(f)?File.ReadAllText(f):"{\\"items\\":[]}");return 0;
} }`;
await writeFile(path.join(dir,'fake-kubectl.cs'),cs);
execFileSync('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe',['/nologo','/out:'+path.join(fixture,'kubectl.exe'),path.join(dir,'fake-kubectl.cs')],{stdio:'pipe'});
const database='file:'+path.join(dir,'audit.db').replaceAll('\\','/');
const cfg=path.join(dir,'config.json'); await writeFile(cfg,JSON.stringify({apiVersion:'v1',kind:'Config',clusters:[{name:'audit',cluster:{server:'https://127.0.0.1:1'}}],users:[{name:'audit',user:{}}],contexts:[{name:'audit',context:{cluster:'audit',user:'audit'}}],'current-context':'audit'}));
const key=randomBytes(48).toString('hex');
const cleanEnv=Object.fromEntries(['SystemRoot','WINDIR','COMSPEC','PATH','TEMP','TMP','USERPROFILE','HOME','SystemDrive','APPDATA','LOCALAPPDATA'].filter(k=>process.env[k]!==undefined).map(k=>[k,process.env[k]]));
const env={...cleanEnv,DATABASE_URL:database,BOTRUS_JWT_SECRET:key,BOTRUS_SECRETS_KEY:randomBytes(32).toString('hex'),KUBECONFIG:cfg,BORTUS_SECRET_NAMESPACES:'apps',BORTUS_DISABLE_PROVISIONING:'true',NODE_ENV:'production',HOSTNAME:'127.0.0.1',PORT:'4206',AUDIT_FIXTURE_DIR:fixture,PATH:fixture+path.delimiter+process.env.PATH};delete env.RUST_LOG;delete env.KUBERNETES_SERVICE_HOST;delete env.BORTUS_SECRET_ALIASES_FILE;
execFileSync(process.execPath,[path.resolve('node_modules/prisma/build/index.js'),'migrate','deploy'],{env,stdio:'pipe'});
const db=new PrismaClient({datasources:{db:{url:database}}});
const child=spawn(process.execPath,[path.resolve('.next/standalone/server.js')],{env,cwd:root,stdio:['ignore','pipe','pipe']});let serverOutput=''; child.stdout.on('data',x=>serverOutput+=x);child.stderr.on('data',x=>serverOutput+=x);
const origin='http://127.0.0.1:4206';
const servers=[];
let interval;
async function stop(){
  if(interval)clearInterval(interval);
  for(const server of servers){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  if(child.exitCode===null&&child.signalCode===null){child.kill();await new Promise(resolve=>child.once('exit',resolve));}
  await db.$disconnect();
  const allowed=path.resolve(root,'tmp')+path.sep;
  if(!path.resolve(dir).startsWith(allowed)||!path.basename(dir).startsWith('audit-'))throw Error('Unsafe fixture cleanup target');
  await rm(dir,{recursive:true,force:true});
}
try {
let ready=false;
for(let i=0;i<100;i++){
  if(child.exitCode!==null||child.signalCode!==null)throw Error('Isolated server exited before readiness.');
  try{if(serverOutput.includes('Ready')&&(await fetch(origin+'/api/health/live',{signal:AbortSignal.timeout(1000)})).ok){ready=true;break;}}catch{}
  await new Promise(r=>setTimeout(r,100));
}
if(!ready)throw Error('Isolated server did not become ready.');
const results={base:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),node:process.version,platform:process.platform,cliDelayMs:50,productionServerPid:child.pid};
const req=async(url,token,options={})=>{const start=performance.now();const response=await fetch(origin+url,{...options,signal:AbortSignal.timeout(10000),headers:{...(token?{cookie:'botrus_auth_token='+token}:{}),...options.headers}});const body=await response.text();return{status:response.status,ms:+(performance.now()-start).toFixed(2),body};};
const racePassword=randomBytes(16).toString('hex');
const reg=await Promise.all(['audit_boot_a','audit_boot_b'].map(username=>req('/api/auth/register',null,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password:racePassword})})));
results.firstRegistration={statuses:reg.map(x=>x.status),writeUsers:await db.user.count({where:{role:'write'}})};
await db.user.deleteMany();
const a=await db.user.create({data:{username:'audit_admin_a',passwordHash:'unused-fixture-hash',role:'write'}});
const b=await db.user.create({data:{username:'audit_admin_b',passwordHash:'unused-fixture-hash',role:'write'}});
const reader=await db.user.create({data:{username:'audit_reader',passwordHash:'unused-fixture-hash',role:'readonly'}});
const deleted=await db.user.create({data:{username:'audit_deleted',passwordHash:'unused-fixture-hash',role:'readonly'}});
const token=async(user)=>new SignJWT({sub:user.id,username:user.username}).setProtectedHeader({alg:'HS256'}).setIssuedAt().setExpirationTime('1h').sign(new TextEncoder().encode(key));
const ta=await token(a),tb=await token(b),tr=await token(reader),td=await token(deleted);
await db.variable.createMany({data:Array.from({length:200},(_,i)=>({key:'audit_config_'+i,value:'nonsecret fixture',category:'general',encrypted:false}))});
await db.user.delete({where:{id:deleted.id}});
const deletedRead=await req('/api/nodes',td),deletedSession=await req('/api/auth/session',td),deletedSecrets=await req('/api/secrets',td);
results.deletedSession={nodesStatus:deletedRead.status,session:JSON.parse(deletedSession.body),nativeSecretsStatus:deletedSecrets.status};
const calls=async()=>{try{return(await readFile(path.join(fixture,'calls.log'),'utf8')).trim().split('\n').filter(Boolean).length;}catch{return 0;}};
const routes=['/api/cluster/pods','/api/cluster/services','/api/cluster/deployments'];
results.cacheRoutes=[];for(const route of routes){const before=await calls();const r=await req(route,ta);results.cacheRoutes.push({route,status:r.status,ms:r.ms,cliCalls:(await calls())-before});}
const beforeConcurrent=await calls();const concurrent=await Promise.all(Array.from({length:20},()=>req('/api/cluster/pods',ta)));results.warmConcurrent={requests:20,cliCalls:(await calls())-beforeConcurrent,minMs:Math.min(...concurrent.map(x=>x.ms)),maxMs:Math.max(...concurrent.map(x=>x.ms))};
const samples=[];for(let i=0;i<12;i++)samples.push((await req('/api/cluster/pods',ta)).ms);samples.sort((a,b)=>a-b);results.warmLatency={n:12,p50Ms:samples[5],p95Ms:samples[11]};
const deployments=JSON.parse((await req('/api/cluster/deployments',ta)).body).deployments;results.deploymentRestartMapping=deployments.map(x=>({name:x.name,restarts:x.restarts}));
const types=await Promise.all(['app','system'].map(type=>req('/api/cluster/pods?type='+type,ta)));results.podTypeFilter={sameResponse:types[0].body===types[1].body,appCount:JSON.parse(types[0].body).pods.length,systemCount:JSON.parse(types[1].body).pods.length};
results.missingRoutes=[];for(const route of ['/api/cluster/pods/apps/api-worker-rs-0/logs','/api/cluster/nodes/audit-node/yaml','/api/cluster/ingresses/apps/audit/yaml'])results.missingRoutes.push({route,status:(await req(route,ta)).status});
const failed=await req('/api/cluster/deployments/apps/api/scale',ta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({replicas:2})});results.failedScale={status:failed.status,response:JSON.parse(failed.body)};
const injected=await req('/api/cluster/namespaces/'+encodeURIComponent('apps --raw=/version')+'/yaml',tr);results.flagInjection={status:injected.status,acceptedRawOption:injected.body.includes('AuditRawResponse')};
const demotions=await Promise.all([[ta,b.id],[tb,a.id]].map(([t,id])=>req('/api/users/'+id,t,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:'readonly',password:randomBytes(16).toString('hex')})})));results.lastWriteRace={statuses:demotions.map(x=>x.status),remainingWriters:await db.user.count({where:{role:'write'}})};await db.user.updateMany({where:{id:{in:[a.id,b.id]}},data:{role:'write'}});
await writeFile(path.join(fixture,'fail.txt'),'all');await req('/api/cluster/refresh',ta,{method:'POST'});
const outageBefore=await calls();const outage=await req('/api/cluster/pods',ta);const outageAgain=await req('/api/cluster/pods',ta);results.outage={status:outage.status,response:JSON.parse(outage.body),secondStatus:outageAgain.status,cliCalls:(await calls())-outageBefore};await writeFile(path.join(fixture,'fail.txt'),'');
await new Promise(resolve=>setTimeout(resolve,11000));
const beforeCold=await calls();
const cold=await Promise.all(Array.from({length:20},()=>req('/api/cluster/pods',ta)));
results.coldConcurrent={requests:20,cliCalls:(await calls())-beforeCold,statuses:[...new Set(cold.map(r=>r.status))],minMs:Math.min(...cold.map(r=>r.ms)),maxMs:Math.max(...cold.map(r=>r.ms))};
const gateway=async(port,t)=>{const server=createServer(async(request,response)=>{const u=new URL(request.url,'http://127.0.0.1');if(request.method!=='GET'){response.writeHead(405,{'Content-Type':'application/json'});response.end(JSON.stringify({error:'Audit UI gateway allows reads only'}));return;}if(u.pathname==='/audit-evidence'){response.setHeader('Content-Type','application/json');response.end(JSON.stringify(results));return;}if(u.pathname.startsWith('/_next/static/')||u.pathname.startsWith('/images/')){try{const f=u.pathname.startsWith('/_next/static/')?path.join(root,'.next/static',decodeURIComponent(u.pathname.slice('/_next/static/'.length))):path.join(root,'public',u.pathname);const body=await readFile(f);response.setHeader('Content-Type',f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'image/webp');response.end(body);}catch{response.statusCode=404;response.end();}return;}const start=performance.now();const upstream=httpRequest(origin+request.url,{method:request.method,headers:{...request.headers,cookie:'botrus_auth_token='+t,host:'127.0.0.1:4206'}},r=>{response.writeHead(r.statusCode,r.headers);r.pipe(response);r.on('end',()=>{results.browserRequests??=[];results.browserRequests.push({route:u.pathname,status:r.statusCode,ms:+(performance.now()-start).toFixed(2)});});});upstream.on('error',()=>{response.statusCode=502;response.end();});request.pipe(upstream);});await new Promise(r=>server.listen(port,'127.0.0.1',r));return server;};
if(process.argv.includes('--ui')){servers.push(await gateway(4207,ta));servers.push(await gateway(4208,tr));
await writeFile(path.join(root,'tmp/audit-reproduction-ready.json'),JSON.stringify({dir,pid:child.pid,adminUrl:'http://127.0.0.1:4207',readonlyUrl:'http://127.0.0.1:4208'},null,2));
console.log('AUDIT_READONLY_UI_GATEWAYS 4207 (write identity), 4208 (readonly identity)');
}
delete results.productionServerPid;
await writeFile(path.join(root,'tmp/audit-reproduction-results.json'),JSON.stringify(results,null,2));
console.log(JSON.stringify(results,null,2));
if(process.argv.includes('--ui')){
  await new Promise(resolve=>{process.once('SIGINT',resolve);process.once('SIGTERM',resolve);});
}
} finally { await stop(); }