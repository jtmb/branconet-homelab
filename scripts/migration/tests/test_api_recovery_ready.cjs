'use strict';
// PUBLIC generated certificates only; exact production readiness source supplied
// as a read-only fixture asset, endpoints and /proof paths remain unchanged.
const fs=require('node:fs'),cp=require('node:child_process'),https=require('node:https');
const assert=require('node:assert/strict');
const program=fs.readFileSync('/fixture/readiness-source.cjs','utf8');
const template=fs.readFileSync('/program/bortus-api-secret-proof.cjs');
const crypto=require('node:crypto');
assert.equal(crypto.createHash('sha256').update(template).digest('hex'),
 '918f71713074bfa7bc7739bde2574932aa89655bb9d66aed4c0a535123279c9d');
const dir='/tmp/public-readiness';fs.mkdirSync(dir,{mode:0o700});
function openssl(args){cp.execFileSync('/usr/bin/openssl',args,{stdio:'ignore',timeout:10000})}
function cert(name,ca,san){
 openssl(['req','-new','-newkey','rsa:2048','-nodes','-subj','/CN=public-fixture',
  '-keyout',dir+'/'+name+'.key','-out',dir+'/'+name+'.csr']);
 fs.writeFileSync(dir+'/'+name+'.ext',san?'subjectAltName=IP:'+san+'\n':'extendedKeyUsage=clientAuth\n');
 openssl(['x509','-req','-in',dir+'/'+name+'.csr','-CA',dir+'/'+ca+'.crt','-CAkey',dir+'/'+ca+'.key',
  '-CAcreateserial','-days','1','-extfile',dir+'/'+name+'.ext','-out',dir+'/'+name+'.crt']);
}
for(const name of ['ca','other'])openssl(['req','-x509','-newkey','rsa:2048','-nodes','-days','1',
 '-subj','/CN=public-'+name,'-keyout',dir+'/'+name+'.key','-out',dir+'/'+name+'.crt']);
cert('client','ca',null);cert('server','ca','192.168.0.4');
cert('badca','other','192.168.0.4');cert('badsan','ca','192.168.0.5');
for(const [name,from]of [['ca.crt','ca.crt'],['admin.crt','client.crt'],['admin.key','client.key']])
 fs.writeFileSync('/proof/'+name,fs.readFileSync(dir+'/'+from),{mode:0o400,flag:'wx'});
let passed=0;const records=[];
async function run(name,options={}){
 const sockets=new Set();let requests=0,server=null;
 const listen=async()=>{
  const identity=options.identity||'server';
  server=https.createServer({key:fs.readFileSync(dir+'/'+identity+'.key'),
   cert:fs.readFileSync(dir+'/'+identity+'.crt'),ca:fs.readFileSync(dir+'/ca.crt'),
   requestCert:true,rejectUnauthorized:true},(req,res)=>{
   requests++;assert.equal(req.method,'GET');assert.equal(req.url,'/readyz');
   if(options.mutate){fs.chmodSync('/proof/ca.crt',0o600);fs.appendFileSync('/proof/ca.crt','\n');fs.chmodSync('/proof/ca.crt',0o400)}
   res.statusCode=options.status||(requests<= (options.startup||0)?503:200);
   res.setHeader('Content-Type','text/plain; charset=utf-8');
   if(options.encoding)res.setHeader('Content-Encoding',options.encoding);
   if(options.length)res.setHeader('Content-Length',String(options.length));
   if(options.quiet){res.write('o');return}
   res.end(options.body|| (res.statusCode===200?'ok':'PUBLIC REFUSAL BODY'));
  });
  server.on('tlsClientError',()=>{});server.on('connection',s=>{sockets.add(s);s.on('close',()=>sockets.delete(s))});
  await new Promise(resolve=>server.listen(16443,'127.0.0.1',resolve));
 };
 let later=null;
 if(options.late)later=setTimeout(()=>listen().catch(()=>{}),options.late);else await listen();
 const lease=options.lease||1800,start=performance.now();
 const child=cp.spawn(process.execPath,['-e',program],{stdio:['pipe','pipe','pipe'],detached:true,
  env:{PATH:'/usr/bin:/bin',HOME:'/tmp',LANG:'C.UTF-8'}});
 let output='',stderr='',total=0;
 child.stdout.on('data',b=>{total+=b.length;assert(total<=4096);output+=b});
 child.stderr.on('data',b=>{assert(stderr.length+b.length<=4096);stderr+=b});
 const timer=setTimeout(()=>{try{process.kill(-child.pid,'SIGKILL')}catch(_){}},lease+500);
 const header=Buffer.alloc(21);header.write('BORTUS-API-PROOF\0');header.writeUInt32BE(lease,17);
 child.stdin.end(options.extra?Buffer.concat([header,Buffer.from('extra')]):header);
 const code=await new Promise(resolve=>child.on('exit',resolve));
 clearTimeout(timer);if(later)clearTimeout(later);
 for(const s of sockets)s.destroy();
 if(server)await new Promise(resolve=>server.close(resolve));
 const elapsed=performance.now()-start;
 assert(elapsed<lease+450);assert.equal(stderr,'');
 if(options.ok){assert.equal(code,0);assert.deepEqual(JSON.parse(output),
  {abi:1,ready:true,tls_verified:true,whole_operation_lease_renewed:false,overall_acceptance:false});
  if(options.startup)assert.equal(requests,options.startup+1);
 }else{assert.equal(code,1);assert.equal(output,'')}
 if(options.identity)assert.equal(requests,0);
 if(options.extra)assert.equal(requests,0);
 if(options.mutate){fs.chmodSync('/proof/ca.crt',0o600);fs.writeFileSync('/proof/ca.crt',fs.readFileSync(dir+'/ca.crt'));fs.chmodSync('/proof/ca.crt',0o400)}
 assert.equal(child.exitCode,code);passed++;records.push({case:name,passed:true,requests,child_closed:true});
}
(async()=>{
 await run('verified mTLS200',{ok:true});
 await run('bounded503 startup',{ok:true,startup:2});
 await run('late listener',{ok:true,late:160});
 await run('wrong CA',{identity:'badca'});
 await run('wrong SAN',{identity:'badsan'});
 await run('401 refuses',{status:401});
 await run('redirect refuses',{status:302});
 await run('200 wrong body',{body:'PUBLIC PRIVATE ERROR'});
 await run('encoding refuses',{encoding:'gzip'});
 await run('length bound',{length:5000});
 await run('chunk bound',{body:'x'.repeat(4097)});
 await run('partial quiet absolute expiry',{quiet:true,lease:250});
 await run('503 absolute expiry',{status:503,lease:250});
 await run('extra input refuses',{extra:true});
 await run('credential inode contents drift',{mutate:true,status:503});
 process.stdout.write(JSON.stringify({abi:1,node:process.version,public_controls:passed,records,
  operator_material_read:false,live_api_recovery:false})+'\n');
})().catch(e=>{process.stderr.write('PUBLIC READINESS FIXTURE FAILURE '+e.name+'\n');process.exitCode=1});
