'use strict';
// Kubernetes v1.37.1 only. Fixed isolated endpoints; no production authority.
const fs = require('node:fs');
const crypto = require('node:crypto');
const http = require('node:http');
const https = require('node:https');
const tls = require('node:tls');
const { TextDecoder } = require('node:util');
const MAGIC = Buffer.from('BORTUS-API-PROOF\0', 'ascii');
const ROOT = '/proof';
const FILES = ['encryption-config.json', 'ca.crt', 'apiserver.crt', 'apiserver.key',
  'sa.key', 'sa.pub', 'admin.crt', 'admin.key', 'snapshot.db'];
const MAX_FILE = 1024 * 1024, MAX_SNAPSHOT = 512 * MAX_FILE;
const MAX_REPLY = 8 * MAX_FILE, MAX_TOTAL = 64 * MAX_FILE, MAX_ITEMS = 10000;
const UTF8 = new TextDecoder('utf-8', { fatal: true });
const own = (o, k) => Object.hasOwn(o, k);
function need(ok) { if (!ok) throw new Error('API proof refused'); }
function keys(o, names) {
  need(o !== null && typeof o === 'object' && !Array.isArray(o) &&
    Object.keys(o).length === names.length && names.every(n => own(o, n)));
}
class Clock {
  constructor(ms = 300000) {
    need(Number.isInteger(ms) && ms > 0 && ms <= 300000);
    this.start = process.hrtime.bigint(); this.deadline = this.start + BigInt(ms) * 1000000n;
  }
  narrow(ms) {
    need(Number.isInteger(ms) && ms > 0 && ms <= 300000);
    const next = this.start + BigInt(ms) * 1000000n;
    if (next < this.deadline) this.deadline = next;
    this.left();
  }
  left() {
    const n = this.deadline - process.hrtime.bigint(); need(n > 0n);
    return Math.max(1, Number(n / 1000000n));
  }
}

// Strict JSON, including duplicate/prototype names. No eval or normal-object map.
function json(raw, clock) {
  need(Buffer.isBuffer(raw) && raw.length <= MAX_TOTAL);
  const text = UTF8.decode(raw); let p = 0, nodes = 0;
  const ws = () => { while (p < text.length && /[\x20\x09\x0a\x0d]/.test(text[p])) p++; };
  function string() {
    need(text[p] === '"'); const start = p++;
    while (p < text.length) {
      const c = text[p++];
      if (c === '"') { const v = JSON.parse(text.slice(start, p)); need(v.length <= MAX_TOTAL); return v; }
      if (c === '\\') { need(p < text.length); p++; }
      else need(c.charCodeAt(0) >= 32);
    }
    need(false);
  }
  function value(depth) {
    clock.left(); need(++nodes <= 200000 && depth <= 32); ws();
    const c = text[p];
    if (c === '"') return string();
    if (c === '{') {
      p++; ws(); const out = Object.create(null);
      if (text[p] === '}') { p++; return out; }
      for (;;) {
        ws(); const k = string(); need(!own(out, k)); ws(); need(text[p++] === ':'); out[k] = value(depth + 1); ws();
        const end = text[p++]; if (end === '}') return out; need(end === ',');
      }
    }
    if (c === '[') {
      p++; ws(); const out = []; if (text[p] === ']') { p++; return out; }
      for (;;) { need(out.length <= MAX_ITEMS * 4); out.push(value(depth + 1)); ws();
        const end = text[p++]; if (end === ']') return out; need(end === ','); }
    }
    for (const [token, result] of [['true', true], ['false', false], ['null', null]]) {
      if (text.startsWith(token, p)) { p += token.length; return result; }
    }
    const n = text.slice(p).match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/);
    need(n); p += n[0].length; const result = Number(n[0]); need(Number.isFinite(result)); return result;
  }
  const result = value(0); ws(); need(p === text.length); clock.left(); return result;
}
function base64(value, maximum) {
  need(typeof value === 'string' && value.length <= Math.ceil(maximum / 3) * 4 &&
    /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value));
  const bytes = Buffer.from(value, 'base64'); need(bytes.length <= maximum && bytes.toString('base64') === value); return bytes;
}
function decimal(v) { need((typeof v === 'string' && /^[0-9]{1,20}$/.test(v)) ||
  (typeof v === 'number' && Number.isSafeInteger(v) && v >= 0)); return BigInt(v); }
function dns(v, maximum = 253) { need(typeof v === 'string' && v.length > 0 && v.length <= maximum &&
  v.split('.').every(s => /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(s) && s.length <= 63)); return v; }
function uid(v) { need(typeof v === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(v)); return v; }
function configKeys(raw, clock) {
  const config = json(raw, clock); keys(config, ['apiVersion', 'kind', 'resources']);
  need(config.apiVersion === 'apiserver.config.k8s.io/v1' && config.kind === 'EncryptionConfiguration' &&
    Array.isArray(config.resources) && config.resources.length > 0 && config.resources.length <= 32);
  const out = new Map(); let matches = 0;
  for (const resource of config.resources) {
    keys(resource, ['resources', 'providers']); need(Array.isArray(resource.resources) && resource.resources.length > 0 &&
      resource.resources.every(r => typeof r === 'string') && Array.isArray(resource.providers) && resource.providers.length > 0);
    const secrets = resource.resources.includes('secrets'); if (secrets) need(++matches === 1);
    for (const provider of resource.providers) {
      if (own(provider, 'identity')) { keys(provider, ['identity']); keys(provider.identity, []); continue; }
      keys(provider, ['aescbc']); keys(provider.aescbc, ['keys']);
      need(Array.isArray(provider.aescbc.keys) && provider.aescbc.keys.length > 0 && provider.aescbc.keys.length <= 16);
      for (const entry of provider.aescbc.keys) {
        keys(entry, ['name', 'secret']); need(typeof entry.name === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(entry.name));
        const secret = base64(entry.secret, 32); need(secret.length === 32);
        if (secrets) { need(!out.has(entry.name)); out.set(entry.name, secret); } else secret.fill(0);
      }
    }
  }
  need(matches === 1 && out.size > 0); return out;
}

// Closed v1.37.1 protobuf wire reader: unknown fields/groups, duplicate singleton,
// overflow/truncation/noncanonical varints and invalid UTF-8 refuse.
function fields(bytes, schema, repeated, clock) {
  need(Buffer.isBuffer(bytes) && bytes.length <= 2 * MAX_FILE); let p = 0, count = 0;
  function variable() {
    let n = 0n, shift = 0n;
    for (let i = 0; i < 10; i++) {
      need(p < bytes.length); const b = bytes[p++];
      need(i < 9 || b <= 1); n |= BigInt(b & 127) << shift;
      if (!(b & 128)) { need(i === 0 || b !== 0); return n; } shift += 7n;
    }
    need(false);
  }
  const out = new Map();
  while (p < bytes.length) {
    clock.left(); need(++count <= 30000); const tag = variable();
    need(tag <= 0xffffffffn); const field = Number(tag >> 3n), wire = Number(tag & 7n);
    need(field > 0 && own(schema, field) && wire === schema[field] && (!out.has(field) || repeated.has(field)));
    let v;
    if (wire === 0) v = variable();
    else { const length = variable(); need(length <= BigInt(bytes.length - p)); const size = Number(length);
      v = bytes.subarray(p, p + size); p += size; }
    if (!out.has(field)) out.set(field, []); out.get(field).push(v);
  }
  return out;
}
const one = (map, id, fallback) => map.has(id) ? map.get(id)[0] : fallback;
const text = bytes => { need(Buffer.isBuffer(bytes)); return UTF8.decode(bytes); };
function secretProto(bytes, clock) {
  need(bytes.length > 4 && bytes.subarray(0, 4).equals(Buffer.from([107, 56, 115, 0])));
  const outer = fields(bytes.subarray(4), {1:2,2:2,3:2,4:2}, new Set(), clock);
  const type = fields(one(outer, 1), {1:2,2:2}, new Set(), clock);
  need(text(one(type, 1)) === 'v1' && text(one(type, 2)) === 'Secret' &&
    text(one(outer, 3, Buffer.alloc(0))) === '' && text(one(outer, 4, Buffer.alloc(0))) === '');
  const secret = fields(one(outer, 2), {1:2,2:2,3:2,5:0}, new Set([2]), clock);
  const meta = fields(one(secret, 1), {1:2,2:2,3:2,4:2,5:2,6:2,7:0,8:2,9:2,10:0,11:2,12:2,13:2,14:2,17:2},
    new Set([11,12,13,14,17]), clock);
  const name = dns(text(one(meta, 1))), namespace = dns(text(one(meta, 3)), 63), identity = uid(text(one(meta, 5)));
  const kind = text(one(secret, 3)); need(kind.length > 0 && kind.length <= 256);
  const immutable = one(secret, 5, null); need(immutable === null || immutable === 0n || immutable === 1n);
  const data = new Map(); let total = 0;
  for (const entry of secret.get(2) || []) {
    const item = fields(entry, {1:2,2:2}, new Set(), clock); const key = text(one(item, 1));
    need(/^[A-Za-z0-9._-]{1,253}$/.test(key) && !data.has(key));
    const value = one(item, 2, Buffer.alloc(0)); total += value.length; need(total <= MAX_FILE); data.set(key, value);
  }
  return {name, namespace, uid:identity, type:kind, immutable:immutable === null ? null : immutable === 1n, data};
}
function decrypt(value, encryption, clock) {
  need(Buffer.isBuffer(value) && value.length <= 2 * MAX_FILE); clock.left();
  const prefix = Buffer.from('k8s:enc:aescbc:v1:'); need(value.subarray(0, prefix.length).equals(prefix));
  const end = value.indexOf(58, prefix.length); need(end > prefix.length && end - prefix.length <= 128);
  const name = text(value.subarray(prefix.length, end)); need(/^[A-Za-z0-9_-]+$/.test(name) && encryption.has(name));
  const body = value.subarray(end + 1); need(body.length >= 32 && (body.length - 16) % 16 === 0);
  const decipher = crypto.createDecipheriv('aes-256-cbc', encryption.get(name), body.subarray(0,16));
  decipher.setAutoPadding(false); const plain = Buffer.concat([decipher.update(body.subarray(16)), decipher.final()]);
  const padding = plain[plain.length - 1]; need(padding >= 1 && padding <= 16 && padding <= plain.length);
  for (let i = plain.length - padding; i < plain.length; i++) need(plain[i] === padding);
  clock.left(); return plain.subarray(0, plain.length - padding);
}
function registry(reply, clock) {
  need(reply !== null && typeof reply === 'object' && !Array.isArray(reply) &&
    typeof reply.header === 'object' && reply.header !== null && !Array.isArray(reply.header));
  const revision = decimal(reply.header.revision); need(revision > 0n);
  const count = decimal(reply.count); need(count <= BigInt(MAX_ITEMS) && Array.isArray(reply.kvs) &&
    BigInt(reply.kvs.length) === count && (!own(reply, 'more') || reply.more === false));
  const result = new Map(); let size = 0;
  for (const item of reply.kvs) {
    clock.left(); need(item !== null && typeof item === 'object');
    const key = text(base64(item.key,1024)); need(/^\/registry\/secrets\/[^/]+\/[^/]+$/.test(key) && !result.has(key));
    const value = base64(item.value,2 * MAX_FILE); need(value.length > 0); size += value.length; need(size <= MAX_TOTAL);
    result.set(key, value);
  }
  return {revision, result};
}
function sameCipher(a, b) {
  need(a.size === b.size);
  for (const [key, value] of a) need(b.has(key) && value.equals(b.get(key)));
}
function apiSecret(obj, typed = false) {
  need(typeof typed === 'boolean');
  need(obj !== null && typeof obj === 'object' &&
    (obj.apiVersion === 'v1' || typed && !own(obj,'apiVersion')) &&
    (obj.kind === 'Secret' || typed && !own(obj,'kind')) &&
    obj.metadata !== null && typeof obj.metadata === 'object' && !Array.isArray(obj.metadata));
  const name = dns(obj.metadata.name), namespace = dns(obj.metadata.namespace,63), identity = uid(obj.metadata.uid);
  need(typeof obj.type === 'string' && obj.type.length > 0 && obj.type.length <= 256 && !own(obj,'stringData'));
  need(!own(obj,'immutable') || typeof obj.immutable === 'boolean');
  const immutable = own(obj,'immutable') ? obj.immutable : null;
  const input = own(obj,'data') ? obj.data : Object.create(null);
  need(input !== null && typeof input === 'object' && !Array.isArray(input)); const data = new Map(); let size = 0;
  for (const key of Object.keys(input)) {
    need(/^[A-Za-z0-9._-]{1,253}$/.test(key)); const value = base64(input[key],MAX_FILE); size += value.length; need(size <= MAX_FILE); data.set(key,value);
  }
  return {name,namespace,uid:identity,type:obj.type,immutable,data};
}
function compare(expected, actual, clock) {
  need(expected.size === actual.size);
  for (const [key, left] of expected) {
    clock.left(); need(actual.has(key)); const right = actual.get(key);
    need(['name','namespace','uid','type','immutable'].every(k => left[k] === right[k])); sameCipher(left.data,right.data);
  }
}

function fingerprint(i) { return ['dev','ino','uid','mode','nlink','size','mtimeNs','ctimeNs'].map(k => i[k].toString()).join(':'); }
class MemoryRoot {
  constructor(path = ROOT, fresh = false) {
    this.pins = [];
    this.path = path; this.fd = fs.openSync(path,fs.constants.O_RDONLY | fs.constants.O_DIRECTORY | fs.constants.O_NOFOLLOW);
    try {
      const i = fs.fstatSync(this.fd,{bigint:true});
      need(i.isDirectory() && i.uid === BigInt(process.getuid()) && (i.mode & 511n) === 448n);
      this.identity = ['dev','ino','uid','mode'].map(k => i[k].toString()).join(':');
      need(fs.statfsSync('/proc/self/fd/'+this.fd).type === 0x01021994);
      if (fresh) need(fs.readdirSync('/proc/self/fd/'+this.fd).length === 0);
      this.check();
    } catch (_) { fs.closeSync(this.fd); this.fd = null; throw new Error('API proof refused'); }
  }
  check() {
    for (const i of [fs.fstatSync(this.fd,{bigint:true}),fs.lstatSync(this.path,{bigint:true})])
      need(i.isDirectory() && ['dev','ino','uid','mode'].map(k => i[k].toString()).join(':') === this.identity);
    need(fs.statfsSync('/proc/self/fd/'+this.fd).type === 0x01021994);
    for(const pin of this.pins)need(fingerprint(fs.fstatSync(pin.fd,{bigint:true}))===pin.identity &&
      fingerprint(fs.lstatSync(pin.path,{bigint:true}))===pin.identity);
  }
  file(name) { need(FILES.includes(name)); this.check(); return '/proc/self/fd/'+this.fd+'/'+name; }
  read(name) {
    const path = this.file(name); const fd = fs.openSync(path,fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
    let retained = false;
    try {
      const i = fs.fstatSync(fd,{bigint:true}); need(i.isFile() && i.uid === BigInt(process.getuid()) &&
        i.nlink === 1n && (i.mode & 511n) === 256n && i.size > 0n && i.size <= BigInt(MAX_FILE));
      const raw = fs.readFileSync(fd); need(raw.length === Number(i.size) &&
        fingerprint(i) === fingerprint(fs.fstatSync(fd,{bigint:true})) &&
        fingerprint(i) === fingerprint(fs.lstatSync(path,{bigint:true}))); this.check();
      this.pins.push({fd,path,identity:fingerprint(i)});retained=true;return raw;
    } finally { if(!retained)fs.closeSync(fd); }
  }
  close() {
    let failed=false;
    for(const fd of [...this.pins.map(p=>p.fd),this.fd])if(fd!==null)try{fs.closeSync(fd);}catch(_){failed=true;}
    this.fd=null;this.pins=[];need(!failed);
  }
}
async function writer(input, clock, rootPath = ROOT) {
  const root = new MemoryRoot(rootPath, true); let file = null, pending = Buffer.alloc(0), position = -1, left = 0, total = 0;
  const created = []; let done = false;
  let timer = setTimeout(() => input.destroy(new Error('API proof refused')),clock.left());
  try {
    for await (const incoming of input) {
      clock.left(); need(Buffer.isBuffer(incoming) && incoming.length <= 65536);
      pending = Buffer.concat([pending,incoming]); need(pending.length <= 65536 + 64);
      for (;;) {
        clock.left(); root.check();
        if (position === -1) {
          if (pending.length < MAGIC.length + 4) break;
          need(pending.subarray(0,MAGIC.length).equals(MAGIC));clock.narrow(pending.readUInt32BE(MAGIC.length));
          clearTimeout(timer);timer=setTimeout(()=>input.destroy(new Error('API proof refused')),clock.left());
          pending=pending.subarray(MAGIC.length+4); position=0; continue;
        }
        if(done){need(pending.length===0);break;}
        if (position === FILES.length) {
          if (!pending.length) break;
          need(pending.length === 1 && pending[0] === 0); pending=Buffer.alloc(0);done=true;break;
        }
        need(!done);
        if (file === null) {
          if (pending.length < 5) break;
          need(pending[0] === position+1); left=pending.readUInt32BE(1);
          need(left > 0 && left <= (position === 8 ? MAX_SNAPSHOT : MAX_FILE)); pending=pending.subarray(5);
          file=fs.openSync(root.file(FILES[position]),fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_WRONLY | fs.constants.O_NOFOLLOW,0o400);
          const i=fs.fstatSync(file,{bigint:true});created.push({name:FILES[position],inode:i.ino,dev:i.dev,size:left});
          need(i.uid===BigInt(process.getuid()) && i.nlink===1n && (i.mode&511n)===256n);
        }
        if (!pending.length) break;
        const n=Math.min(left,pending.length);need(fs.writeSync(file,pending,0,n)===n);left-=n;total+=n;pending=pending.subarray(n);
        need(total <= MAX_SNAPSHOT + 8*MAX_FILE);
        if (!left) {
          fs.fsyncSync(file);const i=fs.fstatSync(file,{bigint:true}),last=created[created.length-1];
          need(i.ino===last.inode && i.dev===last.dev && i.nlink===1n &&
            i.uid===BigInt(process.getuid()) && (i.mode&511n)===256n && i.size===BigInt(last.size) &&
            fingerprint(i)===fingerprint(fs.lstatSync(root.file(last.name),{bigint:true})));
          fs.closeSync(file);file=null;position++;
        }
      }
      if (done) need(pending.length===0);
    }
    clock.left();need(done && position===FILES.length && file===null && pending.length===0);
    fs.fsyncSync(root.fd);root.check();
    return {abi:1,scope:'isolated memory bundle only',files:9,complete:true,plaintext_persisted_outside_memory:false,overall_acceptance:false};
  } finally {
    clearTimeout(timer);
    try { if (file !== null) fs.closeSync(file); } finally { root.close(); }
  }
}

function request(protocol, path, body, credentials, clock, budget) {
  return new Promise((resolve,reject) => {
    let settled=false;const fail=()=>finish(new Error('API proof refused'));
    const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);req.destroy();error?reject(error):resolve(value);};
    const options={hostname:'127.0.0.1',port:protocol===https?16443:32379,path,method:body?'POST':'GET',agent:false,
      headers:{Accept:'application/json','Accept-Encoding':'identity',...(body?{'Content-Type':'application/json','Content-Length':body.length}:{})},
      ...(protocol===https?{...credentials,servername:'',minVersion:'TLSv1.2',rejectUnauthorized:true,checkServerIdentity:(_,cert)=>tls.checkServerIdentity('192.168.0.4',cert)}:{})};
    const req=protocol.request(options,response=>{
      if(response.statusCode!==200 || String(response.headers['content-type']||'').split(';')[0].trim()!=='application/json' ||
        (response.headers['content-encoding']||'identity')!=='identity'){response.destroy();fail();return;}
      const length=response.headers['content-length'];
      if(length!==undefined&&(!/^[0-9]+$/.test(length)||BigInt(length)>BigInt(MAX_REPLY))){response.destroy();fail();return;}
      let count=0;const chunks=[];
      response.on('data',chunk=>{if(settled){response.destroy();return;}try{clock.left();count+=chunk.length;budget.received+=chunk.length;
        need(count<=MAX_REPLY && budget.received<=MAX_TOTAL);chunks.push(chunk);}catch(_){response.destroy();fail();}});
      response.on('end',()=>{if(settled)return;try{clock.left();need(length===undefined||BigInt(count)===BigInt(length));finish(null,json(Buffer.concat(chunks),clock));}catch(_){fail();}});
      response.on('aborted',fail);response.on('error',fail);
    });
    const timer=setTimeout(fail,clock.left());req.on('error',fail);if(body)req.write(body);req.end();
  });
}
async function oracle(clock, rootPath = ROOT) {
  const root=new MemoryRoot(rootPath);let encryption=null;let credentials=null;let before=null,after=null,expected=null,actual=null;const plaintexts=[];
  try {
    encryption=configKeys(root.read('encryption-config.json'),clock);
    credentials={ca:root.read('ca.crt'),cert:root.read('admin.crt'),key:root.read('admin.key')};
    const client=new crypto.X509Certificate(credentials.cert),ca=new crypto.X509Certificate(credentials.ca);
    need(client.verify(ca.publicKey) && client.checkPrivateKey(crypto.createPrivateKey(credentials.key)));
    const body=Buffer.from(JSON.stringify({key:Buffer.from('/registry/secrets/').toString('base64'),
      range_end:Buffer.from('/registry/secrets0').toString('base64')}));
    const cipherBudget={received:0};before=registry(await request(http,'/v3/kv/range',body,null,clock,cipherBudget),clock);
    expected=new Map();
    for(const [key,value]of before.result){clock.left();const plain=decrypt(value,encryption,clock);plaintexts.push(plain);let secret;
      try{secret=secretProto(plain,clock);need(key==='/registry/secrets/'+secret.namespace+'/'+secret.name);}
      finally{/* Underlying decoded values remain private until comparison finishes. */}
      need(!expected.has(key));expected.set(key,secret);}
    actual=new Map();let cursor='',version=null,pages=0;const seen=new Set(),apiBudget={received:0};
    do {
      clock.left();need(++pages<=MAX_ITEMS+1);
      const query=new URLSearchParams({limit:'200'});if(cursor)query.set('continue',cursor);
      const list=await request(https,'/api/v1/secrets?'+query.toString(),null,credentials,clock,apiBudget);
      need(list.apiVersion==='v1'&&list.kind==='SecretList'&&list.metadata!==null&&typeof list.metadata==='object'&&
        Array.isArray(list.items)&&typeof list.metadata.resourceVersion==='string'&&list.metadata.resourceVersion.length>0&&list.metadata.resourceVersion.length<=256);
      if(version===null)version=list.metadata.resourceVersion;need(list.metadata.resourceVersion===version);
      for(const item of list.items){clock.left();const secret=apiSecret(item,true),key='/registry/secrets/'+secret.namespace+'/'+secret.name;
        need(!actual.has(key)&&actual.size<MAX_ITEMS);actual.set(key,secret);}
      cursor=own(list.metadata,'continue')?list.metadata.continue:'';
      need(typeof cursor==='string'&&cursor.length<=8192&&(!cursor||!seen.has(cursor)));if(cursor)seen.add(cursor);
      need(!own(list.metadata,'remainingItemCount')||(Number.isSafeInteger(list.metadata.remainingItemCount)&&list.metadata.remainingItemCount>=0));
      if(!cursor&&own(list.metadata,'remainingItemCount'))need(list.metadata.remainingItemCount===0);
    }while(cursor);
    compare(expected,actual,clock);
    after=registry(await request(http,'/v3/kv/range',body,null,clock,cipherBudget),clock);sameCipher(before.result,after.result);
    root.check();clock.left();
    return {abi:1,scope:'isolated retained-snapshot API Secret recovery only',secret_count:expected.size,
      complete_ciphertext_map_unchanged:true,independent_aescbc_protobuf_api_map_equal:true,
      tls_verified:true,plaintext_or_plaintext_hash_returned:false,production_current_values_read:false,
      full_control_plane_or_longhorn_recovery:false,overall_acceptance:false};
  } finally {
    if(encryption)for(const value of encryption.values())value.fill(0);
    if(credentials)for(const value of Object.values(credentials))value.fill(0);
    for(const inventory of [before?.result,after?.result])if(inventory)for(const value of inventory.values())value.fill(0);
    for(const inventory of [expected,actual])if(inventory)for(const secret of inventory.values())for(const value of secret.data.values())value.fill(0);
    for(const plain of plaintexts)plain.fill(0);
    encryption=credentials=before=after=expected=actual=null;root.close();
  }
}
async function main() {
  const clock=new Clock();need(process.argv.length===3);
  if(process.argv[2]==='--bundle')return writer(process.stdin,clock);
  need(process.argv[2]==='--oracle');
  // Public timing header only; no credential/configuration data in this invocation.
  const parts=[];let count=0;const timer=setTimeout(()=>process.stdin.destroy(new Error('API proof refused')),clock.left());
  try{for await(const part of process.stdin){count+=part.length;need(count<=MAGIC.length+4);parts.push(part);clock.left();}}
  finally{clearTimeout(timer);}
  const header=Buffer.concat(parts);need(header.length===MAGIC.length+4&&header.subarray(0,MAGIC.length).equals(MAGIC));
  clock.narrow(header.readUInt32BE(MAGIC.length));return oracle(clock);
}
if(require.main===module)main().then(value=>process.stdout.write(JSON.stringify(value)+'\n')).catch(()=>{
  process.stdout.write('{"abi":1,"refused":true,"code":"proof","overall_acceptance":false}\n');process.exitCode=1;
});
module.exports={Clock,json,base64,configKeys,secretProto,decrypt,registry,sameCipher,apiSecret,compare,MemoryRoot,writer,oracle,request,FILES,MAGIC};
