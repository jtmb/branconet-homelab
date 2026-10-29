import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {planFromInputs as loginPlan} from '../scripts/auth-login-current-unit-plan.mjs';
import {planFromInputs as currentPlan} from '../scripts/current-packaging-unit-plan.mjs';
import {planFromInputs as previousPlan} from '../scripts/auth-register-current-unit-plan.mjs';
import {readPublicSnapshot,loginPackagingAuthority,assertCurrentRunnerInverse} from '../scripts/current-login-packaging.mjs';
const gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
const current=readPublicSnapshot(gitDir),historical=readPublicSnapshot(gitDir,loginPackagingAuthority.historicalCommit);
const runner='scripts/run-compatible-unit-tests.mjs';
const newNames=['auth-login-current-packaging.test.mjs','current-login-packaging.test.mjs'];
const names=s=>s.names.filter(n=>/^tests\/.*\.test\.(ts|mjs)$/.test(n)).map(n=>n.slice(6));
const root=fileURLToPath(new URL('../',import.meta.url));
test('L01 current raw runner reverses both reviewed deltas to original M14 authority',()=>{
 assertCurrentRunnerInverse(readFileSync(root+runner),historical.read(runner));assert.deepEqual(readFileSync(root+runner),current.read(runner));
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
