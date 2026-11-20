import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
import {planFromInputs as previousPlan,executionFor as previousExecution} from './auth-login-current-unit-plan.mjs';
export {executionBatches,artifactStages,assertArtifactState,portableFixture,qualifiedNativeSHA256} from './auth-login-current-unit-plan.mjs';
const digest=value=>createHash('sha256').update(value).digest('hex');
const canonical=value=>value.replaceAll('\r\n','\n');
export const registerCurrentReplacement=Object.freeze({
 original:'tests/auth-register-post-node22.test.mjs',
 sha256:'f99b0444c2a430300f99bd8727864a378ed9f7faf93ea09f640bd53c438099c0',
 current:'tests/auth-register-post-current-source.test.mjs',controls:78,
 metadata:'tests/auth-register-current-unit-plan.test.mjs',
});
export const historicalRegisterFixture='tests/auth-register-post-source.test.ts';
export const historicalRegisterSHA256='c9d6fc744d812617bfe1aa47bec83f1e0abfd9fbbb37d902a273571639ee2d7d';
export function assertCurrentRegisterSources(original,current,previous){
 assert.equal(digest(canonical(original)),historicalRegisterSHA256,'Historical registration fixture changed');
 assert.equal(digest(canonical(previous)),registerCurrentReplacement.sha256,'Previous Node22 registration fixture changed');
 const source=canonical(current);
 assert.equal(digest(source),'601f87718aa72a21682b2a896e13a2cb49da1baa1f7ad1f35b09174413378acd','Unqualified current registration source');
 assert.equal(source.split('from "zod/v3";').length,2,'Unique maintained import');
 const historical=source.replace('from "zod/v3";','from "zod";');
 assert.equal(digest(historical),'f0a7cf3f7d7fa5e6d42c60dcb65fd99ea95e7eb4d4c236d3ee8a4894d9c85d68','Historical whole-source inverse');
 const marker='export async function POST(';const start=source.indexOf(marker);
 assert.ok(start>=0);assert.equal(source.indexOf(marker,start+1),-1);
 assert.equal(source.slice(start),historical.slice(historical.indexOf(marker)),'Exact selected declaration');
}
export function planFromInputs(names,read){
 const prior=previousPlan(names,read),row=registerCurrentReplacement;
 for(const [path,label] of [[row.original,'previous Node22 input'],[row.current,'replacement'],[row.metadata,'packaging metadata']])
  assert.ok(prior.discovered.includes(path),'Missing '+label+': '+path);
 assert.equal(digest(canonical(read(row.original))),row.sha256,'Previous Node22 registration fixture changed');
 assert.ok(prior.selected.includes(row.original),'Previous registration projection must be selected');
 const replacements=[...prior.replacements,row];
 const selected=[...new Set(prior.selected.map(path=>path===row.original?row.current:path))];
 assert.equal(selected.length,prior.selected.length-1);
 const terminalReplacements=replacements.filter(r=>!replacements.some(next=>next.original===r.current));
 return {...prior,replacements,selected,terminalReplacements,
  retainedUnmapped:prior.discovered.filter(path=>!replacements.some(r=>r.original===path||r.current===path)),
  scope:'63 fixed mappings including one registration chain; all prior62 rows retained, 62 terminal projections. New current-source registration78 only; historical fixtures, prior controls, VM/native phases and complete aggregate qualification remain separate.'};
}
export function unitTestPlan(root){return planFromInputs(readdirSync(join(root,'tests')),name=>readFileSync(join(root,name),'utf8'));}
export function executionFor(plan,args){
 if(args.length===0)return plan.selected;
 if(args.length===2&&args[0]==='--group'&&args[1]==='auth-register-current-source')return [registerCurrentReplacement.current];
 return previousExecution(plan,args);
}
