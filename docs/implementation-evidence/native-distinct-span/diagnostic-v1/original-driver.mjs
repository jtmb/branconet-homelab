import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, chmod, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createServer } from 'node:https';
import net from 'node:net';
import { createRequire } from 'node:module';
import { randomBytes } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { once } from 'node:events';
import { pathToFileURL } from 'node:url';
const require = createRequire('/app/package.json');
const { PrismaClient } = require('@prisma/client');
const { SignJWT } = await import(pathToFileURL(require.resolve('jose')).href);
assert.equal(process.platform, 'linux'); assert.equal(process.version, 'v22.23.3');
const label = process.env.BORTUS_PERF_LABEL, run = Number(process.env.BORTUS_PERF_RUN);
assert.ok(['baseline', 'candidate'].includes(label)); assert.ok(run >= 1 && run <= 5);
const dir = await mkdtemp(path.join(tmpdir(), 'bortus-controlled-perf-'));
const fixture = path.join(dir, 'fixture'); await mkdir(fixture);
const database = 'file:' + path.join(dir, 'fixture.db');
const signing = randomBytes(48).toString('hex');
const created = '2026-10-01T00:00:00Z';
const namespaces = ['apps', ...Array.from({ length: 17 }, (_, i) => 'scope-' + String(i).padStart(2, '0'))];
const report = { label, run, node: process.version, platform: process.platform, arch: process.arch, profiles: [], failures: [],
  definitions: { cold: 'Fresh Next process, /api/auth/session initialized, no cluster resource request; OS/file caches not flushed', warm: 'Same process immediately after one successful identical resource read',
    cli_delay_ms: 50, native_delay_ms: 12, warm_samples: 12, concurrency: 20, percentile: 'nearest rank ceil(p*n)-1', rss_sample_interval_ms: 50,
    cgroup_scope: 'Whole runtime fixture container: driver/native API/Next/Prisma/fake CLI/file cache; not server-only RSS', fixture_payloads_persisted_in_evidence: false,
    max_response_body_bytes: 33554432, request_deadline_ms: 20000, startup_deadline_ms: 30000, run_wall_deadline_seconds: 540 },
};
let server, child, origin, currentProfile, failedNamespace, sampling, activePhase;
let peakSampleRss = 0, peakProcesses = 0, nativeCalls = [], serverSamples = [];
const deadline = Date.now() + 540000;
const readText = async file => (await readFile(file, 'utf8')).trim();
const numberFile = async file => Number(await readText(file));
async function counters() {
  const text = await readText('/sys/fs/cgroup/cpu.stat');
  return Object.fromEntries(text.split('\n').map(line => { const [key, value] = line.split(' '); return [key, Number(value)]; }));
}
async function processMetrics(pid) {
  const status = await readText('/proc/' + pid + '/status');
  const field = name => Number(status.match(new RegExp('^' + name + ':\\s+(\\d+)', 'm'))?.[1] ?? 0);
  const stat = await readText('/proc/' + pid + '/stat'), fields = stat.slice(stat.lastIndexOf(')') + 2).split(' ');
  return { rss_kib: field('VmRSS'), peak_rss_kib: field('VmHWM'), threads: field('Threads'), cpu_ticks: Number(fields[11]) + Number(fields[12]) };
}
async function sample() {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  try {
    const metrics = await processMetrics(child.pid); serverSamples.push(metrics.rss_kib); peakSampleRss = Math.max(peakSampleRss, metrics.rss_kib);
    const processes = (await readdir('/proc')).filter(name => /^\d+$/.test(name)).length;
    peakProcesses = Math.max(peakProcesses, processes);
  } catch { /* Process exit can race observations; kernel HWM is reported separately. */ }
}
async function cliCount() {
  try { return (await readText(path.join(fixture, 'calls.log'))).split('\n').filter(Boolean).length; } catch { return 0; }
}
function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return { n: sorted.length, min: sorted[0], p50: sorted[Math.ceil(sorted.length * .5) - 1], p95: sorted[Math.ceil(sorted.length * .95) - 1], max: sorted.at(-1) };
}
async function stop() {
  clearInterval(sampling); sampling = undefined;
  if (!child) return;
  const stopped = child; child = undefined;
  if (stopped.exitCode === null && stopped.signalCode === null) {
    const exit = once(stopped, 'exit'); stopped.kill('SIGTERM');
    const timer = setTimeout(() => stopped.kill('SIGKILL'), 3000);
    await exit; clearTimeout(timer);
  }
}
const clean = { PATH: fixture + ':' + process.env.PATH, NODE_ENV: 'production', HOSTNAME: '127.0.0.1', DATABASE_URL: database,
  BOTRUS_JWT_SECRET: signing, BOTRUS_SECRETS_KEY: randomBytes(32).toString('hex'), BORTUS_SECRET_NAMESPACES: namespaces.join(','),
  BORTUS_SECRET_ALIASES_FILE: path.join(dir, 'aliases.json'), BORTUS_DISABLE_PROVISIONING: 'true', BORTUS_HISTORY_NAMESPACE: 'history', BORTUS_KV_GUARDED_ADOPTION: 'false',
  NEXT_TELEMETRY_DISABLED: '1', BORTUS_PERF_FIXTURE: fixture };
async function request(route, token, expectedCount) {
  if (Date.now() >= deadline) throw Error('Fixed run deadline exceeded');
  const start = performance.now(), response = await fetch(origin + route, { headers: token ? { Cookie: 'botrus_auth_token=' + token } : {}, signal: AbortSignal.timeout(Math.min(20000, deadline - Date.now())) });
  const bytes = Buffer.from(await response.arrayBuffer());
  assert.ok(bytes.length <= report.definitions.max_response_body_bytes, 'Response exceeds observer limit');
  const elapsed = performance.now() - start;
  let body; try { body = JSON.parse(bytes); } catch { throw Error('Expected JSON response'); }
  const result = { status: response.status, elapsed_ms: elapsed, response_body_bytes: bytes.length };
  if (expectedCount !== undefined) {
    const list = body.pods;
    if (response.ok && Array.isArray(list) && list.length === expectedCount) {
      assert.equal(new Set(list.map(row => row.name + '/' + row.namespace)).size, expectedCount, 'Duplicate public Pod identities');
      for (let i = 0; i < expectedCount; i++) {
        const row = list[i]; assert.equal(row.name, 'pod-' + String(i).padStart(5, '0')); assert.equal(row.namespace, i % 3 === 0 ? 'kube-system' : 'apps');
      }
      result.equivalent_expected_inventory = true; result.returned_count = list.length;
    } else {
      result.equivalent_expected_inventory = false; result.returned_count = Array.isArray(list) ? list.length : null;
      assert.equal(currentProfile.pods, 10000, 'Unexpected inventory/status mismatch on a valid workload');
      if (label === 'baseline') { assert.equal(response.status, 200); assert.equal(list.length, 0); }
      else { assert.equal(response.status, 503); assert.equal(body.availability?.resources?.pods?.state, 'unavailable'); }
    }
  }
  return { result, body };
}
async function start(token) {
  await stop(); peakSampleRss = 0; peakProcesses = 0; serverSamples = [];
  const reservation = net.createServer(); reservation.listen(0, '127.0.0.1'); await once(reservation, 'listening');
  const port = reservation.address().port; await new Promise(resolve => reservation.close(resolve));
  const started = performance.now(); origin = 'http://127.0.0.1:' + port;
  child = spawn(process.execPath, ['/app/.next/standalone/server.js'], { cwd: '/app/.next/standalone', env: { ...clean, PORT: String(port) }, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', () => {}); child.stderr.on('data', () => {});
  const startupDeadline = Math.min(deadline, Date.now() + report.definitions.startup_deadline_ms);
  let ready = false;
  while (Date.now() < startupDeadline) {
    if (child.exitCode !== null || child.signalCode !== null) throw Error('Next exited before startup');
    try {
      const response = await fetch(origin + '/api/health/live', { signal: AbortSignal.timeout(Math.max(1, Math.min(1000, startupDeadline - Date.now()))) });
      if (response.ok) { ready = true; break; }
    } catch { /* bounded startup probing */ }
    await new Promise(resolve => setTimeout(resolve, Math.max(0, Math.min(100, startupDeadline - Date.now()))));
  }
  if (!ready) throw Error('Next startup exceeded thirty seconds');
  const session = await request('/api/auth/session', token); assert.equal(session.result.status, 200); assert.equal(session.body.authenticated, true);
  sampling = setInterval(() => void sample(), 50); await sample();
  return { ready_and_session_ms: performance.now() - started, port };
}
async function phase(name, operation) {
  activePhase = name;
  const before = { cli: await cliCount(), native: nativeCalls.length, cpu: await counters(), process: await processMetrics(child.pid) };
  const started = performance.now(), result = await operation(); await sample();
  const afterCpu = await counters(), afterProcess = await processMetrics(child.pid);
  return { name, elapsed_ms: performance.now() - started, cli_calls: await cliCount() - before.cli, native_api_calls: nativeCalls.length - before.native,
    cgroup_cpu_usage_usec: afterCpu.usage_usec - before.cpu.usage_usec, cgroup_throttled_usec: afterCpu.throttled_usec - before.cpu.throttled_usec,
    server_cpu_ticks: afterProcess.cpu_ticks - before.process.cpu_ticks, server_rss_kib: afterProcess.rss_kib, server_peak_rss_kib: afterProcess.peak_rss_kib,
    peak_sampled_server_rss_kib: peakSampleRss, observed_process_count_max: peakProcesses, ...result };
}
async function fixtures(profile) {
  currentProfile = profile; failedNamespace = undefined;
  const pod = i => ({ apiVersion: 'v1', kind: 'Pod', metadata: { name: 'pod-' + String(i).padStart(5, '0'), namespace: i % 3 === 0 ? 'kube-system' : 'apps', uid: 'pod-uid-' + i, creationTimestamp: created,
    labels: { app: 'fixed-workload', tier: 'frontend' }, ownerReferences: [{ apiVersion: 'apps/v1', kind: 'ReplicaSet', name: 'api-rs', uid: 'rs-api', controller: true }] },
    spec: { nodeName: 'fixture-node', containers: [{ name: 'app', image: 'example.invalid/workload:v1', resources: { requests: { cpu: '100m', memory: '128Mi' } } }] },
    status: { phase: 'Running', podIP: '10.0.0.1', containerStatuses: [{ name: 'app', ready: true, restartCount: i % 13 }] } });
  const node = { apiVersion: 'v1', kind: 'Node', metadata: { name: 'fixture-node', uid: 'node-one', creationTimestamp: created }, status: { capacity: { cpu: '2', memory: '2Gi' }, conditions: [{ type: 'Ready', status: 'True' }], nodeInfo: { kubeletVersion: 'v1.34.1' } } };
  const deployment = name => ({ apiVersion: 'apps/v1', kind: 'Deployment', metadata: { name, namespace: 'apps', uid: 'dep-' + name, creationTimestamp: created }, spec: { replicas: 1, template: { spec: { containers: [{ image: 'example.invalid/workload:v1' }] } } }, status: { replicas: 1, readyReplicas: 1, updatedReplicas: 1, availableReplicas: 1, conditions: [{ type: 'Available', status: 'True' }] } });
  const data = { nodes: { items: [node] }, pods: { items: Array.from({ length: profile.pods }, (_, i) => pod(i)) }, deployments: { items: [deployment('api'), deployment('api-worker')] },
    replicasets: { items: [{ apiVersion: 'apps/v1', kind: 'ReplicaSet', metadata: { name: 'api-rs', namespace: 'apps', uid: 'rs-api', ownerReferences: [{ kind: 'Deployment', name: 'api', uid: 'dep-api', controller: true }] } }] },
    namespaces: { items: namespaces.map(name => ({ metadata: { name, creationTimestamp: created }, status: { phase: 'Active' } })) }, services: { items: [] }, ingress: { items: [] }, pv: { items: [] }, pvc: { items: [] }, sc: { items: [] }, 'volumes.longhorn.io': { items: [] } };
  for (const [name, document] of Object.entries(data)) await writeFile(path.join(fixture, name + '.json'), JSON.stringify(document));
  await writeFile(path.join(fixture, 'mode.json'), JSON.stringify({ failure: false, longhornDelay: 50 })); await writeFile(path.join(fixture, 'calls.log'), '');
  await writeFile(clean.BORTUS_SECRET_ALIASES_FILE, JSON.stringify(Array.from({ length: 603 }, (_, i) => {
    const index = i % Math.min(profile.secrets, 12);
    return { alias: 'exact_alias_' + String(i).padStart(4, '0'), namespace: namespaces[index % (profile.nativeScopes ?? 18)], name: 'secret-' + String(index).padStart(5, '0'), key: 'original_under_score' };
  })));
  const db = new PrismaClient({ datasources: { db: { url: database } } });
  try {
    await db.variable.deleteMany();
    for (let i = 0; i < profile.config; i += 200) await db.variable.createMany({ data: Array.from({ length: Math.min(200, profile.config - i) }, (_, j) => ({ key: 'benchmark_config_' + (i + j), value: 'fixed nonsecret configuration', category: 'general', encrypted: false })) });
  } finally { await db.$disconnect(); }
  return { name: profile.name, pods: profile.pods, secret_objects: profile.secrets, secret_decoded_payload_bytes_each: profile.secretBytes, config_rows: profile.config,
    namespaces: 18, native_active_scopes: profile.nativeScopes ?? 18, alias_references: 603, pod_cli_json_bytes: Buffer.byteLength(JSON.stringify(data.pods)), common_expected_fields: 'every Pod name/namespace and every native Secret name/namespace/type/exact key map; complete expected counts' };
}
const profiles = [
  { name: 'audit-small', pods: 3, secrets: 334, secretBytes: 64, config: 200 },
  { name: 'metadata-200', pods: 200, secrets: 200, secretBytes: 64, config: 200 },
  { name: 'metadata-1000', pods: 1000, secrets: 1000, secretBytes: 64, config: 1000 },
  { name: 'metadata-10000', pods: 10000, secrets: 10000, secretBytes: 64, config: 10000 },
  { name: 'kv-sized-native-25', pods: 3, secrets: 25, secretBytes: 256 * 1024, config: 200, nativeScopes: 1 },
  { name: 'maximum-flat-native-3', pods: 3, secrets: 3, secretBytes: 1024 * 1024, config: 200, nativeScopes: 1 },
];
try {
  report.enforced_limits = { memory_max: await readText('/sys/fs/cgroup/memory.max'), swap_max: await readText('/sys/fs/cgroup/memory.swap.max'), cpu_max: await readText('/sys/fs/cgroup/cpu.max'), cpuset: await readText('/sys/fs/cgroup/cpuset.cpus.effective'), pids_max: await readText('/sys/fs/cgroup/pids.max') };
  assert.equal(report.enforced_limits.memory_max, '1073741824'); assert.equal(report.enforced_limits.swap_max, '0'); assert.equal(report.enforced_limits.cpu_max, '200000 100000'); assert.equal(report.enforced_limits.pids_max, '256');
  report.clock_ticks_per_second = Number(execFileSync('getconf', ['CLK_TCK'], { encoding: 'utf8' }));
  await writeFile(path.join(fixture, 'kubectl'), `#!/usr/bin/env node\nconst fs=require('fs'),path=require('path');const dir=process.env.BORTUS_PERF_FIXTURE,args=process.argv.slice(2),i=args.indexOf('get'),resource=i<0?'unsupported':args[i+1];fs.appendFileSync(path.join(dir,'calls.log'),resource+'\\n');const mode=JSON.parse(fs.readFileSync(path.join(dir,'mode.json'),'utf8'));setTimeout(()=>{if(mode.failure){process.stderr.write('Fixed fixture unavailable');process.exit(1)}const file=path.join(dir,resource+'.json');process.stdout.write(fs.existsSync(file)?fs.readFileSync(file):'{"items":[]}')},resource==='volumes.longhorn.io'?mode.longhornDelay:50);\n`);
  await chmod(path.join(fixture, 'kubectl'), 0o700);
  const cert = path.join(dir, 'cert.pem'), key = path.join(dir, 'key.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key, '-out', cert, '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], { stdio: 'ignore' });
  const payload = size => Buffer.alloc(size, 7).toString('base64');
  const privateAnnotation = randomBytes(32).toString('base64');
  server = createServer({ key: await readFile(key), cert: await readFile(cert) }, async (req, res) => {
    const url = new URL(req.url, 'https://fixture.invalid'), match = url.pathname.match(/^\/api\/v1\/namespaces\/([^/]+)\/secrets$/);
    if (req.method !== 'GET' || !match) { res.writeHead(405); res.end('{"kind":"Status"}'); return; }
    const namespace = match[1], scopeIndex = namespaces.indexOf(namespace), metadata = (req.headers.accept ?? '').includes('PartialObjectMetadata');
    if (namespace === failedNamespace || scopeIndex < 0) {
      nativeCalls.push({ metadata, status: 403, body_bytes: 0 }); res.writeHead(403, { 'Content-Type': 'application/json' }); res.end('{"kind":"Status","reason":"Forbidden"}'); return;
    }
    const activeScopes = currentProfile.nativeScopes ?? namespaces.length;
    const total = scopeIndex >= activeScopes ? 0 : Math.max(0, Math.ceil((currentProfile.secrets - scopeIndex) / activeScopes));
    const limit = Math.min(10000, Number(url.searchParams.get('limit') || '200')), offset = Number(url.searchParams.get('continue') || '0');
    const end = Math.min(total, offset + limit), value = payload(currentProfile.secretBytes), items = [];
    for (let local = offset; local < end; local++) {
      const index = scopeIndex + local * activeScopes;
      const meta = { namespace, name: 'secret-' + String(index).padStart(5, '0'), uid: 'native-uid-' + index, resourceVersion: '10', labels: { fixture: 'metadata' } };
      if (metadata) items.push({ apiVersion: 'meta.k8s.io/v1', kind: 'PartialObjectMetadata', metadata: meta });
      else items.push({ apiVersion: 'v1', kind: 'Secret', metadata: { ...meta, annotations: { 'kubectl.kubernetes.io/last-applied-configuration': privateAnnotation } }, type: 'Opaque', data: { payload: value, original_under_score: '', empty: '' } });
    }
    const body = JSON.stringify({ apiVersion: metadata ? 'meta.k8s.io/v1' : 'v1', kind: metadata ? 'PartialObjectMetadataList' : 'SecretList', metadata: { resourceVersion: '10', ...(end < total ? { continue: String(end) } : {}) }, items });
    nativeCalls.push({ metadata, status: 200, body_bytes: Buffer.byteLength(body), returned_objects: items.length });
    await new Promise(resolve => setTimeout(resolve, 12)); res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(body);
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening'); report.native_port = server.address().port;
  clean.KUBECONFIG = path.join(dir, 'config.json');
  await writeFile(clean.KUBECONFIG, JSON.stringify({ apiVersion: 'v1', kind: 'Config', clusters: [{ name: 'fixture', cluster: { server: 'https://127.0.0.1:' + report.native_port, 'certificate-authority': cert } }], users: [{ name: 'fixture', user: {} }], contexts: [{ name: 'fixture', context: { cluster: 'fixture', user: 'fixture' } }], 'current-context': 'fixture' }));
  await writeFile(clean.BORTUS_SECRET_ALIASES_FILE, JSON.stringify(Array.from({ length: 603 }, (_, i) => ({ alias: 'exact_alias_' + String(i).padStart(4, '0'), namespace: namespaces[i % 12], name: 'secret-' + String(i % 3).padStart(5, '0'), key: 'original_under_score' }))));
  execFileSync(process.execPath, [require.resolve('prisma/build/index.js'), 'migrate', 'deploy'], { cwd: '/app', env: clean, stdio: 'ignore' });
  const db = new PrismaClient({ datasources: { db: { url: database } } }); let writer, reader;
  try {
    const columns = await db.$queryRawUnsafe('PRAGMA table_info(users)');
    const admin = columns.some(column => column.name === 'engineAdmin');
    writer = await db.user.create({ data: { username: 'benchmark_writer', passwordHash: 'unused fixture', role: 'write', ...(admin ? { engineAdmin: true } : {}) } });
    reader = await db.user.create({ data: { username: 'benchmark_reader', passwordHash: 'unused fixture', role: 'readonly' } });
  } finally { await db.$disconnect(); }
  const token = user => new SignJWT({ sub: user.id, username: user.username, sessionVersion: user.sessionVersion ?? 0 }).setProtectedHeader({ alg: 'HS256' }).setIssuedAt().setExpirationTime('1h').sign(new TextEncoder().encode(signing));
  const writerToken = await token(writer), readerToken = await token(reader);
  for (const profile of profiles) {
    await stop(); const item = { fixture: await fixtures(profile), phases: [], startups: [] }; nativeCalls = []; report.profiles.push(item);
    item.startups.push(await start(readerToken));
    item.phases.push(await phase('cold-pods', async () => ({ requests: [(await request('/api/cluster/pods', readerToken, profile.pods)).result] })));
    if (profile.pods < 10000) {
      item.phases.push(await phase('warm-pods-12', async () => { const requests = []; for (let i = 0; i < 12; i++) requests.push((await request('/api/cluster/pods', readerToken, profile.pods)).result); return { requests, latency_ms: stats(requests.map(r => r.elapsed_ms)) }; }));
      item.phases.push(await phase('warm-pods-concurrent-20', async () => ({ requests: await Promise.all(Array.from({ length: 20 }, async () => (await request('/api/cluster/pods', readerToken, profile.pods)).result)) })));
      const warm = item.phases.filter(p => p.name.startsWith('warm-')); assert.equal(warm.every(p => p.cli_calls === 0), true, 'Warm cache regression made new CLI calls');
    }
    item.phases.push(await phase('services-after-pods', async () => { const response = await request('/api/cluster/services', readerToken); assert.equal(response.result.status, 200); assert.deepEqual(response.body.services, []); return { requests: [response.result] }; }));
    item.phases.push(await phase('configuration-metadata', async () => { const response = await request('/api/vars', readerToken); assert.equal(response.result.status, 200); assert.equal(response.body.length, profile.config); return { requests: [response.result], expected_count: profile.config, equivalent_expected_inventory: true }; }));
    item.phases.push(await phase('native-secret-metadata', async () => {
      const startCall = nativeCalls.length, response = await request('/api/secrets', readerToken), rows = response.body.secrets;
      assert.equal(response.result.status, 200); assert.equal(rows.length, profile.secrets, 'Incomplete native metadata inventory');
      assert.equal(new Set(rows.map(row => row.namespace + '/' + row.name)).size, profile.secrets);
      for (const row of rows) {
        const index = Number(row.name.slice(7)); assert.equal(row.name, 'secret-' + String(index).padStart(5, '0')); assert.equal(row.namespace, namespaces[index % (profile.nativeScopes ?? 18)]); assert.equal(row.type, 'Opaque');
        assert.deepEqual([...row.keys].sort(), ['empty', 'original_under_score', 'payload']); assert.equal(row.resourceVersion, '10');
        assert.equal('data' in row || 'annotations' in row || 'managedFields' in row, false, 'Private native payload reached public metadata');
      }
      const produced = nativeCalls.slice(startCall); return { requests: [response.result], equivalent_expected_inventory: true, expected_count: profile.secrets,
        native_produced_response_body_bytes: produced.reduce((sum, call) => sum + call.body_bytes, 0), native_returned_objects_including_retries: produced.reduce((sum, call) => sum + (call.returned_objects || 0), 0) };
    }));
    item.phases.push(await phase('all-alias-metadata', async () => {
      const rows = [], requests = []; let cursor;
      do {
        assert.ok(requests.length < 7, 'Alias pagination exceeded its fixed budget');
        const response = await request('/api/secret-references' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''), readerToken);
        assert.equal(response.result.status, 200); assert.ok(Array.isArray(response.body.references));
        rows.push(...response.body.references); requests.push(response.result); cursor = response.body.nextCursor;
      } while (cursor);
      assert.equal(rows.length, 603); assert.equal(new Set(rows.map(row => row.alias)).size, 603);
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i], index = i % Math.min(profile.secrets, 12);
        assert.equal(row.alias, 'exact_alias_' + String(i).padStart(4, '0')); assert.equal(row.namespace, namespaces[index % (profile.nativeScopes ?? 18)]);
        assert.equal(row.name, 'secret-' + String(index).padStart(5, '0')); assert.equal(row.key, 'original_under_score');
      }
      return { requests, equivalent_expected_inventory: true, expected_count: 603 };
    }));
    item.phases.push(await phase('readiness-five-sequential', async () => { const requests = [], before = nativeCalls.length; for (let i = 0; i < 5; i++) { const response = await request('/api/health/ready'); assert.equal(response.result.status, 200); requests.push(response.result); }
      const produced = nativeCalls.slice(before); return { requests, native_metadata_only_calls: produced.filter(call => call.metadata).length, native_produced_response_body_bytes: produced.reduce((sum, call) => sum + call.body_bytes, 0) }; }));
    item.process_before_restart = await processMetrics(child.pid); item.steady_rss_kib = stats(serverSamples.slice(-20));
    item.startups.push(await start(readerToken));
    item.phases.push(await phase('cold-pods-concurrent-20', async () => ({ requests: await Promise.all(Array.from({ length: 20 }, async () => (await request('/api/cluster/pods', readerToken, profile.pods)).result)) })));
    item.process_after_concurrency = await processMetrics(child.pid);
    if (profile.name === 'audit-small') {
      await writeFile(path.join(fixture, 'mode.json'), JSON.stringify({ failure: false, longhornDelay: 1000 })); item.startups.push(await start(readerToken));
      item.phases.push(await phase('slow-optional-longhorn-cold-pods', async () => ({ requests: [(await request('/api/cluster/pods', readerToken, profile.pods)).result] })));
      await writeFile(path.join(fixture, 'mode.json'), JSON.stringify({ failure: true, longhornDelay: 50 })); item.startups.push(await start(readerToken));
      item.phases.push(await phase('outage-two-sequential', async () => { const requests = []; for (let i = 0; i < 2; i++) { const response = await request('/api/cluster/pods', readerToken);
        assert.equal(response.result.status, label === 'baseline' ? 200 : 503); if (label === 'baseline') assert.equal(response.body.pods.length, 0); else assert.equal(response.body.availability.resources.pods.state, 'unavailable'); requests.push(response.result); }
        return { requests, response_semantics_equivalent: false, comparison_is_latency_speedup_valid: false }; }));
      failedNamespace = namespaces[17]; item.startups.push(await start(readerToken));
      item.phases.push(await phase('readiness-inaccessible-scope', async () => { const response = await request('/api/health/ready'); assert.equal(response.result.status, 503); return { requests: [response.result], rejects_inaccessible_scope: true }; })); failedNamespace = undefined;
    }
    item.completed = true;
  }
  report.cgroup_cpu = await counters(); report.cgroup_memory_current_bytes = await numberFile('/sys/fs/cgroup/memory.current'); report.cgroup_memory_peak_bytes = await numberFile('/sys/fs/cgroup/memory.peak');
  report.cgroup_memory_events = await readText('/sys/fs/cgroup/memory.events'); report.passed = true;
} catch (error) {
  report.passed = false;
  report.failures.push(error instanceof assert.AssertionError ? { kind: 'assertion', profile: currentProfile?.name, phase: activePhase, description: error.message.split('\n')[0] } : { kind: error?.name ?? 'Error', profile: currentProfile?.name, phase: activePhase, description: 'Runtime phase failed; raw bodies/output withheld' });
  process.exitCode = 1;
} finally {
  try { report.cgroup_cpu = await counters(); report.cgroup_memory_peak_bytes = await numberFile('/sys/fs/cgroup/memory.peak'); report.cgroup_memory_events = await readText('/sys/fs/cgroup/memory.events'); } catch { /* unavailable metrics remain unavailable */ }
  await stop(); if (server) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  await writeFile('/results/' + label + '-run-' + run + '.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ label, run, passed: report.passed, completed_profiles: report.profiles.filter(profile => profile.completed).length, failure_count: report.failures.length }));
}
