import assert from 'node:assert/strict';import test from 'node:test';import path from 'node:path';import {createRequire} from 'node:module';import {pathToFileURL} from 'node:url';
const req=createRequire(import.meta.url),source=process.env.BORTUS_ZOD_SOURCE==='1',P=process.env.BORTUS_ZOD_DIRECTORY??path.dirname(req.resolve('zod/package.json')),message='BORTUS validation budget exceeded';
const load=(mode,n)=>mode==='CJS'?req(P+'/'+n+'.cjs'):import(pathToFileURL(P+(mode==='source'?'/src/':'/')+n+(mode==='source'?'.ts':'.js')).href);
const terminal=r=>{assert.equal(r.success,false);assert.equal(r.error.issues.length,1);assert.equal(r.error.issues[0].message,message);assert.deepEqual(r.error.issues[0].path,[]);};
const check = test;
assert.equal(req(P+'/package.json').version,'4.6.7');

for(const mode of source?['source']:['CJS','ESM'])for(const surface of ['root','v3','v4','mini','v4-mini','v4/mini','v4/core']){
 const api=await load(mode,surface==='root'?'index':surface+'/index'),core=await load(mode,'v4/core/index'),v3=surface==='v3',raw=surface==='v4/core';
 const num=()=>raw?new api.$ZodNumber({type:'number',checks:[]}):api.number(),str=()=>raw?new api.$ZodString({type:'string'}):api.string();
 const arr=s=>raw?new api.$ZodArray({type:'array',element:s}):api.array(s),obj=shape=>raw?new api.$ZodObject({type:'object',shape}):api.object(shape),union=ss=>raw?new api.$ZodUnion({type:'union',options:ss}):api.union(ss),any=()=>raw?new api.$ZodAny({type:'any'}):api.any();
 const parse=(s,v,a,c={})=>v3?(a?s.safeParseAsync(v,c):s.safeParse(v,c)):(a?core.safeParseAsync(s,v,c):core.safeParse(s,v,c));
 for(const async of [false,true]){
  const label=mode+' '+surface+' '+(async?'async':'sync');
  await check(label+' explicit and default collection admission',async()=>{
   for(const kind of ['array','set','map']){let reads=0;const child=str();if(v3){const p=child._parse;child._parse=function(i){reads++;return p.call(this,i);};}else{const run=child._zod.run;child._zod.run=(p,c)=>{reads++;return run(p,c);};}
    let schema=kind==='array'?arr(child):kind==='set'?(raw?new api.$ZodSet({type:'set',valueType:child}):api.set(child)):(raw?new api.$ZodMap({type:'map',keyType:num(),valueType:child}):api.map(num(),child));
    const input=n=>kind==='array'?Array(n).fill(0):kind==='set'?new Set(Array.from({length:n},(_,i)=>i)):new Map(Array.from({length:n},(_,i)=>[i,0]));
    if(kind!=='map'||!v3){const check=kind==='array'?core._maxLength(2):core._maxSize(2);const limited=v3?(kind==='array'?schema.max(2):schema.max(2)):schema.check?schema.check(check):core.clone(schema,{...schema._zod.def,checks:[check]});const result=await parse(limited,input(9),async);assert.equal(result.success,false);assert.equal(result.error.issues[0].maximum,2);assert.equal(reads,0);}
    const r=await parse(schema,input(10001),async);assert.equal(r.success,false);assert.equal(reads,0);assert.equal(r.error.issues.length,1);
   }
  });
  await check(label+' nested issues and branch exhaustion',async()=>{const nested=arr(arr(str())),input=Array.from({length:29},()=>Array(53).fill(7));terminal(await parse(obj({value:nested}),{value:input},async));terminal(await parse(union([nested,any()]),input,async));const caught=v3?nested.catch([]):new core.$ZodCatch({type:'catch',innerType:nested,catchValue:()=>[]});terminal(await parse(caught,input,async));});
  await check(label+' small values ordered errors fresh concurrent state',async()=>{const schema=obj({x:arr(arr(str()))}),ctx={};const good={x:[['alpha','β']]};const [bad,valid]=await Promise.all([parse(schema,{x:Array.from({length:29},()=>Array(53).fill(7))},async,ctx),parse(schema,good,async,ctx)]);terminal(bad);assert.deepEqual(valid.data,good);assert.deepEqual(ctx,{});const err=await parse(schema,{x:[[0,1],[2]]},async);assert.deepEqual(err.error.issues.map(i=>i.path),[['x',0,0],['x',0,1],['x',1,0]]);assert.deepEqual((await parse(schema,good,async,ctx)).data,good);});
  await check(label+' mixed-format shares slot budget',async()=>{const otherMode=mode==='CJS'?'ESM':'CJS',other=await load(otherMode,surface==='root'?'index':surface+'/index');const numbers=a=>raw?new a.$ZodArray({type:'array',element:new a.$ZodArray({type:'array',element:new a.$ZodNumber({type:'number',checks:[]})})}):a.array(a.array(a.number()));const schema=obj({a:numbers(api),b:numbers(other)});terminal(await parse(schema,{a:Array.from({length:111},()=>Array(501).fill(1)),b:Array.from({length:111},()=>Array(501).fill(1))},async));});
  await check(label+' depth and default valid boundary',async()=>{let schema;schema=raw?new api.$ZodLazy({type:'lazy',getter:()=>arr(schema)}):api.lazy(()=>arr(schema));let input=[];for(let i=0;i<151;i++)input=[input];terminal(await parse(schema,input,async));assert.equal((await parse(arr(num()),Array(10000).fill(1),async)).data.length,10000);});
 }
 if(!v3)await check(mode+' '+surface+' compiler schema entry points retain bounded runtime',async()=>{const compiler=await load(mode,'v4/core/compile');const schema=arr(arr(num())),compiled=compiler.compile(schema),input=Array.from({length:111},()=>Array(1001).fill(1));terminal(core.safeParse(compiled,input));assert.equal(core.validate(compiled,input),false);assert.equal(core.validate(compiled,[[1,2]]),true);assert.deepEqual(core.parse(compiled,[[1,2]]),[[1,2]]);});
}
