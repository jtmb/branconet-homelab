import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire,stripTypeScriptTypes} from 'node:module';
import {fileURLToPath} from 'node:url';
import {unitTestPlan,planFromInputs,executionFor,executionBatches,artifactStages,assertArtifactState,loginReplacement,assertCurrentLoginSources} from '../scripts/auth-login-current-unit-plan.mjs';
import {unitTestPlan as previousPlan,executionFor as previousExecution,executionBatches as previousBatches,artifactStages as previousStages} from '../scripts/aggregate-unit-plan.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');
const names=readdirSync(new URL('./',import.meta.url));
const original=read(loginReplacement.original),source=read('src/app/api/auth/login/route.ts');
const plan=unitTestPlan(root),prior=previousPlan(root);
const sha=value=>createHash('sha256').update(value).digest('hex');
test('M01 fixed current complete source and historical import-only inverse bind exactly',()=>{
 assert.equal(process.versions.node,'22.23.3');assertCurrentLoginSources(original,source);
 assertCurrentLoginSources(original.replaceAll('\r\n','\n').replaceAll('\n','\r\n'),source.replaceAll('\r\n','\n').replaceAll('\n','\r\n'));
});
test('M02 old complete module is refused rather than substituted for current',()=>{
 assert.throws(()=>assertCurrentLoginSources(original,source.replace('from "zod/v3";','from "zod";')),/Unqualified current login source/);
});
test('M03 unknown source, changed declaration, added neighbour and bare CR refuse',()=>{
 for(const changed of [source+'\n// unknown',source.replace('maxAge: 60','maxAge: 61'),source.replace('try {','try {\r')])
  assert.throws(()=>assertCurrentLoginSources(original,changed),/Unqualified current login source/);
});
test('M04 original fixture and old assertions remain whole-byte bound',()=>{
 for(const changed of [original+'\n// tamper',original.replace('assert.equal','assert.notEqual'),original.replace('06d7b4d0','c42dfb02')])
  assert.throws(()=>assertCurrentLoginSources(changed,source),/Historical login fixture changed/);
});
test('M05 projection inverse preserves entire native-erased original and compiler executable AST',()=>{
 const projected=read(loginReplacement.current).replaceAll('\r\n','\n');
 const begin='// BEGIN EXACT NATIVE TYPE-ERASED ORIGINAL; only current-source pin and registration recording differ.\n';
 const end='\n// END EXACT NATIVE TYPE-ERASED ORIGINAL\n';
 assert.equal(projected.split(begin).length,2);assert.equal(projected.split(end).length,2);
 const body=projected.split(begin)[1].split(end)[0];
 const restored=body.replaceAll('infrastructureControl(','test(').replace("'c42dfb02eb45e5c2627b4b3428ba09f392b580bfca0e89144c03612f1b4098af'","'06d7b4d0684150eac758b00d1219771fb4a86145ac11f055739826a837aa1fb6'");
 const canonical=original.replaceAll('\r\n','\n');const erased=stripTypeScriptTypes(canonical,{mode:'strip'});
 assert.equal(restored,erased,'complete inverse, including every assertion/harness/import/loader byte');
 const ts=createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT??'typescript');assert.equal(ts.version,'5.9.3');
 const normalize=text=>{const sf=ts.createSourceFile('independent.js',text,99,true,ts.ScriptKind.JS);const transformed=ts.transform(sf,[context=>{const visit=node=>ts.isParenthesizedExpression(node)?ts.visitNode(node.expression,visit):ts.visitEachChild(node,visit,context);return root=>ts.visitNode(root,visit);}]);try{return ts.createPrinter().printFile(transformed.transformed[0]);}finally{transformed.dispose();}};
 const compile=text=>{const out=ts.transpileModule(text,{compilerOptions:{target:99,module:99},reportDiagnostics:true});assert.deepEqual(out.diagnostics,[]);return normalize(out.outputText);};
 assert.equal(compile(canonical),compile(restored),'independent full executable AST bytes');
 let inverse=erased;const edits=[];assert.equal(canonical.length,erased.length);
 for(let i=0;i<canonical.length;){if(canonical[i]===erased[i]){i++;continue;}const start=i;while(i<canonical.length&&canonical[i]!==erased[i])i++;edits.push({start,end:i,value:canonical.slice(start,i)});}
 for(const edit of edits.toReversed())inverse=inverse.slice(0,edit.start)+edit.value+inverse.slice(edit.end);
 assert.equal(inverse,canonical);assert.equal(sha(inverse),loginReplacement.sha256);
});
test('M06 exact62 mappings retain prior61 and original controls; complete suite remains unqualified',()=>{
 assert.equal(plan.replacements.length,62);assert.deepEqual(plan.replacements.slice(0,-1),prior.replacements);
 assert.equal(plan.replacements.at(-1),loginReplacement);assert.equal(plan.selected.length,plan.discovered.length-62);
 assert.equal(new Set(plan.selected).size,plan.selected.length);assert.ok(!plan.selected.includes(loginReplacement.original));
 assert.ok(plan.selected.includes(loginReplacement.current));assert.ok(plan.selected.includes(loginReplacement.metadata));
 assert.deepEqual(plan.selected.filter(p=>![loginReplacement.current,loginReplacement.metadata].includes(p)),prior.selected.filter(p=>![loginReplacement.original,loginReplacement.current,loginReplacement.metadata].includes(p)));
});
test('M07 missing original, replacement or metadata refuses',()=>{
 for(const p of [loginReplacement.original,loginReplacement.current,loginReplacement.metadata])
  assert.throws(()=>planFromInputs(names.filter(n=>'tests/'+n!==p),read),/Missing/);
});
test('M08 planner refuses historical fixture tampering',()=>{
 assert.throws(()=>planFromInputs(names,p=>read(p)+(p===loginReplacement.original?'\n// tamper':'')),/Historical login fixture changed/);
});
test('M09 future ordinary TS/MJS inputs remain selected',()=>{
 const next=planFromInputs([...names,'future-login.test.ts','future-login.test.mjs'],read);
 for(const e of ['ts','mjs'])assert.ok(next.selected.includes('tests/future-login.test.'+e));
});
test('M10 new group only dispatches current76 and default retains exact selection',()=>{
 assert.deepEqual(executionFor(plan,['--group','auth-login-current-source']),[loginReplacement.current]);assert.equal(executionFor(plan,[]),plan.selected);
});
test('M11 inherited group and plan dispatch remain exact; unknown/surplus refuse',()=>{
 for(const g of ['aggregate-source-node22','legacy-route-copy','auth-register-node22','auth-session-node22'])
  assert.deepEqual(executionFor(plan,['--group',g]),previousExecution(plan,['--group',g]));
 assert.deepEqual(executionFor(plan,['--plan']),previousExecution(plan,['--plan']));
 for(const a of [['--group'],['--group','unknown'],['--group','auth-login-current-source','extra'],['--unknown']])assert.throws(()=>executionFor(plan,a));
});
test('M12 both VM children retain exact flags/order; all ordinary inputs retained',()=>{
 const batches=executionBatches(plan.selected),old=previousBatches(prior.selected);
 assert.deepEqual(batches.filter(b=>b.flags.length),old.filter(b=>b.flags.length));
 assert.deepEqual(batches.flatMap(b=>b.files),plan.selected);
});
test('M13 inherited genuine native phases and addon refusals are unchanged',()=>{
 const stages=artifactStages(plan.selected),old=previousStages(prior.selected);
 assert.deepEqual(stages.slice(0,2),old.slice(0,2));
 assert.deepEqual(stages.flatMap(s=>s.files).sort(),[...plan.selected].sort());
 assert.throws(()=>assertArtifactState(stages[0],{exists:true}),/genuinely be absent/);
 assert.throws(()=>assertArtifactState(stages[2],{exists:false}),/genuine addon/);
 assert.throws(()=>assertArtifactState(stages[2],{exists:true,regularFile:true,sha256:'unknown'}),/native provenance/);
});
test('M14 actual runner advances only the planner import; original runner inverse exact',()=>{
 const runner=read('scripts/run-compatible-unit-tests.mjs');
 assert.equal(runner.split("from './auth-login-current-unit-plan.mjs'").length,2);
 const inverse=runner.replace("from './auth-login-current-unit-plan.mjs'","from './aggregate-unit-plan.mjs'").replaceAll('\r\n','\n');
 assert.equal(sha(inverse),'07b33c7d19fa6d180b7322035481750ca35ece8d55b4a27200d54ce1a336e868');
});
test('M15 full actual public inputs preserve both privately omitted ordinary fixtures and352/290 selection',()=>{
 const publicRoot=process.env.BORTUS_LOGIN_METADATA_PUBLIC_ROOT??root;
 const publicRead=p=>readFileSync(publicRoot+'/'+p,'utf8');
 const publicNames=readdirSync(publicRoot+'/tests');
 const pins={"system-report.test.ts": "8ecbe79443ff5904faa0856c8cbe121ca87b4fd861fba16e95530455995b0688", "scanner-database-update.test.ts": "e4ea8d9c100f90bcfae26b6240abcd37d9303e7d5d11dd4f366764b70d64cf4d"};
 for(const [name,pin] of Object.entries(pins))assert.equal(sha(publicRead('tests/'+name).replaceAll('\r\n','\n')),pin,'Complete actual public ordinary input');
 const fullNames=[...new Set([...publicNames,...names])];
 const fullRead=p=>[loginReplacement.current,loginReplacement.metadata].includes(p)?read(p):publicRead(p);
 const full=planFromInputs(fullNames,fullRead);assert.equal(full.discovered.length,352);assert.equal(full.selected.length,290);
 for(const name of Object.keys(pins))assert.ok(full.selected.includes('tests/'+name));
 assert.deepEqual(full.replacements,plan.replacements);
 const omitted=full.selected.filter(p=>!plan.selected.includes(p));
 assert.deepEqual(omitted.sort(),Object.keys(pins).map(n=>'tests/'+n).filter(p=>!plan.selected.includes(p)).sort());
});

test('M16 exact selected partition counts every retained metadata/ordinary input once',()=>{
 assert.deepEqual([...plan.selected].sort(),[...plan.retainedUnmapped,...plan.replacements.map(r=>r.current)].sort());
 assert.equal(new Set(plan.retainedUnmapped).size,plan.retainedUnmapped.length);
 for(const r of plan.replacements){assert.ok(!plan.retainedUnmapped.includes(r.original));assert.ok(!plan.retainedUnmapped.includes(r.current));}
});
