import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
import {planFromInputs as previousPlan,executionFor as previousExecution} from './aggregate-unit-plan.mjs';
export {executionBatches,artifactStages,assertArtifactState,portableFixture,qualifiedNativeSHA256} from './aggregate-unit-plan.mjs';
const digest=value=>createHash('sha256').update(value).digest('hex');
const canonical=value=>value.replaceAll('\r\n','\n');
export const loginReplacement=Object.freeze({
 original:'tests/auth-login-post-source.test.ts',
 sha256:'892f245cdea69d2349970f3219a941fe4223ba12fbede9330fb7859a01ad5062',
 current:'tests/auth-login-post-current-source.test.mjs',controls:76,
 metadata:'tests/auth-login-current-unit-plan.test.mjs',
});
export function assertCurrentLoginSources(original,current){
 assert.equal(digest(canonical(original)),loginReplacement.sha256,'Historical login fixture changed');
 const source=canonical(current);
 assert.equal(digest(source),'c42dfb02eb45e5c2627b4b3428ba09f392b580bfca0e89144c03612f1b4098af','Unqualified current login source');
 assert.equal(source.split('from "zod/v3";').length,2,'Unique maintained import');
 const historical=source.replace('from "zod/v3";','from "zod";');
 assert.equal(digest(historical),'06d7b4d0684150eac758b00d1219771fb4a86145ac11f055739826a837aa1fb6','Historical whole-source inverse');
 const marker='export async function POST(';const start=source.indexOf(marker);
 assert.ok(start>=0);assert.equal(source.indexOf(marker,start+1),-1);
 assert.equal(source.slice(start),historical.slice(historical.indexOf(marker)),'Exact selected declaration');
}
export function planFromInputs(names,read){
 const prior=previousPlan(names,read),row=loginReplacement;
 for(const [path,label] of [[row.original,'historical input'],[row.current,'replacement'],[row.metadata,'packaging metadata']])
  assert.ok(prior.discovered.includes(path),'Missing '+label+': '+path);
 assert.equal(digest(canonical(read(row.original))),row.sha256,'Historical login fixture changed');
 const replacements=[...prior.replacements,row];
 const selected=[...new Set(prior.selected.map(path=>path===row.original?row.current:path))];
 assert.equal(selected.length,prior.selected.length-1);
 return {...prior,replacements,selected,
  retainedUnmapped:prior.discovered.filter(path=>!replacements.some(r=>r.original===path||r.current===path)),
  scope:'62 fixed projections; new current-source login76 only. All prior61 mappings, historical login and other ordinary controls retained. Metadata, native/VM phases and complete aggregate qualification remain separate.'};
}
export function unitTestPlan(root){return planFromInputs(readdirSync(join(root,'tests')),name=>readFileSync(join(root,name),'utf8'));}
export function executionFor(plan,args){
 if(args.length===0)return plan.selected;
 if(args.length===2&&args[0]==='--group'&&args[1]==='auth-login-current-source')return [loginReplacement.current];
 return previousExecution(plan,args);
}