import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire,stripTypeScriptTypes} from 'node:module';
import {fileURLToPath} from 'node:url';
import {unitTestPlan,planFromInputs,executionFor,executionBatches,artifactStages,assertArtifactState,registerCurrentReplacement as row,historicalRegisterFixture,historicalRegisterSHA256,assertCurrentRegisterSources} from '../scripts/auth-register-current-unit-plan.mjs';
import {unitTestPlan as previousPlan,executionFor as previousExecution,executionBatches as previousBatches,artifactStages as previousStages} from '../scripts/auth-login-current-unit-plan.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');
const names=readdirSync(new URL('./',import.meta.url));
const original=read(historicalRegisterFixture),previous=read(row.original),source=read('src/app/api/auth/register/route.ts');
const plan=unitTestPlan(root),prior=previousPlan(root);
const sha=value=>createHash('sha256').update(value).digest('hex');
const canonical=value=>value.replaceAll('\r\n','\n');
function inverseProjection(projected){
 const begin='// BEGIN EXACT NATIVE TYPE-ERASED ORIGINAL; only current-source pin, Node22 version and registration recording differ.\n';
 const end='\n// END EXACT NATIVE TYPE-ERASED ORIGINAL\n';
 const text=canonical(projected);assert.equal(text.split(begin).length,2);assert.equal(text.split(end).length,2);
 const body=text.split(begin)[1].split(end)[0];
 assert.equal(body.split("'v22.23.3'").length,2,'Exact Node22 adaptation');
 assert.equal(body.split("'601f87718aa72a21682b2a896e13a2cb49da1baa1f7ad1f35b09174413378acd'").length,2,'Exact current-source adaptation');
 return body.replaceAll('infrastructureControl(','test(')
  .replace("'601f87718aa72a21682b2a896e13a2cb49da1baa1f7ad1f35b09174413378acd'","'f0a7cf3f7d7fa5e6d42c60dcb65fd99ea95e7eb4d4c236d3ee8a4894d9c85d68'")
  .replace("'v22.23.3'","'v24.18.0'");
}
test('M01 fixed complete historical, previous Node22 and current source bindings accept LF and CRLF',()=>{
 assert.equal(process.versions.node,'22.23.3');assertCurrentRegisterSources(original,source,previous);
 const crlf=s=>canonical(s).replaceAll('\n','\r\n');
 assertCurrentRegisterSources(crlf(original),crlf(source),crlf(previous));
});
test('M02 historical whole module is refused as a current source substitute',()=>{
 assert.throws(()=>assertCurrentRegisterSources(original,source.replace('from "zod/v3";','from "zod";'),previous),/Unqualified current registration source/);
});
test('M03 unknown source, changed POST, added neighbour and bare CR refuse',()=>{
 for(const changed of [source+'\n// unknown',source.replace('maxAge: 60','maxAge: 61'),source.replace('try {','try {\r')])
  assert.throws(()=>assertCurrentRegisterSources(original,changed,previous),/Unqualified current registration source/);
});
test('M04 both historical fixtures and old whole-module assertions refuse tampering',()=>{
 for(const changed of [original+'\n// tamper',original.replace('assert.equal','assert.notEqual'),original.replace('f0a7cf3f','601f8771')])
  assert.throws(()=>assertCurrentRegisterSources(changed,source,previous),/Historical registration fixture changed/);
 for(const changed of [previous+'\n// tamper',previous.replace('assert.equal','assert.notEqual'),previous.replace('f0a7cf3f','601f8771')])
  assert.throws(()=>assertCurrentRegisterSources(original,source,changed),/Previous Node22 registration fixture changed/);
});
test('M05 full native-erasure inverse and independent executable AST bind genuine fixed compiler and runtime',()=>{
 const restored=inverseProjection(read(row.current)),text=canonical(original),erased=stripTypeScriptTypes(text,{mode:'strip'});
 assert.equal(restored,erased,'entire original including every harness, assertion, import and loader byte');
 const require=createRequire(import.meta.url),compiler=require.resolve(process.env.BORTUS_SOURCE_TYPESCRIPT??'typescript'),ts=require(compiler);
 assert.equal(ts.version,'5.9.3');assert.equal(sha(readFileSync(compiler)),'3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675');
 assert.equal(sha(readFileSync(process.execPath)),'fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48');
 const normalize=js=>{const sf=ts.createSourceFile('independent.js',js,99,true,ts.ScriptKind.JS);assert.deepEqual(sf.parseDiagnostics,[]);const t=ts.transform(sf,[context=>{const visit=n=>ts.isParenthesizedExpression(n)?ts.visitNode(n.expression,visit):ts.visitEachChild(n,visit,context);return n=>ts.visitNode(n,visit);}]);try{return ts.createPrinter().printFile(t.transformed[0]);}finally{t.dispose();}};
 const compile=s=>{const out=ts.transpileModule(s,{compilerOptions:{target:99,module:99},reportDiagnostics:true});assert.deepEqual(out.diagnostics,[]);return normalize(out.outputText);};
 assert.equal(compile(text),compile(restored),'independent complete executable AST byte parity');
 assert.equal(text.length,erased.length);const edits=[];
 for(let i=0;i<text.length;){if(text[i]===erased[i]){i++;continue;}const start=i;while(i<text.length&&text[i]!==erased[i])i++;edits.push({start,end:i,value:text.slice(start,i)});}
 let inverse=erased;for(const e of edits.toReversed())inverse=inverse.slice(0,e.start)+e.value+inverse.slice(e.end);
 assert.equal(inverse,text);assert.equal(sha(inverse),historicalRegisterSHA256);
});
test('M06 prior62 mapping rows remain exact; one additional chained mapping selects only the current registration',()=>{
 assert.equal(plan.replacements.length,63);assert.deepEqual(plan.replacements.slice(0,-1),prior.replacements);
 assert.equal(plan.replacements.at(-1),row);assert.equal(plan.selected.length,plan.discovered.length-63);
 assert.equal(new Set(plan.selected).size,plan.selected.length);assert.ok(!plan.selected.includes(row.original));
 assert.ok(plan.selected.includes(row.current));assert.ok(plan.selected.includes(row.metadata));
 assert.deepEqual(plan.selected.filter(p=>![row.current,row.metadata].includes(p)),prior.selected.filter(p=>![row.original,row.current,row.metadata].includes(p)));
});
test('M07 missing historical, previous Node22, current projection or metadata refuses',()=>{
 for(const p of [historicalRegisterFixture,row.original,row.current,row.metadata])
  assert.throws(()=>planFromInputs(names.filter(n=>'tests/'+n!==p),read),/Missing/);
});
test('M08 planner refuses changed previous Node22 fixture before returning selection',()=>{
 assert.throws(()=>planFromInputs(names,p=>read(p)+(p===row.original?'\n// tamper':'')),/Previous Node22 registration fixture changed/);
});
test('M09 future ordinary TS and MJS inputs remain selected',()=>{
 const next=planFromInputs([...names,'future-register.test.ts','future-register.test.mjs'],read);
 for(const e of ['ts','mjs'])assert.ok(next.selected.includes('tests/future-register.test.'+e));
});
test('M10 current registration group only dispatches current78; default returns exact current selection',()=>{
 assert.deepEqual(executionFor(plan,['--group','auth-register-current-source']),[row.current]);assert.equal(executionFor(plan,[]),plan.selected);
});
test('M11 inherited dispatch and refusals remain exact without executing old groups',()=>{
 for(const g of ['auth-login-current-source','aggregate-source-node22','legacy-route-copy','auth-register-node22','auth-session-node22'])
  assert.deepEqual(executionFor(plan,['--group',g]),previousExecution(plan,['--group',g]));
 assert.deepEqual(executionFor(plan,['--plan']),previousExecution(plan,['--plan']));
 for(const a of [['--group'],['--group','unknown'],['--group','auth-register-current-source','extra'],['--unknown']])assert.throws(()=>executionFor(plan,a));
});
test('M12 both VM children retain exact flags and order; every selected file appears once',()=>{
 assert.deepEqual(executionBatches(plan.selected).filter(b=>b.flags.length),previousBatches(prior.selected).filter(b=>b.flags.length));
 assert.deepEqual(executionBatches(plan.selected).flatMap(b=>b.files),plan.selected);
});
test('M13 genuine portable absent and pinned native preparation phases are unchanged',()=>{
 const stages=artifactStages(plan.selected),old=previousStages(prior.selected);
 assert.deepEqual(stages.slice(0,2),old.slice(0,2));assert.deepEqual(stages.flatMap(s=>s.files).sort(),[...plan.selected].sort());
 assert.throws(()=>assertArtifactState(stages[0],{exists:true}),/genuinely be absent/);
 assert.throws(()=>assertArtifactState(stages[2],{exists:false}),/genuine addon/);
 assert.throws(()=>assertArtifactState(stages[2],{exists:true,regularFile:true,sha256:'unknown'}),/native provenance/);
});
test('M14 actual runner advances only the planner import; full previous runner inverse exact',()=>{
 const runner=read('scripts/run-compatible-unit-tests.mjs');
 assert.equal(runner.split("from './auth-register-current-unit-plan.mjs'").length,2);
 assert.equal(sha(canonical(runner.replace("from './auth-register-current-unit-plan.mjs'","from './auth-login-current-unit-plan.mjs'"))),'bdd0fbb9def1b6a62f397b196d0564897a58d4dc508f3d55b6766193c654892a');
});
test('M15 actual public354 discovered and291 selected preserve both privately omitted ordinary fixtures',()=>{
 const publicRoot=process.env.BORTUS_REGISTER_METADATA_PUBLIC_ROOT??root;
 const publicRead=p=>readFileSync(publicRoot+'/'+p,'utf8'),publicNames=readdirSync(publicRoot+'/tests');
 const pins={'system-report.test.ts':'8ecbe79443ff5904faa0856c8cbe121ca87b4fd861fba16e95530455995b0688','scanner-database-update.test.ts':'e4ea8d9c100f90bcfae26b6240abcd37d9303e7d5d11dd4f366764b70d64cf4d'};
 for(const [name,pin] of Object.entries(pins))assert.equal(sha(canonical(publicRead('tests/'+name))),pin,'Actual public ordinary input bytes');
 const fullNames=[...new Set([...publicNames,...names])];
 const full=planFromInputs(fullNames,p=>names.includes(p.slice('tests/'.length))?read(p):publicRead(p));
 assert.equal(full.discovered.length,354);assert.equal(full.selected.length,291);assert.deepEqual(full.replacements,plan.replacements);
 for(const name of Object.keys(pins))assert.ok(full.selected.includes('tests/'+name));
 assert.deepEqual(full.selected.filter(p=>!plan.selected.includes(p)).sort(),Object.keys(pins).map(n=>'tests/'+n).filter(p=>!plan.selected.includes(p)).sort());
});
test('M16 exact terminal projection partition excludes intermediates and counts retained inputs once',()=>{
 assert.equal(plan.terminalReplacements.length,62);assert.deepEqual([...plan.selected].sort(),[...plan.retainedUnmapped,...plan.terminalReplacements.map(r=>r.current)].sort());
 assert.equal(new Set(plan.retainedUnmapped).size,plan.retainedUnmapped.length);
 for(const r of plan.replacements){assert.ok(!plan.retainedUnmapped.includes(r.original));assert.ok(!plan.retainedUnmapped.includes(r.current));}
});
test('M17 historical registration chain and previous login76 projection remain whole and bound',()=>{
 const old=plan.replacements.find(r=>r.original===historicalRegisterFixture);
 assert.equal(old.current,row.original);assert.equal(old.controls,78);assert.equal(old.sha256,historicalRegisterSHA256);
 assert.ok(!plan.selected.includes(historicalRegisterFixture));assert.ok(!plan.selected.includes(row.original));
 const login='tests/auth-login-post-current-source.test.mjs';assert.ok(plan.selected.includes(login));
 assert.equal(sha(canonical(read(login))),'4f51f9ea57b2edda4f275bd2c28c3ed4d15bc5a9fafd2e05622588e6fcb46317');
});
test('M18 complete projection inverse refuses assertion, harness, version, source pin and order tampering',()=>{
 const projected=read(row.current),erased=stripTypeScriptTypes(canonical(original),{mode:'strip'});
 for(const [from,to] of [['assert.deepEqual(h.trace,successOrder)','assert.deepEqual(h.trace,[])'],["hit('data.username')","hit('wrong.username')"],["assert.equal(process.version, 'v22.23.3')","assert.equal(process.version, 'v24.18.0')"],["const expectedCanonical = '601f8771","const expectedCanonical = 'unknown601f8771"],["'ensure:call','accounts.registrationOpen:get'","'wrong:call','accounts.registrationOpen:get'"]]){
  assert.ok(projected.includes(from),'Meaningful mutation exists');const changed=projected.replace(from,to);assert.notEqual(changed,projected);
  assert.throws(()=>assert.equal(inverseProjection(changed),erased));
 }
});
