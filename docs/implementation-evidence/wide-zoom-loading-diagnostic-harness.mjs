import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const localRequire=createRequire(import.meta.url);
const { chromium } = localRequire(process.argv[2]);
const {PNG}=localRequire(join(process.argv[2],'../playwright-core/lib/utilsBundle.js'));
const reportPath = '../../docs/implementation-evidence/wide-zoom-browser.json';
const report = { startedAt: new Date().toISOString(), scope: 'Actual disposable local application routes, real chrome.tabs zoom, owned existing bundled Chromium/profile; no viewport/DPR/CSS zoom emulation', checks: [], failures: [], terminal: false };
const save = () => writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function until(check, message, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await check()) return; await pause(100); }
  throw Error(message);
}
const fixture = spawn(process.execPath, ['node_modules/tsx/dist/cli.mjs', 'tests/ui-fixture.ts'], { env: { ...process.env, BORTUS_UI_NATIVE_FIXTURE: 'true', BORTUS_UI_KV_FIXTURE: 'true', BORTUS_UI_KV_GUARDED_FIXTURE: 'true', BORTUS_UI_PRODUCTION_ASSETS_FIXTURE: 'true' }, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
report.ownedProcesses = { fixturePid: fixture.pid };
let browser, chrome, releaseHeld;
try {
  const state = await new Promise((resolve, reject) => {
    let output = ''; const timer = setTimeout(() => reject(Error('Local fixture startup timed out')), 45000);
    fixture.once('exit', () => { clearTimeout(timer); reject(Error('Local fixture exited before ready')); });
    fixture.stdout.on('data', chunk => { output = (output + chunk).slice(-65536); const match = output.match(/UI_FIXTURE_READY (\{[^\n]+\})/); if (match) { clearTimeout(timer); resolve(JSON.parse(match[1])); } });
    fixture.stderr.on('data', () => {});
  });
  const profile = await mkdtemp(join(tmpdir(), 'bortus-flux-zoom-chrome-'));
  const extension = join(profile, 'fixture-zoom-extension'); await mkdir(extension);
  const manifest = JSON.stringify({ manifest_version: 3, name: 'BORTUS local fixture browser zoom', version: '1.0.0', host_permissions: ['http://127.0.0.1/*'], background: { service_worker: 'background.js' } }, null, 2) + '\n';
  const workerSource = `globalThis.fixtureZoom = async ({url,factor}) => {
    const target = new URL(url);
    if(target.protocol!=='http:' || target.hostname!=='127.0.0.1' || !['/pods','/deploy','/secrets/kv'].includes(target.pathname) || ![1,2].includes(factor)) throw Error('Only local application fixture zoom is permitted');
    const tabs = await chrome.tabs.query({url:target.origin+'/*'});
    if(tabs.length!==1 || !Number.isInteger(tabs[0].id)) throw Error('Expected one owned fixture tab');
    const tab=tabs[0];
    const geometry=async()=>{const w=await chrome.windows.get(tab.windowId);return {left:w.left,top:w.top,width:w.width,height:w.height,state:w.state};};
    const before={factor:await chrome.tabs.getZoom(tab.id),window:await geometry()};
    await chrome.tabs.setZoomSettings(tab.id,{mode:'automatic',scope:'per-tab'});
    await chrome.tabs.setZoom(tab.id,factor);
    return {before,after:{factor:await chrome.tabs.getZoom(tab.id),window:await geometry()}};
  };
  chrome.runtime.onInstalled.addListener(()=>{});\n`;
  await writeFile(join(extension, 'manifest.json'), manifest); await writeFile(join(extension, 'background.js'), workerSource);
  report.extension = { hostScope: 'http://127.0.0.1/*', noContentScriptsOrStorage: true, manifestSha256: createHash('sha256').update(manifest).digest('hex'), workerSha256: createHash('sha256').update(workerSource).digest('hex') };
  chrome = spawn(process.argv[3], ['--remote-debugging-port=0', '--user-data-dir=' + profile, '--disable-extensions-except=' + extension, '--load-extension=' + extension, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--window-size=1000,900', 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  report.ownedProcesses.chromePid = chrome.pid; save();
  let port;
  await until(async () => { try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return !!port; } catch { return false; } }, 'Owned bundled Chromium CDP startup failed', 15000);
  browser = await chromium.connectOverCDP('http://127.0.0.1:' + port, { noDefaults: true });
  report.browserVersion = browser.version();
  const context = browser.contexts()[0], page = context.pages()[0];

  const cdp=await context.newCDPSession(page);
  await page.goto(state.writerUrl+'/pods');
  const ownedWorker=worker=>worker.url().startsWith('chrome-extension://')&&worker.url().endsWith('/background.js');
  await until(async()=>context.serviceWorkers().some(ownedWorker),'Owned zoom extension unavailable');
  const worker=context.serviceWorkers().find(ownedWorker);await until(async()=>worker.evaluate(()=>typeof globalThis.fixtureZoom==='function'),'Zoom helper not ready');
  const dimensions=()=>page.evaluate(()=>({cssWidth:innerWidth,cssHeight:innerHeight,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio,outerWidth,outerHeight}));
  const zoom=factor=>worker.evaluate(input=>globalThis.fixtureZoom(input),{url:page.url(),factor});
  await zoom(1);const before=await dimensions();const actual=await zoom(2);await until(async()=>(await dimensions()).cssWidth<before.cssWidth*.6,'Real zoom did not reduce CSS viewport');const after=await dimensions();assert.equal(actual.after.factor,2);assert.deepEqual(actual.before.window,actual.after.window);assert(Math.abs(after.dpr/before.dpr-2)<.02);
  await page.setContent('<style>html,body{margin:0;background:white}i{position:fixed;width:20px;height:20px}#a{top:0;left:0;background:#ff0000}#b{top:0;right:0;background:#00ff00}#c{bottom:0;left:0;background:#0000ff}#d{bottom:0;right:0;background:#ffff00}</style><i id=a></i><i id=b></i><i id=c></i><i id=d></i>');
  const layout=await cdp.send('Page.getLayoutMetrics');report.preflight={before,after,actual,layout:{layoutViewport:layout.layoutViewport,cssLayoutViewport:layout.cssLayoutViewport},attempts:[]};let capture;
  for(const method of ['legacyClip','cssClipScale2','default']){
    const options={format:'png',captureBeyondViewport:false,fromSurface:true};
    if(method==='legacyClip')options.clip={x:0,y:0,width:layout.layoutViewport.clientWidth,height:layout.layoutViewport.clientHeight,scale:1};
    if(method==='cssClipScale2')options.clip={x:0,y:0,width:layout.cssLayoutViewport.clientWidth,height:layout.cssLayoutViewport.clientHeight,scale:2};
    const bytes=Buffer.from((await cdp.send('Page.captureScreenshot',options)).data,'base64'),png=PNG.sync.read(bytes);
    const pixel=(x,y)=>[...png.data.subarray((y*png.width+x)*4,(y*png.width+x)*4+3)];
    const corners=[pixel(5,5),pixel(png.width-6,5),pixel(5,png.height-6),pixel(png.width-6,png.height-6)];
    const whole=JSON.stringify(corners)===JSON.stringify([[255,0,0],[0,255,0],[0,0,255],[255,255,0]]);
    report.preflight.attempts.push({method,width:png.width,height:png.height,corners,whole});save();
    if(whole){capture=method;await writeFile('../../docs/implementation-evidence/wide-zoom-preflight.png',bytes);break;}
  }
  assert(capture,'No full-surface zoom screenshot method passed four-corner preflight');report.checks.push({name:'Actual2x zoom, unchanged browser window and public four-corner full-surface screenshot preflight',capture});save();
  async function screenshot(name){const metrics=await cdp.send('Page.getLayoutMetrics'),options={format:'png',captureBeyondViewport:false,fromSurface:true};if(capture==='legacyClip')options.clip={x:0,y:0,width:metrics.layoutViewport.clientWidth,height:metrics.layoutViewport.clientHeight,scale:1};if(capture==='cssClipScale2')options.clip={x:0,y:0,width:metrics.cssLayoutViewport.clientWidth,height:metrics.cssLayoutViewport.clientHeight,scale:2};const bytes=Buffer.from((await cdp.send('Page.captureScreenshot',options)).data,'base64');const png=PNG.sync.read(bytes);await writeFile('../../docs/implementation-evidence/'+name+'.png',bytes);return {width:png.width,height:png.height,capture};}
  const fit=element=>element.evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,focusInside:el.contains(document.activeElement)};});
  const inspectModal=async(dialog,name,trigger)=>{await dialog.waitFor();const box=await fit(dialog);assert(box.left>=0&&box.right<=box.width&&box.top>=0&&box.bottom<=box.height&&box.focusInside);for(let n=0;n<24;n++){await page.keyboard.press(n%2?'Shift+Tab':'Tab');assert(await dialog.evaluate(el=>el.contains(document.activeElement)));}const image=await screenshot(name);await dialog.getByRole('button',{name:'Close dialog',exact:true}).click();await until(async()=>trigger.evaluate(el=>el===document.activeElement),'Realzoom modal focus return failed');return {box,image};};
  if(process.argv[4]!=='loading-diagnostic'){
  await page.goto(state.writerUrl+'/deploy');await zoom(2);const deleteJob=page.getByRole('button',{name:'Delete job completed-ui-job',exact:true});await deleteJob.waitFor();await deleteJob.click();report.checks.push({name:'Real2x provisioning confirmation fits and keyboard/close focus return without mutation',...await inspectModal(page.getByRole('dialog',{name:'Delete job history',exact:true}),'wide-zoom-provisioning',deleteJob)});save();
  await page.goto(state.writerUrl+'/secrets/kv');await zoom(2);await page.getByRole('button',{name:'Next paths page',exact:true}).waitFor();const path=page.getByRole('button',{name:'Open KV path services/api',exact:true});for(let n=0;n<3&&!await path.count();n++){await page.getByRole('button',{name:'Next paths page',exact:true}).click();await until(async()=>await path.count()||!await page.getByRole('button',{name:'Next paths page',exact:true}).isDisabled(),'Path page unavailable');}await path.click();const values=page.getByRole('button',{name:'Values and versions',exact:true});await until(async()=>!await values.isDisabled(),'Fresh workbench permission unavailable');await values.click();const dialog=page.getByRole('dialog');report.checks.push({name:'Real2x selected KV metadata workbench fits and keyboard/close focus return; no reveal',...await inspectModal(dialog,'wide-zoom-workbench',values)});save();
  }
  await page.goto(state.writerUrl+'/pods');await zoom(2);const actions=page.getByRole('button',{name:'Actions for large-pod-0',exact:true});await actions.waitFor();const chunkManifest=JSON.parse(await readFile('.next/react-loadable-manifest.json','utf8'));const item=Object.entries(chunkManifest).find(([key])=>key.endsWith('-> @/components/cluster/kubectl-shell'));assert(item);const chunk=item[1].files.find(name=>name.endsWith('.js'));let held,release;const gate=new Promise(resolve=>release=resolve);releaseHeld=release;
  await context.route('**/_next/'+chunk,async route=>{held=true;await gate;try{await route.continue();}catch{}});await actions.click();await page.getByRole('menuitem',{name:'Execute Shell',exact:true}).click();const loading=page.getByRole('status').filter({hasText:'Loading terminal…'});await loading.waitFor();await until(async()=>held,'Deferred JS was not held');const loadingFit=await fit(loading);report.loadingDiagnostic={loadingFit,precise:await page.evaluate(()=>({visual:visualViewport?{width:visualViewport.width,height:visualViewport.height,offsetLeft:visualViewport.offsetLeft,offsetTop:visualViewport.offsetTop}:null,innerWidth,innerHeight,clientWidth:document.documentElement.clientWidth,clientHeight:document.documentElement.clientHeight}))};report.loadingImage=await screenshot('wide-zoom-loading');save();assert(loadingFit.top>=0&&loadingFit.bottom<=loadingFit.height);release();const input=page.getByRole('textbox',{name:'Command input for apps/large-pod-0',exact:true});await input.waitFor();await context.unroute('**/_next/'+chunk);await until(async()=>input.evaluate(el=>el===document.activeElement),'Realzoom input focus missing');const terminal=page.getByRole('region',{name:'Terminal for apps/large-pod-0',exact:true}),terminalFit=await fit(terminal);assert(terminalFit.left>=0&&terminalFit.right<=terminalFit.width&&terminalFit.top>=0&&terminalFit.bottom<=terminalFit.height);await page.keyboard.press('Tab');assert(await input.evaluate(el=>el!==document.activeElement));await terminal.getByRole('button',{name:'Clear terminal',exact:true}).click();const terminalImage=await screenshot('wide-zoom-terminal');await terminal.getByRole('button',{name:'Close shell',exact:true}).click();await until(async()=>actions.evaluate(el=>el===document.activeElement),'Realzoom terminal close focus return failed');report.checks.push({name:'Real2x held deferred terminal JS shows fitted loading status, then focused named input/Tab escape/Clear/close return',loadingFit,terminalFit,image:terminalImage});
  const status=await(await fetch(state.writerUrl+'/__fixture/status')).json();assert.equal(status.valueRequests,0);assert(!Object.keys(status.requests).some(key=>/^(POST|PUT|PATCH|DELETE) \/api\//.test(key)));report.requests=status.requests;report.limitations=['Real tabs zoom and full-surface capture are local synthetic evidence, not field/AT/realrunner proof','No private fields/tokens/output/DOM attributes collected; terminal remained an unsubmitted command runner'];await zoom(1);save();
} catch (error) { report.failures.push(error instanceof Error ? error.message : String(error)); process.exitCode = 1;
} finally {
  releaseHeld?.();
  if (browser) { try { const session = await browser.newBrowserCDPSession(); await session.send('Browser.close'); } catch { /* Browser may disconnect before close acknowledgement. */ } await browser.close().catch(() => {}); }
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) await Promise.race([once(chrome, 'exit'), pause(15000)]);
  if (fixture.exitCode === null && fixture.signalCode === null) { fixture.stdin.write('stop\n'); await Promise.race([once(fixture, 'exit'), pause(30000)]); }
  report.cleanup = { chromeExitCode: chrome?.exitCode, chromeSignal: chrome?.signalCode, fixtureExitCode: fixture.exitCode, fixtureSignal: fixture.signalCode };
  if ((chrome && chrome.exitCode === null && chrome.signalCode === null) || (fixture.exitCode === null && fixture.signalCode === null)) { report.failures.push('Owned process failed to terminate normally'); process.exitCode = 1; }
  report.terminal = true; report.completedAt = new Date().toISOString(); save(); console.log(JSON.stringify({ checks: report.checks.length, failures: report.failures, cleanup: report.cleanup }));
}
