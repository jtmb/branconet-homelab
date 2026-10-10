import { execFileSync, spawnSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import https from "node:https";
import { once } from "node:events";
import type { AddressInfo } from "node:net";
import type { V1Secret } from "@kubernetes/client-node";

export async function nativeTlsFixture(dir: string) {
  const openssl = spawnSync("openssl",["version"]).status===0 ? "openssl" : "C:/Program Files/Git/usr/bin/openssl.exe";
  if(spawnSync(openssl,["version"]).status!==0) throw new Error("OpenSSL is required for native TLS HTTP qualification");
  const key=path.join(dir,"native-key.pem"),cert=path.join(dir,"native-cert.pem"),config=path.join(dir,"native-config");
  execFileSync(openssl,["req","-x509","-newkey","rsa:2048","-nodes","-keyout",key,"-out",cert,"-days","1","-subj","/CN=localhost","-addext","subjectAltName=IP:127.0.0.1,DNS:localhost"],{stdio:"ignore"});
  const objects=new Map<string,V1Secret>(), calls:{method:string;path:string;metadata:boolean}[]=[]; let revision=0;
  const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
  const seed=(ns:string,name:string,data:Record<string,string>,extra:Partial<V1Secret>={})=>{
    const body:V1Secret={apiVersion:"v1",kind:"Secret",type:"Opaque",...extra,metadata:{...extra.metadata,namespace:ns,name,uid:"tls-uid-"+ ++revision,resourceVersion:String(revision),creationTimestamp:new Date()},data:clone(data)};
    objects.set(ns+"/"+name,body);return clone(body);
  };
  const server=https.createServer({key:await readFile(key),cert:await readFile(cert)},async(request,response)=>{
    try {
      const url=new URL(request.url||"/","https://localhost"),match=/^\/api\/v1\/namespaces\/([^/]+)\/secrets(?:\/([^/]+))?$/.exec(url.pathname);
      const metadata=!!request.headers.accept?.includes("PartialObjectMetadataList");
      calls.push({method:request.method||"",path:url.pathname,metadata});
      const send=(code:number,result:unknown)=>{response.writeHead(code,{"Content-Type":"application/json"});response.end(JSON.stringify(result));};
      if(request.headers.authorization!=="Bearer synthetic-native-api-token") return send(403,{message:"synthetic private API error"});
      if(!match) return send(404,{kind:"Status",code:404});
      const [,ns,name]=match,id=ns+"/"+name; let raw="";
      for await(const chunk of request){raw+=chunk;if(raw.length>2*1024*1024)throw Error();}
      if(request.method==="GET") {
        if(name){const value=objects.get(id);return value?send(200,value):send(404,{kind:"Status",code:404});}
        const list=[...objects.values()].filter(s=>s.metadata?.namespace===ns),limit=Number(url.searchParams.get("limit")||20),offset=Number(url.searchParams.get("continue")||0),page=list.slice(offset,offset+limit);
        return send(200,{apiVersion:metadata?"meta.k8s.io/v1":"v1",kind:metadata?"PartialObjectMetadataList":"SecretList",metadata:{continue:offset+limit<list.length?String(offset+limit):""},items:metadata?page.map(s=>({apiVersion:"meta.k8s.io/v1",kind:"PartialObjectMetadata",metadata:s.metadata})):page});
      }
      const body=JSON.parse(raw);
      if(request.method==="POST") {
        const target=ns+"/"+body.metadata.name;
        if(objects.has(target))return send(409,{kind:"Status",code:409});
        return send(201,seed(ns,body.metadata.name,body.data||{},body));
      }
      const current=objects.get(id);if(!current)return send(404,{kind:"Status",code:404});
      if(request.method==="PUT") {
        if(current.immutable||body.metadata.resourceVersion!==current.metadata?.resourceVersion)return send(409,{kind:"Status",code:409,message:"synthetic rejected body"});
        const next={...body,metadata:{...body.metadata,uid:current.metadata?.uid,resourceVersion:String(++revision)}};objects.set(id,next);return send(200,next);
      }
      if(request.method==="DELETE") {
        if(body.preconditions?.uid!==current.metadata?.uid||body.preconditions?.resourceVersion!==current.metadata?.resourceVersion)return send(409,{kind:"Status",code:409});
        objects.delete(id);return send(200,{apiVersion:"v1",kind:"Status",code:200});
      }
      return send(405,{kind:"Status",code:405});
    } catch { if(!response.headersSent)response.writeHead(500,{"Content-Type":"application/json"});response.end('{"error":"synthetic native fixture error"}'); }
  });
  server.listen(0,"127.0.0.1");await once(server,"listening");
  await writeFile(config,JSON.stringify({apiVersion:"v1",kind:"Config",clusters:[{name:"test",cluster:{server:"https://127.0.0.1:"+(server.address() as AddressInfo).port,"certificate-authority":cert}}],contexts:[{name:"test",context:{cluster:"test",user:"test"}}],users:[{name:"test",user:{token:"synthetic-native-api-token"}}],"current-context":"test"}));
  return {config,seed,objects,calls,async close(){server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));}};
}
