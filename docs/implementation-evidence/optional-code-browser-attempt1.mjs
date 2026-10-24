// Current built routes only. Public disposable SQLite/CLI fixtures, no runner or mutations.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,sep} from 'node:path';
import {gzipSync,brotliCompressSync} from 'node:zlib';
const {chromium}=createRequire(import.meta.url)(process.argv[2]);
const reportPath='../../docs/implementation-evidence/optional-code-browser.json';
const report={startedAt:new Date().toISOString(),source:'cd4ff760; unchanged6fb01043 production build',scope:'Actual /deploy and /pods with existing disposable fixture. Initial versus explicitly opened optional chunks; no baseline speed claim',profile:{width:390,height:844,cpuRate:4,latencyMs:150,downloadBytesPerSecond:200000,uploadBytesPerSecond:93750,pairs:3},samples:[],checks:[],failures:[],terminal:false};
const save=()=>writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(check,message,ms=30000){const end=Date.now()+ms;while(Date.now()<end){if(await check())return;await pause(100);}throw Error(message);}
async function closed(child){if(!child||child.exitCode!==null||child.signalCode!==null)return;await new Promise(resolve=>{const timer=setTimeout(resolve,10000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
const fixture=spawn(process.execPath,['node_modules/tsx/dist/cli.mjs','tests/ui-fixture.ts'],{stdio:['pipe','pipe','pipe'],windowsHide:true});
report.ownedProcesses={fixturePid:fixture.pid};let chrome,browser;
const metrics=result=>Object.fromEntries(result.metrics.filter(row=>['TaskDuration','ScriptDuration','LayoutDuration','RecalcStyleDuration','JSHeapUsedSize','Nodes'].includes(row.name)).map(row=>[row.name,row.value]));
function delta(a,b){return Object.fromEntries(Object.keys(b).map(name=>[name,name.endsWith('Duration')?(b[name]-a[name])*1000:b[name]]));}
try{
 const state=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture startup timeout')),45000);fixture.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited before ready'));});fixture.stderr.on('data',()=>{});fixture.stdout.on('data',chunk=>{raw=(raw+chunk).slice(-65536);const match=raw.match(/UI_FIXTURE_READY (\{[^\n]+\})/);if(match){clearTimeout(timer);resolve(JSON.parse(match[1]));}});});
 const profile=await mkdtemp(join(tmpdir(),'bortus-optional-code-chrome-'));
 chrome=spawn(process.argv[3],['--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-networking','about:blank'],{stdio:'ignore',windowsHide:true});report.ownedProcesses.chromePid=chrome.pid;save();
 let port;await until(async()=>{try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];return !!port;}catch{return false;}},'Owned Chrome startup timeout',15000);
 browser=await chromium.connectOverCDP('http://127.0.0.1:'+port,{noDefaults:true});report.browserVersion=browser.version();
 const context=browser.contexts()[0],page=context.pages()[0],cdp=await context.newCDPSession(page);
 await page.setViewportSize({width:390,height:844});await cdp.send('Network.enable');await cdp.send('Performance.enable',{timeDomain:'timeTicks'});await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});await cdp.send('Network.setCacheDisabled',{cacheDisabled:false});await cdp.send('Network.setBypassServiceWorker',{bypass:true});
 const network={urlPattern:'',latency:150,downloadThroughput:200000,uploadThroughput:93750,connectionType:'cellular3g'};
 report.networkRule=await cdp.send('Network.emulateNetworkConditionsByRule',{offline:false,matchedNetworkConditions:[network]});
 await page.addInitScript(()=>{globalThis.fixtureLcp=[];new PerformanceObserver(list=>{for(const row of list.getEntries())globalThis.fixtureLcp.push({startTime:row.startTime,renderTime:row.renderTime,loadTime:row.loadTime,size:row.size});}).observe({type:'largest-contentful-paint',buffered:true});});
 let requests=new Map(),scripts=[],events={},eventCount=0,tracing=false;
 cdp.on('Network.responseReceived',data=>{const url=new URL(data.response.url);if(data.type==='Script'&&url.pathname.startsWith('/_next/static/'))requests.set(data.requestId,{path:url.pathname,status:data.response.status,fromDiskCache:!!data.response.fromDiskCache,fromServiceWorker:!!data.response.fromServiceWorker});});
 cdp.on('Network.loadingFinished',data=>{const row=requests.get(data.requestId);if(row){scripts.push({...row,encodedDataLength:data.encodedDataLength});requests.delete(data.requestId);}});
 cdp.on('Tracing.dataCollected',data=>{if(!tracing)return;for(const event of data.value){eventCount++;if(event.ph==='X'&&typeof event.dur==='number'&&['EvaluateScript','FunctionCall','v8.compile','V8.CompileCode','V8.ParseOnBackground','V8.ParseOnBackgroundParsing','ParseProgram','CompileScript'].includes(event.name)){const row=events[event.name]??={count:0,totalDurationUs:0};row.count++;row.totalDurationUs+=event.dur;events[event.name]=row;}}});
 async function traceStart(){events={};eventCount=0;tracing=true;await cdp.send('Tracing.start',{categories:'devtools.timeline,v8,disabled-by-default-v8.compile',transferMode:'ReportEvents'});}
 async function traceEnd(){await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Trace completion timeout')),15000);cdp.once('Tracing.tracingComplete',()=>{clearTimeout(timer);resolve();});void cdp.send('Tracing.end').catch(reject);});tracing=false;assert(eventCount<1000000,'Trace bounded count exceeded');return {events,eventCount};}
 const fit=()=>page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,width:innerWidth,height:innerHeight,dpr:devicePixelRatio}));
 const api=async()=>{const response=await fetch(state.writerUrl+'/__fixture/status',{signal:AbortSignal.timeout(10000)});assert.equal(response.status,200);return response.json();};
 for(const route of ['/deploy','/pods'])for(let pair=0;pair<3;pair++)for(const cache of ['cold','warm']){
  report.phase={route,pair,cache};save();await page.goto('about:blank');if(cache==='cold')await cdp.send('Network.clearBrowserCache');requests=new Map();scripts=[];
  const before=metrics(await cdp.send('Performance.getMetrics'));await traceStart();const start=Date.now();await page.goto(state.writerUrl+route,{waitUntil:'load',timeout:60000});
  const trigger=route==='/deploy'?page.getByRole('button',{name:'Delete job completed-ui-job',exact:true}):page.getByRole('button',{name:'Actions for large-pod-0',exact:true});await trigger.waitFor({timeout:30000});
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const initial={locatorReadyWallMs:Date.now()-start,metrics:delta(before,metrics(await cdp.send('Performance.getMetrics'))),trace:await traceEnd(),scripts:[...scripts],lcp:await page.evaluate(()=>globalThis.fixtureLcp.at(-1)??null),geometry:await fit()};assert(initial.geometry.scroll<=initial.geometry.client,'Initial mobile overflow');assert(initial.lcp,'Buffered LCP unavailable');assert(scripts.every(row=>row.status===200),'Initial script unavailable');
  if(route==='/deploy')assert.equal(await page.getByText('Provisioning is disabled in this runtime. Run it from the independent operator environment.',{exact:true}).count(),1);
  const statusBefore=await api(),scriptIndex=scripts.length;
  const interactionBefore=metrics(await cdp.send('Performance.getMetrics'));await traceStart();
  await page.evaluate(()=>{globalThis.fixtureInteraction={};document.addEventListener('click',()=>{globalThis.fixtureInteraction.clickAt=performance.now();const observer=new MutationObserver(()=>{const modal=document.querySelector('[role="dialog"]');const menu=document.querySelector('[role="menu"]');if(modal||menu){observer.disconnect();requestAnimationFrame(()=>{globalThis.fixtureInteraction.visibleAt=performance.now();globalThis.fixtureInteraction.role=modal?'dialog':'menu';});}});observer.observe(document.body,{childList:true,subtree:true});},{capture:true,once:true});});
  const clicked=Date.now();await trigger.click();let dialog;
  if(route==='/pods'){await page.getByRole('menuitem',{name:'View YAML',exact:true}).waitFor();await until(async()=>await page.evaluate(()=>Number.isFinite(globalThis.fixtureInteraction.visibleAt)),'Menu event timing unavailable');initial.menuEventToFrameMs=await page.evaluate(()=>globalThis.fixtureInteraction.visibleAt-globalThis.fixtureInteraction.clickAt);await page.evaluate(()=>{globalThis.fixtureInteraction={};document.addEventListener('click',()=>{globalThis.fixtureInteraction.clickAt=performance.now();const observer=new MutationObserver(()=>{if(document.querySelector('[role="dialog"]')){observer.disconnect();requestAnimationFrame(()=>{globalThis.fixtureInteraction.visibleAt=performance.now();globalThis.fixtureInteraction.role='dialog';});}});observer.observe(document.body,{childList:true,subtree:true});},{capture:true,once:true});});await page.getByRole('menuitem',{name:'View YAML',exact:true}).click();dialog=page.getByRole('dialog',{name:/YAML:/});}
  else dialog=page.getByRole('dialog',{name:'Delete job history',exact:true});
  await dialog.waitFor();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const interaction={locatorVisibleWallMs:Date.now()-clicked,eventToFirstMenuOrDialogFrameMs:await page.evaluate(()=>globalThis.fixtureInteraction.visibleAt-globalThis.fixtureInteraction.clickAt),metrics:delta(interactionBefore,metrics(await cdp.send('Performance.getMetrics'))),trace:await traceEnd(),scripts:scripts.slice(scriptIndex),geometry:await dialog.evaluate(element=>{const r=element.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,focusInside:element.contains(document.activeElement)};})};
  assert(Number.isFinite(interaction.eventToFirstMenuOrDialogFrameMs),'Click/frame timing unavailable');assert(interaction.scripts.length>0,'Explicit optional opening loaded no distinct script');assert(interaction.scripts.every(row=>!initial.scripts.some(before=>before.path===row.path)),'Optional chunk was already in initial script inventory');assert(interaction.geometry.left>=0&&interaction.geometry.right<=interaction.geometry.width&&interaction.geometry.top>=0&&interaction.geometry.bottom<=interaction.geometry.height,'Optional dialog clipped');assert(interaction.geometry.focusInside,'Optional dialog focus missing');
  for(let n=0;n<8;n++){await page.keyboard.press('Tab');assert(await dialog.evaluate(element=>element.contains(document.activeElement)),'Dialog focus escaped');}
  await dialog.getByRole('button',{name:'Close dialog',exact:true}).click();await until(async()=>await trigger.evaluate(element=>element===document.activeElement),'Focus did not return');
  const statusAfter=await api();const sentMutations=Object.entries(statusAfter.requests).filter(([key,count])=>/^(POST|PATCH|DELETE) /.test(key)&&count>(statusBefore.requests[key]??0));assert.deepEqual(sentMutations,[],'Optional inspection sent mutation');
  report.samples.push({route,pair,cache,initial,interaction,noMutation:true});save();console.log('OPTIONAL_CODE_SAMPLE '+route+' '+pair+' '+cache);
 }
 const files=new Map();const staticRoot=resolve('.next/static');
 for(const sample of report.samples)for(const row of [...sample.initial.scripts,...sample.interaction.scripts])if(!files.has(row.path)){
  const target=resolve(staticRoot,decodeURIComponent(row.path.slice('/_next/static/'.length)));assert(target.startsWith(staticRoot+sep),'Static asset escape');const raw=await readFile(target);files.set(row.path,{path:row.path,sha256:createHash('sha256').update(raw).digest('hex'),rawBytes:raw.length,gzipBytes:gzipSync(raw).length,brotliBytes:brotliCompressSync(raw).length});
 }
 report.files=[...files.values()];for(const sample of report.samples)for(const phase of ['initial','interaction']){const rows=[...new Set(sample[phase].scripts.map(row=>row.path))].map(path=>files.get(path));sample[phase].offlineCompression={files:rows.length,rawBytes:rows.reduce((n,row)=>n+row.rawBytes,0),gzipBytes:rows.reduce((n,row)=>n+row.gzipBytes,0),brotliBytes:rows.reduce((n,row)=>n+row.brotliBytes,0)};}
 await page.goto('about:blank');await until(async()=>(await api()).activeStreams===0,'Provisioning stream survived navigation');
 report.checks=[{name:'Twelve actual mobile cold/warm route samples with separate initial/optional wire and CPU/LCP/firstinteraction observations'},{name:'All optional dialog inspections preserve mobile geometry, trapped focus/return and zero mutation'},{name:'Owned provisioning streams close after navigation; runtime remains disabled'}];
 report.limitations=['Current-source contribution observations, not before/after audit speed acceptance','CDP ScriptDuration/TaskDuration are renderer elapsed CPU task metrics; trace durations overlap and must not be summed as totalCPU','Offline gzip/defaultBrotli are estimates of exact public chunks; encodedDataLength is actual local response/cache observation','Locator wall timings include automation/scroll overhead; event-to-frame is separately observed','Buffered initial LCP is recorded before explicit interaction; no Lighthouse/field/CoreWebVitals claim','Existing fixture runner disabled and no real provision or shell executed','No dynamic credential values/tokens/rawDOM/raw trace event arguments persisted'];
}catch(error){report.failures.push(error instanceof Error?error.message:'Fixed optional-code harness failure');process.exitCode=1;}
finally{
 if(browser){try{const s=await browser.newBrowserCDPSession();await s.send('Browser.close');}catch{}await browser.close().catch(()=>{});}await closed(chrome);if(chrome&&chrome.exitCode===null&&chrome.signalCode===null){chrome.kill();await closed(chrome);}
 if(!fixture.stdin.destroyed)fixture.stdin.write('stop\n');await closed(fixture);if(fixture.exitCode===null&&fixture.signalCode===null){fixture.kill();await closed(fixture);}
 report.cleanup={chromeExitCode:chrome?.exitCode??null,chromeSignal:chrome?.signalCode??null,fixtureExitCode:fixture.exitCode,fixtureSignal:fixture.signalCode};report.completedAt=new Date().toISOString();report.terminal=true;save();
}
