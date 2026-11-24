'use strict';
// Disposable public fixtures only; no operator/runtime credentials or cluster IO.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),crypto=require('node:crypto'),os=require('node:os');
const path=require('node:path'),http=require('node:http'),https=require('node:https');
const cp=require('node:child_process'),{Readable,PassThrough}=require('node:stream');
const m=require('../bortus-api-secret-proof.cjs');
const source=path.resolve(__dirname,'../bortus-api-secret-proof.cjs');
const ID='00000000-0000-0000-0000-000000000001';
const key=Buffer.alloc(32,7),iv=Buffer.alloc(16,3);
const encoded=b=>b.toString('base64');
function variable(n){n=BigInt(n);const out=[];do{let b=Number(n&127n);n>>=7n;out.push(b|(n?128:0));}while(n);return Buffer.from(out);}
function field(id,v){return Buffer.concat([variable(id*8+2),variable(v.length),v]);}
function integer(id,n){return Buffer.concat([variable(id*8),variable(n)]);}
const str=(id,v)=>field(id,Buffer.from(v));
function proto({name='public-secret',namespace='public',type='Opaque',immutable=null,data=new Map([['empty',Buffer.alloc(0)],['__proto__',Buffer.from([0,255,128])]])}={}){
 const meta=Buffer.concat([str(1,name),str(3,namespace),str(5,ID)]);
 const secret=Buffer.concat([field(1,meta),...Array.from(data,([k,v])=>field(2,Buffer.concat([str(1,k),field(2,v)]))),str(3,type),...(immutable===null?[]:[integer(5,immutable?1:0)])]);
 return Buffer.concat([Buffer.from([107,56,115,0]),field(1,Buffer.concat([str(1,'v1'),str(2,'Secret')])),field(2,secret),str(3,''),str(4,'')]);
}
function encrypted(plain){const e=crypto.createCipheriv('aes-256-cbc',key,iv);return Buffer.concat([Buffer.from('k8s:enc:aescbc:v1:public:'),iv,e.update(plain),e.final()]);}
function encryption(){return Buffer.from(JSON.stringify({apiVersion:'apiserver.config.k8s.io/v1',kind:'EncryptionConfiguration',resources:[{resources:['secrets'],providers:[{aescbc:{keys:[{name:'public',secret:encoded(key)}]}},{identity:{}}]}]}));}
function header(ms=3000){const n=Buffer.alloc(4);n.writeUInt32BE(ms);return Buffer.concat([m.MAGIC,n]);}
function frame(files,ms=3000){return Buffer.concat([header(ms),...files.flatMap((v,i)=>{const h=Buffer.alloc(5);h[0]=i+1;h.writeUInt32BE(v.length,1);return[h,v];}),Buffer.from([0])]);}
function input(raw,step=13){return Readable.from(Array.from({length:Math.ceil(raw.length/step)},(_,i)=>raw.subarray(i*step,(i+1)*step)));}
function folder(){return fs.mkdtempSync('/proof/fixture-');}
function write(root,name,body){fs.writeFileSync(path.join(root,name),body,{mode:0o400,flag:'wx'});}
function registry(value=encrypted(proto()),name='public-secret'){return {header:{revision:'10'},count:'1',kvs:[{key:encoded(Buffer.from('/registry/secrets/public/'+name)),value:encoded(value)}]};}
function secret(){return {metadata:{name:'public-secret',namespace:'public',uid:ID},type:'Opaque',data:{empty:'',__proto__:undefined}};}
function apiItem(){const out=JSON.parse('{"metadata":{"name":"public-secret","namespace":"public","uid":"'+ID+'"},"type":"Opaque","data":{"empty":"","__proto__":"AP+A"}}');return out;}
function reject(fn){assert.throws(fn);}

test('exact approved Node22 binary/runtime and UID; no ambient fixture credentials',()=>{
 assert.equal(process.version,'v22.23.3');assert.equal(process.getuid(),1000);
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(process.execPath)).digest('hex'),'fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48');
 assert.equal(fs.statfsSync('/proof').type,0x01021994);
});
test('actual CLI fixed nine slots,400/tmpfs, no values in stdout or argv',async()=>{
 const files=m.FILES.map((n,i)=>Buffer.from('PUBLIC FIXTURE '+i));
 const child=cp.spawn(process.execPath,[source,'--bundle'],{stdio:['pipe','pipe','ignore'],detached:true});
 let output='';child.stdout.on('data',b=>output+=b);child.stdin.end(frame(files));
 const status=await new Promise(resolve=>child.on('close',resolve));assert.equal(status,0);
 const receipt=JSON.parse(output);assert.equal(receipt.files,9);assert.equal(receipt.overall_acceptance,false);
 for(let i=0;i<m.FILES.length;i++){const p='/proof/'+m.FILES[i];assert.deepEqual(fs.readFileSync(p),files[i]);assert.equal(fs.statSync(p).mode&511,256);fs.unlinkSync(p);}
 assert.equal(fs.readdirSync('/proof').length,0);assert(!output.includes('PUBLIC FIXTURE'));
 assert.throws(()=>process.kill(child.pid,0));
});
test('fragmented writer full frame and EOF',async()=>{
 const dir=folder(),files=m.FILES.map((n,i)=>Buffer.alloc(i+1,i));
 const out=await m.writer(input(frame(files),1),new m.Clock(3000),dir);assert.equal(out.complete,true);
 for(let i=0;i<9;i++)assert.deepEqual(fs.readFileSync(path.join(dir,m.FILES[i])),files[i]);
});
test('malformed magic/reordered/oversized header refuses before file creation',async()=>{
 const files=m.FILES.map(()=>Buffer.from('PUBLIC'));
 for(const edit of ['magic','order','size']){
  const dir=folder(),raw=frame(files);if(edit==='magic')raw[0]^=1;
  if(edit==='order')raw[m.MAGIC.length+4]=2;
  if(edit==='size')raw.writeUInt32BE(1048577,m.MAGIC.length+5);
  await assert.rejects(m.writer(input(raw),new m.Clock(3000),dir));assert.equal(fs.readdirSync(dir).length,0);
 }
});
test('truncated body/missing EOF/duplicate end/extra bytes refuse without replay',async()=>{
 const raw=frame(m.FILES.map(()=>Buffer.from('PUBLIC')));
 for(const bad of [raw.subarray(0,raw.length-1),raw.subarray(0,45),Buffer.concat([raw,Buffer.from([0])]),Buffer.concat([raw,Buffer.from([1])])]){
  const dir=folder();await assert.rejects(m.writer(input(bad,1),new m.Clock(3000),dir));
  await assert.rejects(m.writer(input(raw),new m.Clock(3000),dir));
 }
});
test('quiet input header narrowing retains original deadline and owned FD closure',async()=>{
 const dir=folder(),before=fs.readdirSync('/proc/self/fd').length,stream=new PassThrough(),start=Date.now();
 stream.write(header(35));await assert.rejects(m.writer(stream,new m.Clock(1000),dir));
 assert(Date.now()-start<250);assert.equal(fs.readdirSync('/proc/self/fd').length,before);
 assert.equal(fs.readdirSync(dir).length,0);
});
test('exclusive root/file/symlink/owner-mode and non-memory refusals',async()=>{
 const dir=folder();write(dir,'ca.crt',Buffer.from('PUBLIC'));
 await assert.rejects(m.writer(input(frame(m.FILES.map(()=>Buffer.from('PUBLIC')))),new m.Clock(3000),dir));
 const bad=folder();fs.chmodSync(bad,0o755);reject(()=>new m.MemoryRoot(bad));
 const regular=fs.mkdtempSync('/tmp/public-regular-');fs.chmodSync(regular,0o700);
 // /tmp is tmpfs in the qualified container; use read-only source as non-tmpfs.
 reject(()=>new m.MemoryRoot('/src/scripts/migration'));
 const link=folder();fs.symlinkSync(dir,path.join(link,'link'));reject(()=>new m.MemoryRoot(path.join(link,'link')));
});
test('file pin substitution and independent descriptor closure',()=>{
 const dir=folder();write(dir,'ca.crt',Buffer.from('PUBLIC'));
 const before=fs.readdirSync('/proc/self/fd').length,root=new m.MemoryRoot(dir);root.read('ca.crt');
 const replacement=path.join(dir,'new');fs.writeFileSync(replacement,'PUBLIC',{mode:0o400});fs.renameSync(replacement,path.join(dir,'ca.crt'));
 reject(()=>root.check());root.close();assert.equal(fs.readdirSync('/proc/self/fd').length,before);
});
test('strict JSON duplicate keys/prototype map/depth/UTF8/trailing syntax',()=>{
 const clock=new m.Clock();reject(()=>m.json(Buffer.from('{"x":1,"x":2}'),clock));
 const p=m.json(Buffer.from('{"__proto__":"PUBLIC"}'),clock);assert.equal(Object.getPrototypeOf(p),null);assert.equal(p.__proto__,'PUBLIC');
 for(const raw of [Buffer.from([255]),Buffer.from('{}\u00a0'),Buffer.from('{} true'),Buffer.from('['.repeat(34)+']'.repeat(34))])reject(()=>m.json(raw,clock));
});
test('canonical base64 preserves empty and binary while malformed encodings refuse',()=>{
 assert.deepEqual(m.base64('',1),Buffer.alloc(0));assert.deepEqual(m.base64('AP+A',3),Buffer.from([0,255,128]));
 for(const raw of ['AA','AB==','AA==\n','AAAA='])reject(()=>m.base64(raw,20));
});
test('real built-in CBC+strict PKCS7 and protobuf data identity map',()=>{
 const clock=new m.Clock(),keys=m.configKeys(encryption(),clock),raw=m.decrypt(encrypted(proto()),keys,clock);
 const result=m.secretProto(raw,clock);assert.equal(result.uid,ID);assert.equal(result.immutable,null);
 assert.deepEqual(result.data.get('__proto__'),Buffer.from([0,255,128]));assert.equal(result.data.get('empty').length,0);
});
test('CBC prefix/key/malformed IV/truncation/nonASCII name/invalid padding refuses',()=>{
 const c=new m.Clock(),keys=m.configKeys(encryption(),c),raw=encrypted(proto());
 const unknown=Buffer.concat([Buffer.from('k8s:enc:aescbc:v1:missing:'),raw.subarray(raw.indexOf(iv))]);
 const broken=Buffer.from(raw);broken[broken.length-17]^=16;
 for(const bad of [raw.subarray(1),raw.subarray(0,raw.length-1),unknown,broken,Buffer.concat([Buffer.from('k8s:enc:aescbc:v1:'),Buffer.from([0xf0]),Buffer.from(':')])])reject(()=>m.decrypt(bad,keys,c));
});
test('original encryption schema/key uniqueness/provider/length refusals',()=>{
 for(const kind of ['duplicate','unknown','short','empty']){
  const v=JSON.parse(encryption());const p=v.resources[0].providers[0];
  if(kind==='duplicate')p.aescbc.keys.push({...p.aescbc.keys[0]});
  if(kind==='unknown')v.resources[0].providers[0]={kms:{}};
  if(kind==='short')p.aescbc.keys[0].secret=encoded(Buffer.alloc(16));
  if(kind==='empty')p.aescbc.keys=[];
  reject(()=>m.configKeys(Buffer.from(JSON.stringify(v)),new m.Clock()));
 }
});
test('protobuf nil/false/true immutable and empty data remain distinct',()=>{
 for(const immutable of [null,false,true]){
  const result=m.secretProto(proto({immutable,data:new Map()}),new m.Clock());assert.equal(result.immutable,immutable);assert.equal(result.data.size,0);
 }
});
test('protobuf duplicate singleton/unknown/groups/truncated/overflow varint refuse',()=>{
 const good=proto(),c=new m.Clock();
 for(const bad of [Buffer.concat([good,str(3,'')]),Buffer.concat([good,integer(20,1)]),Buffer.concat([good,Buffer.from([0x1b])]),good.subarray(0,good.length-1),Buffer.concat([good,Buffer.alloc(11,128)])])reject(()=>m.secretProto(bad,c));
});
test('protobuf duplicate data key/malformed UTF8/key syntax and unsupported type refuse',()=>{
 const entry=field(2,Buffer.concat([str(1,'same'),field(2,Buffer.from('PUBLIC'))]));
 const meta=field(1,Buffer.concat([str(1,'public-secret'),str(3,'public'),str(5,ID)]));
 const wrap=raw=>Buffer.concat([Buffer.from([107,56,115,0]),field(1,Buffer.concat([str(1,'v1'),str(2,'Secret')])),field(2,raw)]);
 reject(()=>m.secretProto(wrap(Buffer.concat([meta,entry,entry,str(3,'Opaque')])),new m.Clock()));
 reject(()=>m.secretProto(proto({name:'../outside'}),new m.Clock()));
 reject(()=>m.secretProto(wrap(Buffer.concat([meta,field(3,Buffer.from([255]))])),new m.Clock()));
 const wrong=Buffer.from(proto());wrong[wrong.indexOf(Buffer.from('Secret'))]=65;reject(()=>m.secretProto(wrong,new m.Clock()));
});
test('typed-list only omitted headers and explicit immutable types',()=>{
 assert.equal(m.apiSecret(apiItem(),true).data.size,2);reject(()=>m.apiSecret(apiItem()));
 for(const changes of [{kind:null},{apiVersion:'v2'},{kind:'Pod'},{immutable:null},{immutable:0}])reject(()=>m.apiSecret({...apiItem(),...changes},true));
});
test('full selected map oracle refuses type/UID/immutable/key/value/inventory drift',()=>{
 const c=new m.Clock(),p=m.secretProto(proto(),c),left=new Map([['key',p]]);
 const normal=m.apiSecret(apiItem(),true);m.compare(left,new Map([['key',normal]]),c);
 for(const field of ['uid','type','immutable','key','value','inventory']){
  const item=m.apiSecret(apiItem(),true);const right=new Map([['key',item]]);
  if(field==='uid')item.uid='replacement';if(field==='type')item.type='other';if(field==='immutable')item.immutable=false;
  if(field==='key')item.data.delete('empty');if(field==='value')item.data.set('empty',Buffer.from([0]));if(field==='inventory')right.clear();
  reject(()=>m.compare(left,right,c));
 }
});
test('complete raw registry rejects duplicate/count/more/key/header drift',()=>{
 const c=new m.Clock();assert.equal(m.registry(registry(),c).result.size,1);
 for(const field of ['duplicate','count','more','key','revision']){
  const v=registry();if(field==='duplicate'){v.kvs.push({...v.kvs[0]});v.count='2';}if(field==='count')v.count='2';
  if(field==='more')v.more=true;if(field==='key')v.kvs[0].key=encoded(Buffer.from('/not/secrets/x'));if(field==='revision')v.header.revision='opaque';
  reject(()=>m.registry(v,c));
 }
 reject(()=>m.sameCipher(new Map([['k',Buffer.from('a')]]),new Map([['k',Buffer.from('b')]])));
});
test('original deadline cannot renew or accept expiry',async()=>{
 const c=new m.Clock(25),d=c.deadline;c.narrow(300000);assert.equal(c.deadline,d);
 await new Promise(resolve=>setTimeout(resolve,30));reject(()=>c.left());
});

let certificates=null;
function certs(){
 if(certificates)return certificates;
 const dir=fs.mkdtempSync('/tmp/public-tls-');const create=(name,ip)=>{
  const key=path.join(dir,name+'.key'),cert=path.join(dir,name+'.crt');
  const out=cp.spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=PUBLIC FIXTURE',
   '-addext','subjectAltName=IP:'+ip,'-keyout',key,'-out',cert,'-days','1'],{stdio:'ignore',timeout:10000});assert.equal(out.status,0);
  return {key:fs.readFileSync(key),cert:fs.readFileSync(cert)};
 };certificates={good:create('good','192.168.0.4'),wrong:create('wrong','10.0.0.1')};return certificates;
}
async function serve({change=false,kind='good',pageDrift=false,malformedHeaders=false}={}){
 const c=certs()[kind],counts={etcd:0,api:0};
 const e=http.createServer((req,res)=>{let body='';req.on('data',b=>body+=b);req.on('end',()=>{
  assert.equal(req.url,'/v3/kv/range');assert.equal(req.method,'POST');
  const data=JSON.parse(body);assert.equal(Buffer.from(data.key,'base64').toString(),'/registry/secrets/');
  counts.etcd++;const reply=registry(change&&counts.etcd===2?encrypted(proto({type:'CHANGED'})):encrypted(proto()));
  const raw=JSON.stringify(reply);res.writeHead(200,{'Content-Type':'application/json','Content-Length':Buffer.byteLength(raw)});res.end(raw);
 });});
 const a=https.createServer({key:c.key,cert:c.cert,ca:c.cert,requestCert:true,rejectUnauthorized:true},(req,res)=>{
  counts.api++;assert(req.url.startsWith('/api/v1/secrets?'));assert.equal(req.method,'GET');
  const item=apiItem();if(malformedHeaders)item.kind=null;
  const reply={apiVersion:'v1',kind:'SecretList',metadata:{resourceVersion:pageDrift&&counts.api===2?'changed':'opaque',continue:pageDrift&&counts.api===1?'next':''},items:pageDrift&&counts.api===1?[]:[item]};
  const raw=JSON.stringify(reply);res.writeHead(200,{'Content-Type':'application/json','Content-Length':Buffer.byteLength(raw)});res.end(raw);
 });
 a.on('tlsClientError',()=>{});
 await new Promise((resolve,reject)=>{e.once('error',reject);e.listen(32379,'127.0.0.1',resolve);});
 try{await new Promise((resolve,reject)=>{a.once('error',reject);a.listen(16443,'127.0.0.1',resolve);});}
 catch(error){e.closeAllConnections();await new Promise(r=>e.close(r));throw error;}
 return {counts,c,close:async()=>{e.closeAllConnections();a.closeAllConnections();await Promise.all([new Promise(r=>e.close(r)),new Promise(r=>a.close(r))]);}};
}
function proofRoot(c){const dir=folder();write(dir,'encryption-config.json',encryption());write(dir,'ca.crt',c.cert);write(dir,'admin.crt',c.cert);write(dir,'admin.key',c.key);return dir;}
test('actual loopback mTLS API/HTTP full-map oracle; fixed output and typed headers',async()=>{
 const servers=await serve();const dir=proofRoot(servers.c);const before=fs.readdirSync('/proc/self/fd').length;
 try{const result=await m.oracle(new m.Clock(5000),dir);assert.equal(result.secret_count,1);assert.equal(result.independent_aescbc_protobuf_api_map_equal,true);
  assert.equal(result.overall_acceptance,false);assert(!JSON.stringify(result).includes('public-secret'));assert.deepEqual(servers.counts,{etcd:2,api:1});}
 finally{await servers.close();}
 assert(fs.readdirSync('/proc/self/fd').length<=before);
});
test('actual TLS wrong SAN and wrong CA refuse, no insecure fallback',async()=>{
 for(const fault of ['san','ca']){
  const servers=await serve({kind:fault==='san'?'wrong':'good'});
  try{
   if(fault==='san')await assert.rejects(m.oracle(new m.Clock(3000),proofRoot(servers.c)));
   else await assert.rejects(m.request(https,'/api/v1/secrets?limit=200',null,{ca:certs().wrong.cert,cert:servers.c.cert,key:servers.c.key},new m.Clock(3000),{received:0}));
   assert.equal(servers.counts.api,0);
  }finally{await servers.close();}
 }
});
test('real ciphertext before/after drift refuses equality',async()=>{
 const servers=await serve({change:true});try{await assert.rejects(m.oracle(new m.Clock(5000),proofRoot(servers.c)));assert.equal(servers.counts.etcd,2);}
 finally{await servers.close();}
});
test('real complete-page RV or explicit typed-header drift refuses',async()=>{
 for(const field of ['pageDrift','malformedHeaders']){
  const servers=await serve({[field]:true});try{await assert.rejects(m.oracle(new m.Clock(5000),proofRoot(servers.c)));}
  finally{await servers.close();}
 }
});
test('actual partial HTTP response expires under original lease and closes owned socket',async()=>{
 let open=0;const sockets=new Set();
 const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'application/json'});res.write('{');});
 server.on('connection',socket=>{open++;sockets.add(socket);socket.on('close',()=>{open--;sockets.delete(socket);});});
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(32379,'127.0.0.1',resolve);});
 const started=Date.now();
 try{
  await assert.rejects(m.request(http,'/v3/kv/range',Buffer.from('{}'),null,new m.Clock(40),{received:0}));
  const until=Date.now()+200;while(open&&Date.now()<until)await new Promise(r=>setTimeout(r,5));
  assert.equal(open,0);assert(Date.now()-started<250);
 }finally{for(const socket of sockets)socket.destroy();await new Promise(resolve=>server.close(resolve));}
});
