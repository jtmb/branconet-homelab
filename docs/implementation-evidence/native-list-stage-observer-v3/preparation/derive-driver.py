import hashlib,json,pathlib,subprocess,sys
repository,destination=sys.argv[1:];candidate='15786222e4b01b0692ad9aebab99b8734b505c7b'
destination=pathlib.Path(destination);assert not destination.resolve().is_relative_to(pathlib.Path(repository).resolve())
raw=subprocess.run(['git','-C',repository,'show',candidate+':benchmarks/bortus-controlled-perf/whole-server.mjs'],check=True,stdout=subprocess.PIPE).stdout
assert hashlib.sha256(raw).hexdigest()=='ee7d4f9efcbc88e08999a72feafe0099add8c1c1124362f1d839fab2746ebd2b'
text=raw.decode()
changes=[
 ('let server, child, origin, currentProfile, failedNamespace, sampling, activePhase;','let server, child, origin, currentProfile, failedNamespace, sampling, activePhase; let diagnosticRequest=0, diagnosticProcess=0;'),
 ("const start = performance.now(), response = await fetch(origin + route, { headers: token ? { Cookie: 'botrus_auth_token=' + token } : {},","const requestId = 'native-diag-' + (++diagnosticRequest); const start = performance.now(), response = await fetch(origin + route, { headers: { ...(token ? { Cookie: 'botrus_auth_token=' + token } : {}), 'x-bortus-diagnostic-id': requestId },"),
 ('const result = { status: response.status, elapsed_ms: elapsed, response_body_bytes: bytes.length };','const result = { request_id: requestId, status: response.status, elapsed_ms: elapsed, response_body_bytes: bytes.length };'),
 ("child = spawn(process.execPath, ['/app/.next/standalone/server.js'], { cwd: '/app/.next/standalone', env: { ...clean, PORT: String(port) },","child = spawn(process.execPath, ['--require', '/diagnostic/preload.cjs', '/app/.next/standalone/server.js'], { cwd: '/app/.next/standalone', env: { ...clean, PORT: String(port), BORTUS_NATIVE_DIAGNOSTIC_OUTPUT: '/results/native-spans-' + (++diagnosticProcess) + '.json' },"),
 ('for (const profile of profiles) {',"report.diagnostic_only = true; report.source_commit = process.env.BORTUS_NATIVE_DIAGNOSTIC_SOURCE; assert(/^[0-9a-f]{40}$/.test(report.source_commit)); for (const profile of profiles) {"),
]
for before,after in changes:
 assert text.count(before)==1,'Missing or ambiguous driver hook'
 text=text.replace(before,after)
destination.mkdir(exist_ok=False)
(destination/'native-stage-driver.mjs').write_bytes(text.encode())
manifest={'diagnostic_only':True,'original_sha256':hashlib.sha256(raw).hexdigest(),'derived_sha256':hashlib.sha256(text.encode()).hexdigest(),'frozen_driver_unmodified':True,'changes':['fixed-format correlation IDs','preload only in Next child','separate metadata outputs, exact source commit from fixed launcher environment'],'unchanged':['all six profiles and every inventory/negative assertion','12 warm/20 concurrent samples, including unconditional10k warm skip','full-body client timing','all original deadlines/response limits'],'expected_native_HTTP_requests':6,'no_heavy_run':True}
(destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
