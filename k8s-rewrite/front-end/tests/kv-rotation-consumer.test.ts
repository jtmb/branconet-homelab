import { test } from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import type { KvRotation } from "@prisma/client";
import { KvError } from "../src/lib/kv-contract";
import { KubectlRotationConsumer, ROTATION_MARKER } from "../src/lib/kv-rotation-consumer";
const row={id:randomUUID(),consumerKind:"Deployment",consumerNamespace:"apps",consumerName:"named-consumer"} as KvRotation;
const object=()=>({
  apiVersion:"apps/v1",kind:"Deployment",
  metadata:{name:"named-consumer",namespace:"apps",uid:"same-uid",resourceVersion:"1",annotations:{private:"synthetic-private-marker"}},
  spec:{template:{
    metadata:{labels:{app:"preserved"},annotations:{unrelated:"preserved"} as Record<string,string>},
    spec:{containers:[{name:"app",env:[{name:"PRIVATE",value:"synthetic-private-marker"}]}]},
  }},
});
test("consumer adapter returns selected metadata and UID/RV JSON-patches only one exact template marker",async()=>{
  const original=object(),calls:readonly string[][]=[];
  const adapter=new KubectlRotationConsumer(async args=>{(calls as string[][]).push([...args]);if(args[0]==="get")return original;
    const patch=JSON.parse(args[args.indexOf("-p")+1]);assert.deepEqual(patch.slice(0,2),[{op:"test",path:"/metadata/uid",value:"same-uid"},{op:"test",path:"/metadata/resourceVersion",value:"1"}]);
    assert.deepEqual(patch[2],{op:"add",path:"/spec/template/metadata/annotations/bortus.io~1rotation-id",value:row.id});assert.equal(patch.length,3);
    return {...original,metadata:{...original.metadata,resourceVersion:"2"},spec:{template:{...original.spec.template,metadata:{...original.spec.template.metadata,annotations:{...original.spec.template.metadata.annotations,[ROTATION_MARKER]:row.id}}}}};});
  original.spec.template.metadata.annotations[ROTATION_MARKER]="synthetic-private-marker";
  const meta=await adapter.inspect(row);assert.deepEqual(meta,{uid:"same-uid",resourceVersion:"1"});
  const result=await adapter.reload(row,meta);assert.equal(result.rotationId,row.id);assert.equal(result.resourceVersion,"2");
  assert.deepEqual(calls[2].slice(0,6),["patch","deployment","named-consumer","-n","apps","--type=json"]);
  assert(!JSON.stringify(calls).includes("synthetic-private-marker"));assert(!JSON.stringify(result).includes("synthetic-private-marker"));assert.equal(original.spec.template.metadata.annotations.unrelated,"preserved");
});
test("consumer replacement, stale RV and invalid identity refuse patch; matching owned marker is idempotent",async()=>{
  let current=object(),patches=0;
  const adapter=new KubectlRotationConsumer(async args=>{if(args[0]==="patch")patches++;return current;});
  await assert.rejects(adapter.reload(row,{uid:"changed",resourceVersion:"1"}),error=>error instanceof KvError&&error.status===409);
  await assert.rejects(adapter.reload(row,{uid:"same-uid",resourceVersion:"old"}),error=>error instanceof KvError&&error.status===409);
  current.spec.template.metadata.annotations[ROTATION_MARKER]=row.id;
  assert.equal((await adapter.reload(row,{uid:"same-uid",resourceVersion:"1"})).rotationId,row.id);assert.equal(patches,0);
  current={...current,metadata:{...current.metadata,name:"other"}};
  await assert.rejects(adapter.inspect(row),error=>error instanceof KvError&&error.status===409);
});
