import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const { chromium } = createRequire(import.meta.url)(process.argv[2]);
const reportPath = '../../docs/implementation-evidence/flux-zoom-browser.json';
const report = { startedAt: new Date().toISOString(), scope: 'Actual disposable local Flux routes, real chrome.tabs zoom, owned existing bundled Chromium/profile; no viewport/DPR/CSS zoom emulation', checks: [], failures: [], terminal: false };
const save = () => writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function until(check, message, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await check()) return; await pause(100); }
  throw Error(message);
}
const fixture = spawn(process.execPath, ['node_modules/tsx/dist/cli.mjs', 'tests/ui-fixture.ts'], { env: { ...process.env, BORTUS_UI_FLUX_FIXTURE: 'true' }, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
report.ownedProcesses = { fixturePid: fixture.pid };
let browser, chrome;
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
    if(target.protocol!=='http:' || target.hostname!=='127.0.0.1' || !target.pathname.startsWith('/flux') || ![1,2].includes(factor)) throw Error('Only local Flux fixture zoom is permitted');
    const tabs = await chrome.tabs.query({url:target.origin+'/flux*'});
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
  await page.goto(state.writerUrl + '/flux');
  await until(async () => await page.locator('[data-flux-repository]').count() === 100 && await page.getByRole('button', { name: 'Add Repository', exact: true }).count() === 1, 'Actual hierarchy/admin did not load');
  const ownedWorker = worker => worker.url().startsWith('chrome-extension://') && worker.url().endsWith('/background.js');
  await until(async () => context.serviceWorkers().some(ownedWorker), 'Owned extension service worker unavailable');
  const worker = context.serviceWorkers().find(ownedWorker);
  report.extension.workerUrl = worker.url();
  await until(async () => worker.evaluate(() => typeof globalThis.fixtureZoom === 'function'), 'Owned extension zoom helper initialization failed');
  const dimensions = () => page.evaluate(() => ({ cssWidth: innerWidth, cssHeight: innerHeight, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, devicePixelRatio, outerWidth, outerHeight }));
  const setZoom = factor => worker.evaluate(input => globalThis.fixtureZoom(input), { url: state.writerUrl + '/flux', factor });
  assert.equal((await setZoom(1)).after.factor, 1);
  const before = await dimensions();
  const actual = await setZoom(2);
  await until(async () => (await dimensions()).cssWidth < before.cssWidth * 0.6, 'Real browser zoom did not reduce CSS viewport');
  const after = await dimensions();
  assert.equal(actual.after.factor, 2); assert.deepEqual(actual.after.window, actual.before.window);
  assert(after.scrollWidth <= after.clientWidth, 'Hierarchy escaped real2x CSS viewport');
  assert(Math.abs(after.devicePixelRatio / before.devicePixelRatio - 2) < 0.02);
  report.checks.push({ name: 'Real tabs.setZoom/getZoom factor2 with unchanged window geometry and reduced CSS viewport; hierarchy reflow fits', actual, before, after }); save();
  await page.getByRole('button', { name: 'Add Repository', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Add Git Repository', exact: true }); await dialog.waitFor();
  const dialogFit = await dialog.evaluate(element => { const box = element.getBoundingClientRect(); return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, viewport: innerWidth, height: innerHeight, focusInside: element.contains(document.activeElement) }; });
  assert(dialogFit.left >= 0 && dialogFit.right <= after.cssWidth && dialogFit.top >= 0 && dialogFit.bottom <= after.cssHeight && dialogFit.focusInside);
  const cancel = dialog.getByRole('button', { name: 'Cancel', exact: true });
  let keyboardReachedCancel = false;
  for (let index = 0; index < 30; index++) {
    await page.keyboard.press('Tab'); assert(await dialog.evaluate(element => element.contains(document.activeElement)));
    if (await cancel.evaluate(element => element === document.activeElement)) { keyboardReachedCancel = true; break; }
  }
  assert(keyboardReachedCancel, 'Bottom dialog action was unreachable with the keyboard at real2x zoom');
  const actionFit = await cancel.evaluate(element => { const box = element.getBoundingClientRect(); return { top: box.top, bottom: box.bottom, height: innerHeight }; });
  assert(actionFit.top >= 0 && actionFit.bottom <= actionFit.height, 'Focused bottom dialog action was clipped');
  await page.screenshot({ path: '../../docs/implementation-evidence/flux-zoom-dialog.png' });
  await page.keyboard.press('Enter');
  assert(await page.getByLabel('Search repositories and descendants').evaluate(element => element === document.activeElement));
  report.checks.push({ name: 'Real2x dialog fits, keyboard stays contained and reaches visible bottom action, Cancel returns focus', dialogFit, keyboardReachedCancel, actionFit }); save();
  await page.getByLabel('Search repositories and descendants').fill('sort-repo-0');
  await until(async () => await page.getByRole('link', { name: 'sort-repo-0', exact: true }).count() === 1, 'Search did not expose the exact owned repository link');
  const link = page.getByRole('link', { name: 'sort-repo-0', exact: true }); await link.focus(); await page.keyboard.press('Enter');
  await until(async () => await page.getByRole('region', { name: 'Bundles', exact: true }).locator('tbody tr').count() === 100, 'Real2x child table did not load');
  const detail = await dimensions(); assert(detail.scrollWidth <= detail.clientWidth, 'Real2x child overflow escaped local table');
  await page.screenshot({ path: '../../docs/implementation-evidence/flux-zoom-detail.png' });
  report.checks.push({ name: 'Real2x dialog focus/keyboard/fit and close return; keyboard child link and100-row local table fit', dialogFit, detail });
  const restored = await setZoom(1); assert.equal(restored.after.factor, 1);
  const status = await (await fetch(state.writerUrl + '/__fixture/status')).json();
  assert.equal(status.valueRequests, 0); assert(!Object.keys(status.requests).some(key => /^(POST|PUT|PATCH|DELETE) \/api\/flux/.test(key)));
  report.requests = status.requests; report.restored = restored; save();
} catch (error) { report.failures.push(error instanceof Error ? error.message : String(error)); process.exitCode = 1;
} finally {
  if (browser) { try { const session = await browser.newBrowserCDPSession(); await session.send('Browser.close'); } catch { /* Browser may disconnect before close acknowledgement. */ } await browser.close().catch(() => {}); }
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) await Promise.race([once(chrome, 'exit'), pause(15000)]);
  if (fixture.exitCode === null && fixture.signalCode === null) { fixture.stdin.write('stop\n'); await Promise.race([once(fixture, 'exit'), pause(30000)]); }
  report.cleanup = { chromeExitCode: chrome?.exitCode, chromeSignal: chrome?.signalCode, fixtureExitCode: fixture.exitCode, fixtureSignal: fixture.signalCode };
  if ((chrome && chrome.exitCode === null && chrome.signalCode === null) || (fixture.exitCode === null && fixture.signalCode === null)) { report.failures.push('Owned process failed to terminate normally'); process.exitCode = 1; }
  report.terminal = true; report.completedAt = new Date().toISOString(); save(); console.log(JSON.stringify({ checks: report.checks.length, failures: report.failures, cleanup: report.cleanup }));
}
