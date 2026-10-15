import assert from 'node:assert/strict';
import { readFile, realpath, stat } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire('/tools/package.json');
const pkg = require('playwright-core/package.json');
assert.equal(pkg.name, 'playwright-core'); assert.equal(pkg.version, '1.62.1');
assert.deepEqual(pkg.dependencies ?? {}, {}); assert.deepEqual(pkg.optionalDependencies ?? {}, {});
const { chromium } = require('playwright-core');
const executable = await realpath(chromium.executablePath());
assert.equal(executable.startsWith('/ms-playwright/'), true);
assert.equal((await stat(executable)).isFile(), true);
const state = JSON.parse(await readFile('/exchange/ready.json', 'utf8'));
const base = new URL(state.writerUrl);
assert.equal(base.protocol, 'http:'); assert.equal(base.hostname, '127.0.0.1');
assert.equal(base.pathname, '/'); assert.equal(base.search, ''); assert.equal(base.hash, '');
assert.equal(base.username, ''); assert.equal(base.password, '');
const expected = [
  { name: 'sort-fixture-12', namespace: 'kube-system', restarts: 12 },
  { name: 'sort-fixture-2', namespace: 'apps', restarts: 2 },
  { name: 'sort-fixture-7', namespace: 'apps', restarts: 7 },
];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check) {
  const end = Date.now() + 10000;
  while (Date.now() < end) { if (await check()) return; await sleep(100); }
  assert.fail('Bounded browser smoke state did not become ready');
}
let browser, failed = false;
try {
  // No host IPC, added capabilities or privileged mode. Browser sandbox is not claimed.
  browser = await chromium.launch({ executablePath: executable, headless: true, chromiumSandbox: false, timeout: 15000 });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const page = await context.newPage(); page.setDefaultTimeout(10000); page.setDefaultNavigationTimeout(30000);
  const wire = page.waitForResponse(response => {
    const u = new URL(response.url());
    return u.origin === base.origin && u.pathname === '/api/cluster/pods' && !u.search && response.request().method() === 'GET';
  });
  const [, response] = await Promise.all([page.goto(base.origin + '/pods', { waitUntil: 'domcontentloaded' }), wire]);
  assert.equal(response.status(), 200);
  const data = await response.json(); assert.equal(data.pods.length, 208);
  assert.equal(data.privateFieldsOmitted, true);
  assert.equal(new Set(data.pods.map(row => row.namespace + '/' + row.name)).size, 208);
  for (const item of expected) {
    const matches = data.pods.filter(row => row.name === item.name && row.namespace === item.namespace);
    assert.equal(matches.length, 1); assert.equal(matches[0].restarts, item.restarts);
  }
  const main = page.locator('main').filter({ has: page.getByRole('heading', { name: 'Pods', exact: true }) });
  assert.equal(await main.count(), 1);
  const search = main.getByRole('textbox', { name: 'Search', exact: true });
  assert.equal(await search.count(), 1);
  await until(async () => await main.locator('tbody tr').count() === 100);
  await search.fill('sort-fixture');
  await until(async () => await main.locator('tbody tr').count() === 3);
  assert.equal(await search.inputValue(), 'sort-fixture');
  const rows = await main.locator('tbody tr').evaluateAll(elements => elements.map(row => ({
    cells: [...row.querySelectorAll('td')].slice(0, 8).map(cell => cell.textContent?.trim()),
    links: [...row.querySelectorAll('td:nth-child(2) a')].map(link => link.getAttribute('href')),
  })));
  assert.deepEqual(rows.map(row => row.cells[1]).sort(), expected.map(row => row.name).sort());
  for (const item of expected) {
    const row = rows.find(row => row.cells[1] === item.name);
    assert.deepEqual(row.cells, ['Running', item.name, item.namespace, 'example.invalid/fixture:v1', '1/1', String(item.restarts), '10.0.0.1', 'fixture-node']);
    assert.deepEqual(row.links, ['/pods/' + item.namespace + '/' + item.name]);
  }
  console.log(JSON.stringify({ browserSmoke: 'passed', realPodGETStatus: 200, wireRows: 208, initialPageRows: 100, filteredRows: 3, nonAgeColumnsVerified: 8, exactLinks: 3, noMutationsAttempted: true, ATQualified: false, performanceQualified: false }));
} catch (error) {
  failed = true;
  console.log(JSON.stringify({ browserSmoke: 'refused', errorType: error?.name === 'AssertionError' ? 'AssertionError' : 'Error' }));
} finally {
  if (browser) { try { await browser.close(); } catch { failed = true; } }
  process.exitCode = failed ? 1 : 0;
}
