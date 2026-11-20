import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdtemp, readFile } from 'node:fs/promises';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const evidencePath = '../../docs/implementation-evidence/flux-browser.json';
const progressPath = '../../docs/implementation-evidence/flux-browser-progress.json';
const evidence = { startedAt: new Date().toISOString(), fixture: 'Actual disposable production routes, SQLite, bounded metadata-only fake CLI; no production cluster', checks: [], failures: [], terminal: false };
if (process.argv[4]) {
  const scannerHash = createHash('sha256').update(await readFile(process.argv[4])).digest('hex');
  assert.equal(scannerHash, '20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878', 'Pinned axe scanner bytes differ');
  evidence.scanner = { name: 'axe-core', version: '4.14.0', sha256: scannerHash, source: 'https://registry.npmjs.org/axe-core/4.14.0', registryIntegrityVerified: true, registrySignaturesVerified: false, packageScriptsExecuted: false };
}
const mark = (name, metadata = {}) => { evidence.checks.push({ name, recordedAt: Date.now(), ...metadata }); console.log('BROWSER_CHECK ' + name); writeFileSync(progressPath, JSON.stringify({ ...evidence, checkpointAt: new Date().toISOString() }, null, 2) + '\n'); };
const fixture = spawn(process.execPath, ['node_modules/tsx/dist/cli.mjs', 'tests/ui-fixture.ts'], { env: { ...process.env, BORTUS_UI_FLUX_FIXTURE: 'true' }, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
evidence.ownedProcesses = { fixturePid: fixture.pid };
let browser, chrome, state, ownedPage;
const browserReadEvents = [];
async function until(check, message, timeout = 22000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await check()) return; await new Promise(resolve => setTimeout(resolve, 100)); }
  throw Error(message);
}
const ready = new Promise((resolve, reject) => {
  let output = ''; const timer = setTimeout(() => reject(Error('Fixture startup timed out')), 45000);
  fixture.once('exit', () => { clearTimeout(timer); reject(Error('Fixture exited before ready')); });
  fixture.stdout.on('data', chunk => { output = (output + chunk).slice(-65536); const match = output.match(/UI_FIXTURE_READY (\{[^\n]+\})/); if (match) { clearTimeout(timer); resolve(JSON.parse(match[1])); } });
  fixture.stderr.on('data', () => {});
});
async function status() { return (await fetch(state.writerUrl + '/__fixture/status')).json(); }
async function control(action) {
  const response = await fetch(state.writerUrl + '/__fixture/flux-control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) });
  assert.equal(response.status, 204, 'Fixture control failed');
}
const rows = page => page.locator('[data-flux-repository]');
const names = page => rows(page).evaluateAll(items => items.map(item => item.getAttribute('data-flux-repository')));
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
try {
  state = await ready;
  const profile = await mkdtemp(join(tmpdir(), 'bortus-flux-chrome-'));
  chrome = spawn(process.argv[3], ['--remote-debugging-port=0', '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion', 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  evidence.ownedProcesses.chromePid = chrome.pid;
  let port;
  await until(async () => { try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return !!port; } catch { return false; } }, 'Owned Chrome CDP startup failed', 15000);
  browser = await chromium.connectOverCDP('http://127.0.0.1:' + port, { noDefaults: true });
  const context = browser.contexts()[0], page = context.pages()[0];
  await context.exposeBinding('__recordFluxRead', (_source, event) => {
    if (browserReadEvents.length < 2000) browserReadEvents.push(event);
  });
  ownedPage = page;
  await page.addInitScript(() => { window.__fluxVisibility = []; document.addEventListener('visibilitychange', () => window.__fluxVisibility.push(document.visibilityState)); });
  await page.addInitScript(() => {
    const original = window.fetch.bind(window), events = [], documents = [];
    try { const prior = sessionStorage.getItem('bortus-fixture-flux-read-events'); if (prior) documents.push(...JSON.parse(prior)); } catch { /* Diagnostic storage unavailable. */ }
    window.__fluxReadOwnership = events;
    let next = 0;
    const record = event => {
      if (events.length < 2000) events.push(event);
      void window.__recordFluxRead(event).catch(() => {});
      try { sessionStorage.setItem('bortus-fixture-flux-read-events', JSON.stringify([...documents, ...events].slice(-2000))); } catch { /* Only public read events; no data or credentials are saved. */ }
    };
    window.fetch = (input, init) => {
      const url = new URL(typeof input === 'string' ? input : input.url, location.href);
      if ((init?.method ?? 'GET') !== 'GET' || !url.pathname.startsWith('/api/flux/')) return original(input, init);
      const id = ++next, key = 'GET ' + url.pathname, at = Date.now();
      record({ id, key, event: 'start', at, documentStartedAt: performance.timeOrigin });
      init?.signal?.addEventListener('abort', () => record({ id, key, event: 'signal-abort', at: Date.now(), documentStartedAt: performance.timeOrigin }), { once: true });
      return original(input, init).then(response => { record({ id, key, event: 'headers', at: Date.now(), documentStartedAt: performance.timeOrigin }); return response; }, error => { record({ id, key, event: 'fetch-rejected', at: Date.now(), documentStartedAt: performance.timeOrigin }); throw error; });
    };
  });
  const windowControl = await context.newCDPSession(page);
  const { windowId } = await windowControl.send('Browser.getWindowForTarget');
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'minimized' } });
  await until(async () => await page.evaluate(() => document.visibilityState) === 'hidden', 'Real hidden visibility prerequisite failed', 5000);
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } });
  await page.bringToFront();
  await until(async () => await page.evaluate(() => document.visibilityState) === 'visible', 'Visible restoration prerequisite failed', 5000);
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(state.writerUrl + '/flux');
  await until(async () => await rows(page).count() === 100, 'Hierarchy did not render bounded first page');
  await until(async () => await page.getByRole('button', { name: 'Add Repository', exact: true }).count() === 1, 'Fresh administrator did not load');
  const pages = page.getByRole('navigation', { name: 'Repository pages' });
  await pages.getByRole('button', { name: 'Next', exact: true }).click(); assert.equal(await rows(page).count(), 100);
  await pages.getByRole('button', { name: 'Next', exact: true }).click(); assert.equal(await rows(page).count(), 1);
  await page.getByLabel('Search repositories and descendants').fill('sort-repo');
  await until(async () => await rows(page).count() === 5, 'Hierarchy search failed');
  await page.getByRole('button', { name: /^Sort by Last Sync/ }).click();
  assert.deepEqual(await names(page), ['sort-repo-4', 'sort-repo-0', 'sort-repo-3', 'sort-repo-1', 'sort-repo-2']);
  await page.getByRole('button', { name: /^Sort by Last Sync/ }).click();
  assert.deepEqual(await names(page), ['sort-repo-0', 'sort-repo-3', 'sort-repo-4', 'sort-repo-1', 'sort-repo-2']);
  mark('Hierarchy pages reach all 201 repositories; mixed valid/equal/null/invalid date sorting keeps unknowns last in both directions', { pageRows: [100, 100, 1] });
  const bounds = [];
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 900 });
    const size = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    assert(size.scroll <= size.client, 'Long hierarchy metadata escaped the viewport'); bounds.push({ width, ...size });
  }
  mark('Long branch/path/URL rows fit 320/390/768 CSS widths', { bounds });
  await page.setViewportSize({ width: 390, height: 900 });
  const repository = page.getByRole('link', { name: 'sort-repo-0', exact: true });
  await repository.focus(); await page.keyboard.press('Enter');
  const bundles = page.getByRole('region', { name: 'Bundles', exact: true });
  await until(async () => await bundles.locator('tbody tr').count() === 100, 'Bundle table failed to load');
  await bundles.getByRole('button', { name: /^Sort by Resources/ }).click();
  assert.match(await bundles.locator('tbody tr').first().textContent(), /fixture-bundle-0001/);
  assert.match(await bundles.locator('tbody tr').nth(1).textContent(), /fixture-bundle-0002/);
  await bundles.getByRole('button', { name: /^Sort by Name/ }).click();
  const bundle = bundles.getByRole('link', { name: 'fixture-bundle-0000', exact: true });
  await bundle.focus(); await page.keyboard.press('Enter');
  const inventory = page.getByRole('region', { name: 'Managed Resources', exact: true });
  await until(async () => await inventory.locator('tbody tr').count() === 100, 'Inventory first page failed');
  await inventory.getByRole('button', { name: 'Next', exact: true }).click(); assert.equal(await inventory.locator('tbody tr').count(), 100);
  await inventory.getByRole('button', { name: 'Next', exact: true }).click(); assert.equal(await inventory.locator('tbody tr').count(), 1);
  await inventory.getByRole('button', { name: 'Previous', exact: true }).click();
  await inventory.getByLabel('Search Managed Resources').fill('fixture-deployment-0200');
  assert.equal(await inventory.locator('tbody tr').count(), 1);
  assert.equal(await inventory.getByRole('link', { name: 'fixture-deployment-0200', exact: true }).getAttribute('href'), '/deployments/apps/fixture-deployment-0200');
  mark('Keyboard repository/bundle navigation and complete bounded inventory; counts2/10 sort numerically', { inventoryPageRows: [100, 100, 1] });
  await page.goto(state.writerUrl + '/flux'); await until(async () => await rows(page).count() > 0, 'Return hierarchy missing');
  await control('fail-hierarchy'); await page.getByRole('button', { name: 'Refresh Flux hierarchy' }).click();
  await page.getByRole('alert').filter({ hasText: 'Fixture Flux metadata unavailable' }).waitFor();
  assert(await rows(page).count() > 0); assert.equal(await page.getByText('No Git repositories in the current successful snapshot.').count(), 0);
  await control('restore-hierarchy'); await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await until(async () => await page.locator('main').getByRole('alert').count() === 0, 'Hierarchy recovery failed');
  mark('Failed hierarchy read retains labelled prior metadata; Retry recovers without false empty');
  await page.getByRole('button', { name: 'Add Repository', exact: true }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Name', { exact: true }).fill('synthetic-draft');
  await dialog.getByLabel('Authentication', { exact: true }).selectOption('https');
  await dialog.getByLabel('Personal Access Token', { exact: true }).fill('synthetic ephemeral test draft');
  const beforeHidden = await status();
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'minimized' } });
  await until(async () => await page.evaluate(() => document.visibilityState) === 'hidden', 'Form hide was not real');
  await until(async () => await page.getByRole('dialog').count() === 0, 'Hidden page retained private form');
  await pause(11000); const hiddenLater = await status();
  assert.equal(hiddenLater.requests['GET /api/flux/hierarchy'], beforeHidden.requests['GET /api/flux/hierarchy']);
  assert.equal(hiddenLater.requests['POST /api/flux/repos'], beforeHidden.requests['POST /api/flux/repos']);
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } }); await page.bringToFront();
  await until(async () => await page.getByRole('button', { name: 'Add Repository', exact: true }).count() === 1, 'Restore form control failed');
  await page.getByRole('button', { name: 'Add Repository', exact: true }).click();
  dialog = page.getByRole('dialog'); assert.equal(await dialog.getByLabel('Name', { exact: true }).inputValue(), '');
  assert.equal(await dialog.getByLabel('Personal Access Token', { exact: true }).count(), 0);
  await dialog.getByLabel('Authentication', { exact: true }).selectOption('https');
  await dialog.getByLabel('Personal Access Token', { exact: true }).fill('synthetic permission withdrawal draft');
  await control('withdraw-admin');
  await until(async () => await page.getByRole('dialog').count() === 0, 'Fresh administrator withdrawal retained credentials');
  assert.equal(await page.getByRole('button', { name: 'Add Repository', exact: true }).count(), 0);
  assert.equal((await status()).requests['POST /api/flux/repos'], beforeHidden.requests['POST /api/flux/repos']);
  await control('restore-admin'); await until(async () => await page.getByRole('button', { name: 'Add Repository', exact: true }).count() === 1, 'Administrator restoration failed');
  mark('Genuine hidden clears private form and stops hierarchy polls11s; fresh administrator withdrawal clears credentials without POST', { pollsWhileHidden: 0, visibility: await page.evaluate(() => window.__fluxVisibility) });
  await page.getByLabel('Search repositories and descendants').fill('sort-repo-0');
  await control('hold-sync'); await page.getByRole('button', { name: 'Sync sort-repo-0', exact: true }).click();
  await until(async () => (await status()).heldFluxReplies.includes('sync'), 'Actual sync reply hold missing');
  const syncCount = (await status()).requests['POST /api/flux/repos/gr-fixture-source-0/sync'];
  await control('withdraw-admin'); await until(async () => await page.getByRole('button', { name: 'Sync sort-repo-0', exact: true }).count() === 0, 'Pending sync owner survived permission loss');
  await control('release-replies'); await control('restore-admin');
  await until(async () => await page.getByRole('button', { name: 'Add Repository', exact: true }).count() === 1, 'Post-sync administrator restoration failed');
  assert.equal(await page.getByText(/^Reconciliation requested for sort-repo-0/).count(), 0);
  assert.equal((await status()).requests['POST /api/flux/repos/gr-fixture-source-0/sync'], syncCount);
  mark('Fresh permission loss fences a held accepted Sync reply without automatic retry');
  await page.getByLabel('Search repositories and descendants').fill('sort-repo-4');
  await control('hold-discovery'); await page.getByRole('button', { name: 'Remove sort-repo-4', exact: true }).click();
  dialog = page.getByRole('dialog'); assert(await dialog.getByRole('button', { name: 'Remove repository', exact: true }).isDisabled());
  await dialog.getByLabel('Type sort-repo-4 to confirm').fill('sort-repo-4');
  await dialog.getByRole('button', { name: 'Remove repository', exact: true }).click();
  await page.getByRole('dialog').getByText('running:', { exact: false }).first().waitFor();
  const deleteCount = (await status()).requests['DELETE /api/flux/repos/gr-fixture-source-4'];
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'minimized' } });
  await until(async () => await page.evaluate(() => document.visibilityState) === 'hidden', 'Delete hide was not real');
  const hiddenDelete = await status(); await pause(3200);
  assert.equal((await status()).requests['GET /api/flux/repos/gr-sort-repo-4/delete-progress'], hiddenDelete.requests['GET /api/flux/repos/gr-sort-repo-4/delete-progress']);
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } }); await page.bringToFront();
  await page.getByRole('dialog', { name: 'Repository removal: sort-repo-4', exact: true }).waitFor();
  assert.equal((await status()).requests['DELETE /api/flux/repos/gr-fixture-source-4'], deleteCount);
  await control('release-discovery'); await page.getByText('Server removal completed. Review the hierarchy and retained native credentials.', { exact: true }).waitFor();
  await pause(2500); assert.equal(await page.getByRole('dialog').count(), 1);
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  mark('Exact-name delete; real hidden mid-cascade preserves public monitor, pauses progress, resumes without duplicate DELETE and retains completed result');
  await page.getByLabel('Search repositories and descendants').fill('sort-repo-3');
  await control('hold-progress'); await control('hold-removal'); await page.getByRole('button', { name: 'Remove sort-repo-3', exact: true }).click();
  dialog = page.getByRole('dialog'); await dialog.getByLabel('Type sort-repo-3 to confirm').fill('sort-repo-3'); await dialog.getByRole('button', { name: 'Remove repository', exact: true }).click();
  await until(async () => (await status()).heldFluxReplies.includes('progress'), 'Held progress reply missing');
  await until(async () => (await status()).heldFluxReplies.includes('removal'), 'Held accepted removal reply missing');
  await page.getByRole('dialog').getByRole('button', { name: 'Dismiss monitoring', exact: true }).click();
  await control('release-replies'); await pause(2000);
  assert.equal(await page.getByRole('dialog').count(), 0);
  assert.equal(await page.getByText(/Progress monitoring dismissed/).count(), 1);
  mark('Dismissal stops progress subscription and fences both held progress and accepted removal replies without claiming server cancellation');
  await page.goto(state.readerUrl + '/flux'); await until(async () => await rows(page).count() > 0, 'Readonly hierarchy failed');
  assert.equal(await page.getByRole('button', { name: /^Sync / }).count(), 0); assert.equal(await page.getByRole('button', { name: /^Remove / }).count(), 0); assert.equal(await page.getByRole('button', { name: 'Add Repository', exact: true }).count(), 0);
  await page.screenshot({ path: '../../docs/implementation-evidence/flux-mobile.png', fullPage: true });
  await page.screenshot({ path: '../../docs/implementation-evidence/flux-mobile-viewport.png', fullPage: false });
  if (process.argv[4]) {
    await page.addScriptTag({ path: process.argv[4] });
    const scan = await page.evaluate(async () => {
      const result = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } });
      const safeTargets = targets => targets.map(target => typeof target === 'string' && /^[A-Za-z0-9#._>:() +~*\-]+$/.test(target) ? target : 'Selector with attributes withheld');
      const finding = item => ({ id: item.id, impact: item.impact, helpUrl: item.helpUrl, nodes: item.nodes.map(node => ({ target: safeTargets(node.target) })) });
      // Review clipped text using render metadata only: never save content,
      // HTML, input attributes, arbitrary classes or original unsafe selectors.
      const contrastReview = result.incomplete.filter(item => item.id === 'color-contrast').flatMap(item => item.nodes.map(node => {
        let element; try { element = document.querySelector(node.target[0]); } catch { return { unlocated: true }; }
        if (!element) return { unlocated: true };
        const color = getComputedStyle(element).color;
        const layers = []; let ancestor = element;
        while (ancestor) { layers.unshift(getComputedStyle(ancestor).backgroundColor); ancestor = ancestor.parentElement; }
        const rgb = value => { const parts = value.match(/[\d.]+/g)?.map(Number); return parts?.length >= 3 ? [parts[0], parts[1], parts[2], parts[3] ?? 1] : null; };
        let backdrop = [255, 255, 255];
        for (const layer of layers) { const parsed = rgb(layer); if (parsed) backdrop = backdrop.map((component, index) => parsed[index] * parsed[3] + component * (1 - parsed[3])); }
        const foreground = rgb(color);
        const luminance = channels => channels.slice(0, 3).map(channel => { const value = channel / 255; return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4; }).reduce((value, channel, index) => value + channel * [0.2126, 0.7152, 0.0722][index], 0);
        const first = foreground ? luminance(foreground) : null, second = luminance(backdrop);
        return { category: element.closest('[data-flux-repository]') ? 'public repository metadata' : 'other public UI', tag: element.tagName.toLowerCase(), staticClasses: ['text-zinc-400', 'truncate', 'font-mono', 'min-w-0', 'text-sm'].filter(value => element.classList.contains(value)), color, backgroundRgb: backdrop, ratio: first === null ? null : (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05), clipped: element.scrollWidth > element.clientWidth };
      }));
      return { version: result.testEngine.version, violations: result.violations.map(finding), passes: result.passes.map(item => item.id), incomplete: result.incomplete.map(finding), incompleteContrastRenderMetadata: contrastReview };
    });
    evidence.accessibilityScan = scan;
    assert.equal(scan.version, '4.14.0', 'Unexpected scanner version');
  }
  const finalStatus = await status();
  evidence.fluxReadTimeline = { events: finalStatus.fluxReadEvents, dropped: finalStatus.droppedFluxEvents };
  evidence.browserReadOwnership = browserReadEvents;
  assert(Object.values(finalStatus.maxActiveFluxReads).every(value => value <= 1), 'A Flux read overlapped an unsettled request');
  mark('Readonly navigation has no mutation controls; no overlapping Flux read ownership', { maxActiveReads: finalStatus.maxActiveFluxReads });
  await windowControl.detach();
} catch (failure) {
  evidence.failures.push(failure instanceof Error ? failure.message : String(failure)); process.exitCode = 1;
  try { evidence.failureState = { hierarchyAlertCount: await ownedPage.locator('main').getByRole('alert').count(), allAlertCount: await ownedPage.getByRole('alert').count(), repositoryRows: await rows(ownedPage).count(), fixture: await status() }; } catch { evidence.failureState = { observationUnavailable: true }; }
} finally {
  if (browser) {
    try { const closeSession = await browser.newBrowserCDPSession(); await closeSession.send('Browser.close'); } catch { /* A successful close may disconnect before its acknowledgement. */ }
    await browser.close().catch(() => {});
  }
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) await Promise.race([once(chrome, 'exit'), pause(15000)]);
  if (fixture.exitCode === null && fixture.signalCode === null) { fixture.stdin.write('stop\n'); await Promise.race([once(fixture, 'exit'), pause(30000)]); }
  evidence.cleanup = { chromeExitCode: chrome?.exitCode, chromeSignal: chrome?.signalCode, fixtureExitCode: fixture.exitCode, fixtureSignal: fixture.signalCode };
  if ((chrome && chrome.exitCode === null && chrome.signalCode === null) || (fixture.exitCode === null && fixture.signalCode === null)) { evidence.failures.push('Owned browser or fixture did not terminate normally'); process.exitCode = 1; }
  evidence.terminal = true; evidence.completedAt = new Date().toISOString();
  writeFileSync(evidencePath, JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify({ checks: evidence.checks.length, failures: evidence.failures, cleanup: evidence.cleanup }));
}
