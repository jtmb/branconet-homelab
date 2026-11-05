'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{createRequire}=require('node:module');
const ts=createRequire(path.join(process.argv[2],'package.json'))('typescript');
assert.equal(process.version,'v22.23.3');
(async()=>{
 let hooks=0;
 for(const file of ['src/lib/auth.ts','src/middleware.ts']){
  const text=fs.readFileSync(path.join(__dirname,'baseline-v3-51e8cd6',file),'utf8'),parsed=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true),selectors=[];
  function visit(node){if(ts.isCallExpression(node)&&node.expression.getText(parsed).includes('?.span ??'))selectors.push(node.expression.getText(parsed));ts.forEachChild(node,visit);}visit(parsed);
  assert.equal(selectors.length,file.includes('middleware')?1:3);
  for(const selector of selectors){
   const code=ts.transpileModule('globalThis.invoke='+selector+';',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
   const absent=vm.createContext({});vm.runInContext(code,absent);const value={public_fixture:true},error=new Error('PUBLIC_EDGE_ERROR');
   assert.equal(absent.invoke('auth.jwt',()=>value),value);const promise=Promise.resolve(value);assert.equal(absent.invoke('auth.jwt',()=>promise),promise);
   assert.throws(()=>absent.invoke('auth.jwt',()=>{throw error;}),caught=>caught===error);
   await assert.rejects(absent.invoke('auth.jwt',()=>Promise.reject(error)),caught=>caught===error);
   let count=0;const present=vm.createContext({__bortusNativeDiag:{span(label,operation){assert.equal(label,'auth.jwt');count++;return operation();}}});vm.runInContext(code,present);
   assert.equal(present.invoke('auth.jwt',()=>value),value);assert.equal(count,1);hooks++;
  }
 }
 console.log(JSON.stringify({passed:true,actual_derived_hooks_tested:hooks,checks:['Absent-hook Edge-shaped context preserves return identity','Promise identity preserved','Sync error identity preserved','Async rejection identity preserved','Present Node hook required and invoked exactly once'],private_runtime_bridge:false}));
})().catch(()=>{process.exitCode=1;});
