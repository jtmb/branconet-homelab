import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {planFromInputs as loginPlan,loginReplacement,assertCurrentLoginSources} from '../scripts/auth-login-current-unit-plan.mjs';
import {planFromInputs as currentPlan} from '../scripts/current-packaging-unit-plan.mjs';
import {planFromInputs as previousPlan,registerCurrentReplacement,historicalRegisterFixture,assertCurrentRegisterSources} from '../scripts/auth-register-current-unit-plan.mjs';
import {readPublicSnapshot,loginPackagingAuthority,assertCurrentRunnerInverse} from '../scripts/current-login-packaging.mjs';
const gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
const current=readPublicSnapshot(gitDir),historical=readPublicSnapshot(gitDir,loginPackagingAuthority.historicalCommit);
const runner='scripts/run-compatible-unit-tests.mjs';
const runnerDigest=bytes=>createHash('sha256').update(bytes).digest('hex');
const newNames=['auth-login-current-packaging.test.mjs','current-login-packaging.test.mjs'];
const names=s=>s.names.filter(n=>/^tests\/.*\.test\.(ts|mjs)$/.test(n)).map(n=>n.slice(6));
const root=fileURLToPath(new URL('../',import.meta.url));
test('L01 current raw runner reverses orchestration and both prior reviewed deltas to original M14 authority',()=>{
 assertCurrentRunnerInverse(readFileSync(root+runner),historical.read(runner));assert.equal(runnerDigest(current.read(runner)),loginPackagingAuthority.preOrchestrationRunner);
});
test('L02 original352/290 and current460/397 complete PUBLIC coverage remain distinct',()=>{
 const oldNames=names(historical),old=loginPlan(oldNames,n=>historical.read(n).toString());assert.equal(old.discovered.length,352);assert.equal(old.selected.length,290);assert.equal(old.replacements.length,62);
 const currentNames=[...names(current),...newNames],read=n=>current.names.includes(n)?current.read(n).toString():readFileSync(root+n,'utf8');
 const full=currentPlan(currentNames,read,gitDir),prior=previousPlan(currentNames,read);assert.equal(full.discovered.length,460);assert.equal(full.selected.length,397);assert.equal(full.replacements.length,63);assert.deepEqual(full.selected,prior.selected);assert.deepEqual(full.replacements,prior.replacements);
 const omitted=['tests/scanner-database-update.test.ts','tests/system-report.test.ts'];
 for(const p of omitted){assert.ok(old.selected.includes(p));assert.ok(full.selected.includes(p));assert.deepEqual(current.read(p),historical.read(p));}
 const privatePlan=currentPlan(currentNames.filter(n=>!omitted.includes('tests/'+n)),read,gitDir);assert.equal(privatePlan.discovered.length,458);assert.equal(privatePlan.selected.length,395);assert.deepEqual(full.selected.filter(n=>!privatePlan.selected.includes(n)).sort(),omitted);
 for(const r of full.terminalReplacements)assert.ok(full.selected.includes(r.current));assert.equal(new Set(full.selected).size,397);
});

import {readRegisterSnapshot,registerPackagingAuthority,assertCurrentRegisterRunnerInverse} from '../scripts/current-register-packaging.mjs';
const registerNow=readRegisterSnapshot(gitDir),registerHistory=readRegisterSnapshot(gitDir,registerPackagingAuthority.historicalCommit);
test('R73 A01 current runner raw inverse retains original registration M14',()=>{
 assertCurrentRegisterRunnerInverse(readFileSync(root+runner),registerHistory.read(runner));assert.equal(runnerDigest(registerNow.read(runner)),registerPackagingAuthority.preOrchestrationRunner);
});
test('R66 A02 historical354/291 and current460/397 PUBLIC coverage stay explicit',()=>{
 const old=previousPlan(names(registerHistory),n=>registerHistory.read(n).toString());assert.equal(old.discovered.length,354);assert.equal(old.selected.length,291);assert.equal(old.replacements.length,63);
 const newNames=names(registerNow),read=n=>registerNow.read(n).toString(),full=currentPlan(newNames,read,gitDir),prior=previousPlan(newNames,read);assert.equal(full.discovered.length,460);assert.equal(full.selected.length,397);assert.deepEqual(full.replacements,prior.replacements);assert.deepEqual(full.selected,prior.selected);
 const omissions=['tests/scanner-database-update.test.ts','tests/system-report.test.ts'];for(const p of omissions){assert.ok(old.selected.includes(p));assert.ok(full.selected.includes(p));assert.deepEqual(registerNow.read(p),registerHistory.read(p));}
 const privatePlan=currentPlan(newNames.filter(n=>!omissions.includes('tests/'+n)),read,gitDir);assert.equal(privatePlan.discovered.length,458);assert.equal(privatePlan.selected.length,395);assert.deepEqual(full.selected.filter(n=>!privatePlan.selected.includes(n)).sort(),omissions);
});

// M03 derivatives preserve all three original mutations. The CR perturbation
// includes a space so an LF source cannot turn it into accepted CRLF.
test('L03 original login mutations refuse on both supported source line-ending views',()=>{
 const original=readFileSync(root+loginReplacement.original,'utf8'),publicSource=current.read('src/app/api/auth/login/route.ts').toString();assert.equal(publicSource.includes('\r'),false);
 for(const source of [publicSource,publicSource.replaceAll('\n','\r\n')]){
  assertCurrentLoginSources(original,source);
  for(const changed of [source+'\n// unknown',source.replace('maxAge: 60','maxAge: 61'),source.replace('try {','try {\r ')]){
   assert.notEqual(changed,source,'Mutation must change source');assert.notEqual(changed.replaceAll('\r\n','\n'),source.replaceAll('\r\n','\n'),'Mutation survives accepted line-ending projection');
   assert.throws(()=>assertCurrentLoginSources(original,changed),/Unqualified current login source/);
  }
 }
});
test('R70 L03 original registration mutations refuse on both supported source line-ending views',()=>{
 const original=readFileSync(root+historicalRegisterFixture,'utf8'),previous=readFileSync(root+registerCurrentReplacement.original,'utf8'),publicSource=registerNow.read('src/app/api/auth/register/route.ts').toString();assert.equal(publicSource.includes('\r'),false);
 for(const source of [publicSource,publicSource.replaceAll('\n','\r\n')]){
  assertCurrentRegisterSources(original,source,previous);
  for(const changed of [source+'\n// unknown',source.replace('maxAge: 60','maxAge: 61'),source.replace('try {','try {\r ')]){
   assert.notEqual(changed,source,'Mutation must change source');assert.notEqual(changed.replaceAll('\r\n','\n'),source.replaceAll('\r\n','\n'),'Mutation survives accepted line-ending projection');
   assert.throws(()=>assertCurrentRegisterSources(original,changed,previous),/Unqualified current registration source/);
  }
 }
});
