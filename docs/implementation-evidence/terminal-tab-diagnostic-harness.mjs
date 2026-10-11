// Disposable actual-route terminal checks. No submitted shell command or private output.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {mkdtemp,readFile} from 'node:fs/promises';
import {writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,sep} from 'node:path';
import {gzipSync,brotliCompressSync} from 'node:zlib';
const {chromium}=createRequire(import.meta.url)(process.argv[2]);
const reproduction=process.argv[4]==='reproduce';
const tabDiagnostic=process.argv[4]==='tab-diagnostic';
const reportPath='../../docs/implementation-evidence/terminal-'+(reproduction?'reproduction':tabDiagnostic?'tab-diagnostic':'browser')+'.json';
const report={startedAt:new Date().toISOString(),scope:'Actual disposable /pods terminal; no command submitted',reproduction,checks:[],failures:[],terminal:false};
const save=()=>writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn,message,ms=20000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await pause(100);}throw Error(message);}
async function closed(child){if(!child||child.exitCode!==null||child.signalCode!==null)return;await new Promise(resolve=>{const t=setTimeout(resolve,10000);child.once('exit',()=>{clearTimeout(t);resolve();});});}
const fixture=spawn(process.execPath,['node_modules/tsx/dist/cli.mjs','tests/ui-fixture.ts'],{env:{...process.env,BORTUS_UI_PRODUCTION_ASSETS_FIXTURE:'true',...(!reproduction?{BORTUS_UI_NATIVE_FIXTURE:'true'}:{})},stdio:['pipe','pipe','pipe'],windowsHide:true});
report.ownedProcesses={fixturePid:fixture.pid};let chrome,browser;
try{
 const state=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture startup timeout')),45000);fixture.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited before ready'));});fixture.stderr.on('data',()=>{});fixture.stdout.on('data',chunk=>{raw=(raw+chunk).slice(-65536);const match=raw.match(/UI_FIXTURE_READY (\{[^\n]+\})/);if(match){clearTimeout(timer);resolve(JSON.parse(match[1]));}});});
 const profile=await mkdtemp(join(tmpdir(),'bortus-terminal-chrome-'));
 chrome=spawn(process.argv[3],['--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-networking','about:blank'],{stdio:'ignore',windowsHide:true});report.ownedProcesses.chromePid=chrome.pid;save();
 let port;await until(async()=>{try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];return !!port;}catch{return false;}},'Owned Chrome startup timeout',15000);
 browser=await chromium.connectOverCDP('http://127.0.0.1:'+port,{noDefaults:true});report.browserVersion=browser.version();
 const context=browser.contexts()[0],page=context.pages()[0];await page.setViewportSize({width:390,height:844});
 const cdp=await context.newCDPSession(page);await cdp.send('Network.enable');await cdp.send('Performance.enable');
 let pending=new Map(),cached=new Set(),scripts=[];
 cdp.on('Network.requestServedFromCache',row=>cached.add(row.requestId));
 cdp.on('Network.responseReceived',row=>{const path=new URL(row.response.url).pathname;if(row.type==='Script'&&path.startsWith('/_next/static/'))pending.set(row.requestId,{path,status:row.response.status,fromDiskCache:!!row.response.fromDiskCache,cacheControl:row.response.headers['Cache-Control']??row.response.headers['cache-control']});});
 cdp.on('Network.loadingFinished',row=>{const script=pending.get(row.requestId);if(script){scripts.push({...script,servedFromCache:cached.has(row.requestId),encodedDataLength:row.encodedDataLength});pending.delete(row.requestId);cached.delete(row.requestId);}});
 const api=async()=>{const response=await fetch(state.writerUrl+'/__fixture/status',{signal:AbortSignal.timeout(10000)});assert.equal(response.status,200);return response.json();};
 await page.goto(state.writerUrl+'/pods');const trigger=page.getByRole('button',{name:'Actions for large-pod-0',exact:true});await trigger.waitFor();
 const before=await api();await trigger.click();await page.getByRole('menuitem',{name:'Execute Shell',exact:true}).click();await page.locator('.xterm').waitFor();
 const geometry=await page.locator('.xterm').evaluate(el=>{const r=el.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:innerWidth,height:innerHeight,focusInside:el.contains(document.activeElement)};});
 report.checks.push({name:'Actual first terminal initialized',geometry});save();
 if(tabDiagnostic){
  const input=page.getByRole('textbox',{name:'Command input for apps/large-pod-0',exact:true});await input.focus();await page.keyboard.press('Tab');
  report.tabEscaped=await input.evaluate(el=>el!==document.activeElement);save();assert(report.tabEscaped,'Terminal input trapped Tab navigation');
 }else{
 await page.getByTitle('Minimize',{exact:true}).click();await until(async()=>await page.locator('.xterm').count()===0,'Minimized private buffer was retained');
 if(reproduction){
  const restore=page.getByTitle('Restore apps/large-pod-0',{exact:true});
  const tag=await restore.evaluate(el=>({tag:el.tagName,tabIndex:el.tabIndex,role:el.getAttribute('role')}));
  assert.equal(tag.tag,'SPAN');assert.equal(tag.tabIndex,-1);
  const beforeClear=await page.evaluate(()=>sessionStorage.getItem('botrus-shells'));await page.getByTitle('Clear terminal',{exact:true}).click();
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('botrus-shells')),beforeClear);assert.equal(await page.locator('.xterm').count(),0);
  report.checks.push({name:'Mouse-only restore and inert minimized Clear reproduced; private terminal already disposed',restore:tag,noStateChange:true});
 }else{
  const region=page.getByRole('region',{name:'Terminal for apps/large-pod-0',exact:true});
  const restore=page.getByRole('button',{name:'Restore apps/large-pod-0 Shell',exact:true});assert.equal(await page.getByRole('button',{name:'Clear terminal',exact:true}).count(),0);
  await restore.focus();await page.keyboard.press('Enter');await region.waitFor();
  const input=page.getByRole('textbox',{name:'Command input for apps/large-pod-0',exact:true});await until(async()=>await input.evaluate(el=>el===document.activeElement),'Restored terminal input not focused');
  const fit=()=>region.evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth};});
  for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:844});await until(async()=>{const r=await fit();return r.left>=0&&r.right<=r.width&&r.top>=0&&r.bottom<=r.height&&r.scroll<=r.client;},'Terminal viewport fit failed');report.checks.push({name:'Viewport-bound terminal fits long Pods page',width,geometry:await fit()});}
  await page.setViewportSize({width:390,height:844});await input.focus();await page.keyboard.type('PUBLIC_UNSUBMITTED_PROBE');
  const hasProbe=()=>region.evaluate(el=>el.querySelector('.xterm-accessibility')?.textContent.includes('PUBLIC_UNSUBMITTED_PROBE')??false);
  await until(hasProbe,'Public unsent input was not exposed in accessibility supporting DOM');
  await region.getByRole('button',{name:'Clear terminal',exact:true}).click();await until(async()=>!await hasProbe(),'Active Clear retained unsent input');assert(await input.evaluate(el=>el===document.activeElement));
  const separator=region.getByRole('separator',{name:'Terminal height',exact:true});await separator.focus();await page.keyboard.press('Home');assert.equal(await separator.getAttribute('aria-valuenow'),'20');await page.keyboard.press('ArrowUp');assert.equal(await separator.getAttribute('aria-valuenow'),'25');await page.keyboard.press('End');assert.equal(await separator.getAttribute('aria-valuenow'),'80');await page.keyboard.press('Home');
  report.checks.push({name:'Keyboard restore/input focus, active Clear erases unsent buffer, keyboard height20→25→80→20; minimized no fake Clear'});save();
  const second=page.getByRole('button',{name:'Actions for large-pod-1',exact:true});await second.click();await page.getByRole('menuitem',{name:'Execute Shell',exact:true}).click();
  await page.getByRole('textbox',{name:'Command input for apps/large-pod-1',exact:true}).waitFor();
  const switchFirst=page.getByRole('button',{name:'Switch to apps/large-pod-0 Shell',exact:true});await switchFirst.focus();await page.keyboard.press('Enter');await input.waitFor();assert(await input.evaluate(el=>el===document.activeElement));
  await page.getByRole('button',{name:'Close apps/large-pod-1',exact:true}).click();await region.getByRole('button',{name:'Minimize terminal',exact:true}).click();await until(async()=>await restore.evaluate(el=>el===document.activeElement),'Minimize did not focus restore');await page.keyboard.press('Enter');await input.waitFor();assert(!await hasProbe());
  await region.getByRole('button',{name:'Close shell',exact:true}).click();await until(async()=>await trigger.evaluate(el=>el===document.activeElement),'Close did not return to originating Actions button');
  report.checks.push({name:'Keyboard switches two terminals; private buffers dispose on minimize/switch; close returns connected pod origin'});save();
  const open=async()=>{await trigger.click();await page.getByRole('menuitem',{name:'Execute Shell',exact:true}).click();await input.waitFor();};
  await open();const rootCdp=await browser.newBrowserCDPSession(),window=await cdp.send('Browser.getWindowForTarget');
  await page.evaluate(()=>{globalThis.terminalVisibility=[];document.addEventListener('visibilitychange',()=>globalThis.terminalVisibility.push(document.visibilityState));});
  await rootCdp.send('Browser.setWindowBounds',{windowId:window.windowId,bounds:{windowState:'minimized'}});await until(async()=>await page.evaluate(()=>document.visibilityState==='hidden'),'Genuine hidden prerequisite failed');
  await until(async()=>await page.locator('.xterm').count()===0,'Hidden terminal buffer survived');assert.equal(await page.evaluate(()=>sessionStorage.getItem('botrus-shells')),null);const hiddenBefore=await api();await pause(11000);const hiddenAfter=await api();assert.deepEqual(hiddenAfter.requests,hiddenBefore.requests);
  await rootCdp.send('Browser.setWindowBounds',{windowId:window.windowId,bounds:{windowState:'normal'}});await until(async()=>await page.evaluate(()=>document.visibilityState==='visible'),'Visible restoration failed');assert.equal(await page.locator('.xterm').count(),0);
  report.checks.push({name:'Actual minimized hidden event disposes terminal, clears identity storage and starts zero11s polling; restoration does not resurrect',events:await page.evaluate(()=>globalThis.terminalVisibility)});save();
  await open();await page.getByRole('link',{name:'Provisioning',exact:true}).click();await until(async()=>await page.locator('.xterm').count()===0&&await page.evaluate(()=>sessionStorage.getItem('botrus-shells'))===null,'Navigation retained terminal');await page.goto(state.writerUrl+'/pods');await trigger.waitFor();await open();
  report.profile={width:390,height:844,cpuRate:4,latencyMs:150,downloadBytesPerSecond:200000,uploadBytesPerSecond:93750,pairs:3};report.samples=[];
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});await cdp.send('Network.setBypassServiceWorker',{bypass:true});await cdp.send('Network.emulateNetworkConditionsByRule',{offline:false,matchedNetworkConditions:[{urlPattern:'',latency:150,downloadThroughput:200000,uploadThroughput:93750,connectionType:'cellular3g'}]});
  await page.addInitScript(()=>{globalThis.terminalLcp=[];new PerformanceObserver(list=>{for(const row of list.getEntries())globalThis.terminalLcp.push({startTime:row.startTime,renderTime:row.renderTime,loadTime:row.loadTime,size:row.size});}).observe({type:'largest-contentful-paint',buffered:true});});
  const metric=async()=>Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.filter(row=>['TaskDuration','ScriptDuration','LayoutDuration','RecalcStyleDuration'].includes(row.name)).map(row=>[row.name,row.value]));
  const delta=(a,b)=>Object.fromEntries(Object.keys(b).map(key=>[key,(b[key]-a[key])*1000]));
  for(let pair=0;pair<3;pair++)for(const cache of ['cold','warm']){
   report.phase={pair,cache};save();await page.goto('about:blank');if(cache==='cold')await cdp.send('Network.clearBrowserCache');pending=new Map();cached=new Set();scripts=[];const initialBefore=await metric();await page.goto(state.writerUrl+'/pods',{waitUntil:'load'});await trigger.waitFor();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   const initial={scripts:[...scripts],rendererDurationMs:delta(initialBefore,await metric()),lcp:await page.evaluate(()=>globalThis.terminalLcp.at(-1)??null)};assert(initial.lcp);await trigger.click();const item=page.getByRole('menuitem',{name:'Execute Shell',exact:true});await item.waitFor();
   const index=scripts.length,interactionBefore=await metric();await page.evaluate(()=>{globalThis.terminalTiming={};document.addEventListener('click',()=>{globalThis.terminalTiming.clickAt=performance.now();const observer=new MutationObserver(()=>{if(document.querySelector('.xterm')){observer.disconnect();requestAnimationFrame(()=>{globalThis.terminalTiming.visibleAt=performance.now();});}});observer.observe(document.body,{childList:true,subtree:true});},{capture:true,once:true});});await item.click();await input.waitFor();await until(async()=>await input.evaluate(el=>el===document.activeElement),'Measured terminal input focus absent');await until(async()=>await page.evaluate(()=>Number.isFinite(globalThis.terminalTiming.visibleAt)),'Terminal frame timing unavailable');
   const interaction={scripts:scripts.slice(index),rendererDurationMs:delta(interactionBefore,await metric()),clickToFirstTerminalFrameMs:await page.evaluate(()=>globalThis.terminalTiming.visibleAt-globalThis.terminalTiming.clickAt),geometry:await fit()};assert(interaction.scripts.length>0);assert(interaction.scripts.every(row=>!initial.scripts.some(before=>before.path===row.path)));assert(interaction.geometry.bottom<=844&&interaction.geometry.top>=0&&interaction.geometry.scroll<=interaction.geometry.client);
   for(const rows of [initial.scripts,interaction.scripts]){assert(rows.every(row=>row.status===200&&row.cacheControl?.includes('immutable')));if(cache==='warm')assert(rows.every(row=>(row.fromDiskCache||row.servedFromCache)&&row.encodedDataLength===0));}
   report.samples.push({pair,cache,initial,interaction});save();
  }
  report.files=[];const staticRoot=resolve('.next/static');for(const path of new Set(report.samples.flatMap(sample=>[...sample.initial.scripts,...sample.interaction.scripts].map(row=>row.path)))){const target=resolve(staticRoot,decodeURIComponent(path.slice('/_next/static/'.length)));assert(target.startsWith(staticRoot+sep));const bytes=await readFile(target);report.files.push({path,sha256:createHash('sha256').update(bytes).digest('hex'),rawBytes:bytes.length,gzipBytes:gzipSync(bytes).length,brotliBytes:brotliCompressSync(bytes).length});}
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:1});report.checks.push({name:'Six actual terminal cold/warm fixed-mobile samples: separate initial/deferred bytes, LCP/renderer durations and click/frame/focus; warm disk OR memory cache zero-wire'});save();
  const axePath='C:/Users/james/AppData/Local/BORTUS/qa-tools/axe-core-4.14.0/axe.min.js',axeBytes=await readFile(axePath);assert.equal(createHash('sha256').update(axeBytes).digest('hex'),'20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878');await page.addScriptTag({path:axePath});
  const scan=await region.evaluate(async el=>{const r=await axe.run(el);return {passes:r.passes.length,violations:r.violations.map(row=>({id:row.id,impact:row.impact,helpUrl:row.helpUrl,targets:row.nodes.map(node=>node.target)})),incomplete:r.incomplete.map(row=>({id:row.id,impact:row.impact,helpUrl:row.helpUrl,targets:row.nodes.map(node=>node.target)}))};});report.axe=scan;
  report.contrastReview=await region.evaluate(el=>{
   const rgb=color=>{const values=color.match(/[\d.]+/g)?.map(Number)??[];return values.length>=3?[values[0],values[1],values[2],values[3]??1]:null;};
   const luminance=rgb=>rgb.slice(0,3).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
   return [...el.querySelectorAll('.xterm-rows span')].filter(node=>node.textContent?.trim()).slice(0,200).map(node=>{const style=getComputedStyle(node),fg=rgb(style.color),box=node.getBoundingClientRect();let ancestor=node,bg;while(ancestor&&!bg){const color=rgb(getComputedStyle(ancestor).backgroundColor);if(color?.[3]===1)bg=color;ancestor=ancestor.parentElement;}const alpha=fg?.[3]??1,composite=fg&&bg?fg.slice(0,3).map((v,i)=>v*alpha+bg[i]*(1-alpha)):null;const a=composite?luminance(composite):null,b=bg?luminance(bg):null;return {foreground:style.color,background:bg,fontSize:style.fontSize,opacity:style.opacity,ratio:a!==null&&b!==null?(Math.max(a,b)+.05)/(Math.min(a,b)+.05):null,visible:box.width>0&&box.height>0&&box.bottom>0&&box.top<innerHeight};});
  });save();assert.equal(scan.violations.length,0,'Terminal axe violations');
  const ax=await cdp.send('Accessibility.getFullAXTree');report.accessibleApi={namedInput:ax.nodes.some(node=>node.role?.value==='textbox'&&node.name?.value==='Command input for apps/large-pod-0'),namedRegion:ax.nodes.some(node=>node.role?.value==='region'&&node.name?.value==='Terminal for apps/large-pod-0'),supportingDOM:await region.locator('.xterm-accessibility').count()};assert(report.accessibleApi.namedInput&&report.accessibleApi.namedRegion);report.limitations=['Accessible API and xterm supporting DOM plus scoped axe/manual keyboard are not an actual NVDA/Narrator/VoiceOver pass','Renderer elapsed duration counters and local buffered LCP are contribution observations, not before/after speed or total host CPU proof','Offline gzip/Brotli exact chunk estimates differ from actual response wire bytes; browser cache may be disk or memory'];
  await page.screenshot({path:'../../docs/implementation-evidence/terminal-mobile.png'});
  const withdraw=await fetch(state.writerUrl+'/__fixture/native-control',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'withdraw-admin'})});assert.equal(withdraw.status,204);await until(async()=>await page.locator('.xterm').count()===0,'Fresh permission withdrawal retained terminal',20000);
  report.checks.push({name:'Navigation and fresh admin withdrawal dispose terminal; accessible API names and scoped pinned axe reviewed',axe:scan,accessibleApi:report.accessibleApi});save();
 }
 }
 const after=await api();assert(!Object.entries(after.requests).some(([key,count])=>/^POST \/api\/cluster\/(kubectl|pods\/.*\/exec)/.test(key)&&count>(before.requests[key]??0)),'Terminal inspection submitted command');report.noCommandSubmitted=true;
}catch(error){report.failures.push(error instanceof Error?error.message:'Fixed terminal harness failure');process.exitCode=1;}
finally{
 if(browser){try{const s=await browser.newBrowserCDPSession();await s.send('Browser.close');}catch{}await browser.close().catch(()=>{});}await closed(chrome);if(chrome&&chrome.exitCode===null&&chrome.signalCode===null){chrome.kill();await closed(chrome);}
 if(!fixture.stdin.destroyed)fixture.stdin.write('stop\n');await closed(fixture);if(fixture.exitCode===null&&fixture.signalCode===null){fixture.kill();await closed(fixture);}
 report.cleanup={chromeExitCode:chrome?.exitCode??null,chromeSignal:chrome?.signalCode??null,fixtureExitCode:fixture.exitCode,fixtureSignal:fixture.signalCode};report.completedAt=new Date().toISOString();report.terminal=true;save();
}
