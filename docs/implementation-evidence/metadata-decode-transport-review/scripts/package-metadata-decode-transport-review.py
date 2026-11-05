from pathlib import Path
import hashlib,json,subprocess,statistics

b=Path(__file__).parent
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
dest=repo/'docs/implementation-evidence/metadata-decode-transport-review'
dest.mkdir(exist_ok=False)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
r=json.loads((b/'metadata-decode-diagnostic-v2/report.json').read_bytes())
t=json.loads((b/'metadata-decode-diagnostic-v2/terminal.json').read_bytes())
assert t['actual_exit']==t['child_exit']==0 and t['reaped'] and t['owned_pid_absent']
assert r['cases']==26404 and r['malformedCases']==20171 and r['equivalencePassed'] and r['exactProductionSourceUnchanged']
assert len(r['timings'])==15 and all(len(row['beforeMs'])==len(row['afterMs'])==15 for row in r['timings'])
assert all(row['equal'] for row in r['structural'])
copies=[]
def retain(p,rel):
 raw=p.read_bytes(); d=dest/rel; d.parent.mkdir(parents=True,exist_ok=True); d.write_bytes(raw)
 assert d.read_bytes()==raw
 copies.append({'original':str(p),'copy':str(rel).replace('\\','/'),'bytes':len(raw),'sha256':sha(raw)})
for label in ['v1','v2']:
 for p in sorted((b/('metadata-decode-diagnostic-'+label)).rglob('*')):
  if p.is_file():retain(p,Path('diagnostic-'+label)/p.relative_to(b/('metadata-decode-diagnostic-'+label)))
for p in [Path(__file__),b/'prepare-metadata-decode-diagnostic.py',b/'prepare-metadata-decode-diagnostic-v2.py']:
 retain(p,Path('scripts')/p.name)
phase=b/'characterize-phase-7e30b9b-complete/output/request-229-1.json'
current=b/'characterize-phase-7e30b9b-complete/analysis-v2.json'
baseline=b/'characterize-phase-baseline-51e8-complete/analysis.json'
for p,label in [(phase,'request-229-1.json'),(current,'candidate-analysis-v2.json'),(baseline,'baseline-analysis.json')]:retain(p,Path('retained-phase')/label)
p=json.loads(phase.read_bytes()); before=json.loads(baseline.read_bytes()); after=json.loads(current.read_bytes())
assert p['nonAcceptance'] and before['nonAcceptance'] and after['nonAcceptance']
h=p['https'];assert len(h)==18 and sum(row['tlsMs'] is not None for row in h)==4 and sum(row['reused'] for row in h)==14
assert all(row['tlsMs'] is None for row in h if row['reused'])
bindings=[]
for rel in ['k8s-rewrite/front-end/src/lib/secret-client.ts','k8s-rewrite/front-end/src/lib/cluster-secrets.ts','k8s-rewrite/front-end/src/lib/secret-summary-json.ts','k8s-rewrite/front-end/tests/native-list-window.test.ts','k8s-rewrite/front-end/tests/helpers/native-tls.ts','benchmarks/bortus-controlled-perf/whole-server.mjs']:
 working=(repo/rel).read_bytes(); raw=subprocess.check_output(['git','show','4668ceb40c3120c7e4053d94edff31f57b7e1f7f:'+rel],cwd=repo)
 tree=subprocess.check_output(['git','ls-tree','4668ceb40c3120c7e4053d94edff31f57b7e1f7f','--',rel],cwd=repo,text=True).strip().split()
 assert working==raw or working==raw.replace(b'\n',b'\r\n')
 assert subprocess.check_output(['git','show','HEAD:'+rel],cwd=repo)==raw
 retain(repo/rel,Path('current-working')/rel)
 (dest/'raw-source'/rel).parent.mkdir(parents=True,exist_ok=True);(dest/'raw-source'/rel).write_bytes(raw)
 bindings.append({'path':rel,'gitMode':tree[0],'gitBlob':tree[2],'rawSha256':sha(raw),'workingSha256':sha(working),'workingRelation':'exact' if working==raw else 'literal LF to CRLF','productionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f'})
sdk=repo/'k8s-rewrite/front-end/node_modules/@kubernetes/client-node/dist/config.js'
retain(sdk,Path('installed-sdk/config.js'))
a=next(row for row in before['rows'] if row['fixture']=='metadata-1000')
c=next(row for row in after['rows'] if row['fixture']=='metadata-1000')
keys=['nativeWindowMs','nativeRequestCount','tlsConnectionCount','sdkCalls','sdkAsyncSumMs','preFirstNativeRequestCombinedMs','firstNativeStartToLastNativeEndCombinedMs','postLastNativeEndToResponseEndCombinedMs','endEventHandlerSynchronousSumMs','fixtureStringifySumMs','fixtureRequestToResponseEndCombinedMedianMs','fixtureRequestToResponseEndCombinedMaxMs']
assessment={
 'nonAcceptance':True,'currentProductionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f','copies':copies,'currentSourceBindings':bindings,
 'decoderDiagnostic':{'terminal':t,'node':r['node'],'cases':r['cases'],'malformedRefusals':r['malformedCases'],'structural':r['structural'],'causal':r['causal'],'rows':r['timings'],'productionProposalAccepted':False,'decision':'Reject: representative 56-object/16KiB and 200-object/16KiB medians regress; escaped 56-object p95 also regresses. Equivalence and reduced fatal-decode count do not prove useful endpoint improvement.','attempt1':'Preparation only; not executed. Attempt2 has actual OS/child exit0.'},
 'operationReuse':{'source':'secret-client.ts:221-237,254-282,347-353','keepAlive':True,'agentMaxSockets':4,'agentMaxTotalSockets':4,'agentMaxFreeSockets':4,'freshAuthenticationPerRequest':True,'destroyAtBudgetFinish':True,'fixtureSourceConnectionOverride':False,'requestSourceConnectionOverride':False,'retainedHttpRequests':len(h),'retainedFreshTLSConnections':4,'retainedReusedRequests':14,'exactPerSocketRequestDistributionAvailable':False,'socketDistributionLimitation':'The retained observer records request reusedSocket and TLS events, not stable socket identities. It cannot establish an exact per-socket request count distribution.','separateOperationUsesDifferentAgent':'Existing real TLS unit at native-list-window.test.ts:215-231; current211-unit Linux qualification includes it.','exceptions':'Proxy/client-certificate requests retain fresh non-pooled SDK behavior; changed fresh TLS options are not reused.','opportunityMissing':False},
 'phaseComparison':{'profile':'metadata-1000','baselineSource':before['sourceCommit'],'candidateSource':after['sourceCommit'],'baseline':{k:a[k] for k in keys},'candidate':{k:c[k] for k in keys},'candidateFirstFourRequestHeaderMs':[row['responseMs'] for row in h[:4]],'candidateReusedHeaderMedianMs':statistics.median(row['responseMs'] for row in h if row['reused']),'candidateInclusiveFrames':[frame for frame in c['topWeightedCPUFrames'] if frame['function'] in ['capture','skip','string','space']],'requestCap':4,'namespaceRequests':18,'fixtureDelayMs':12,'idealFiveWaveFixtureDelayFloorMs':60,'floorIsInference':True,'limitations':['Observer single-run windows are not paired acceptance statistics.','Candidate phase source is7e30, before4668 long-value scanner. Current-source bindings prove unchanged operation-pool logic, not a new4668 CPU profile.','Async, socket, capture and skip inclusive intervals overlap and must not be summed as wall attribution.','End synchronous handlers include grammar/parse, listener/cleanup and observer overhead; sampled GC cannot be attributed to a particular allocation.','The five-wave floor is a scheduler lower bound from18 requests/four active/12ms fixture delay, not a complete causal explanation or an impossibility claim.','All18 namespace requests remain required under current namespace scopes; no emptiness cache or cluster-wide privilege expansion is authorized.']},
 'nextProductionChange':None,'decision':'No materially useful production change is demonstrated by retained evidence. Keepalive is already effective; both metadata-boundary/decode proposals regress typical public cases; freshSDK time and secure-context CPU alone are too small to explain the gap. Fixed-field allocations are an unmeasured hypothesis, not a qualified fix. Do not repeat the unchanged pair.',
 'performanceAcceptance':False,'A07':'failed/open','A21':'failed/open'}
(dest/'.gitattributes').write_text('* -text\n')
(dest/'assessment.json').write_text(json.dumps(assessment,indent=2)+'\n')
(b/'metadata-decode-transport-review-receipt.json').write_bytes((dest/'assessment.json').read_bytes())
note='A bounded redundant-metadata-decoder diagnostic retained26,404 differential comparisons (20,171 refusals), unchanged string/skip/capture/text source and all untrimmed15-observation timing arrays. Its actual one-CPU Node22.23.3 OS/child exit was0 with owned cleanup; reducing200-object fatal decodes401→200 did not support a production edit:56-object/16KiB median regressed0.952→1.022ms,200-object/16KiB3.802→3.984ms, and escaped56-object p951.435→1.951ms. The proposal was rejected. A read-only transport review confirms current operation-local keepalive already works: retained1k phase evidence has18 HTTP requests, four TLS handshakes and14 reused requests, with fresh SDK auth and destroy-at-finish; neither fixture nor request code forces Connection:close. The observer has no socket identity distribution, so exact per-socket request counts are unavailable. The earlier7e30 instrumented native window was113.151ms versus baseline77.042ms; first-native→last-end97.680 versus59.518ms and synchronous end-handler sums23.580 versus1.537ms include parser/listener/observer work.18 namespace reads under four active requests and the fixture12ms delay imply a five-wave60ms lower bound, not full wall causality. Inclusive capture13.254ms overlaps skip10.185ms; these cannot be added. No missing keepalive, material new production optimization, new paired run or A07/A21 pass is claimed. [Original rejected diagnostic and source-backed transport/phase assessment](implementation-evidence/metadata-decode-transport-review/assessment.json) preserve exact sources, SDK bytes, ownership, attempts and limitations.'
reviews=[]
for path in sorted((repo/'docs').rglob('*.md')):
 raw=path.read_bytes();raw.decode('utf-8-sig');updated=path.parent==repo/'docs' and path.name in ['BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-CONTROLLED-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md']
 reviews.append({'path':path.relative_to(repo).as_posix(),'beforeSha256':sha(raw),'updated':updated})
 if updated:
  eol='\r\n' if b'\r\n' in raw else '\n';path.write_bytes(raw+(eol+eol+note+eol).encode())
(dest/'doc-review.json').write_text(json.dumps(reviews,indent=2)+'\n')
print(json.dumps({'artifactCopies':len(copies),'docsChecked':len(reviews),'assessment':str(dest/'assessment.json'),'sha256':sha((dest/'assessment.json').read_bytes()),'productionChanged':False}))
