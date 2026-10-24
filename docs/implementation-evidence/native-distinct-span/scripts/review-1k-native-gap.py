from pathlib import Path
import json,hashlib,statistics
b=Path(__file__).parent
p=b/'phase-scheduling-7e30.json';q=b/'characterize-phase-7e30b9b-complete/analysis-v2.json'
t=next(x for x in json.loads(p.read_bytes())['rows'] if x['source']=='candidate' and x['fixture']=='metadata-1000')['timeline']
a=next(x for x in json.loads(q.read_bytes())['rows'] if x['fixture']=='metadata-1000')
starts=sorted(x['startOffsetMs'] for x in t);ends=sorted(x['endCallbackOrWireEndOffsetMs'] for x in t)
gaps=[round(starts[i+4]-ends[i],3) for i in range(len(t)-4)]
record={'source':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','nonAcceptance':True,'inputs':[{'path':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in [p,q]],
 'scope':'Light read-only derivation from retained neutral single instrumented observation; no new runtime/endpoint measurement',
 'requestCount':len(t),'tlsConnections':a['tlsConnectionCount'],'sdkAsyncSumMs':a['sdkAsyncSumMs'],
 'firstFour':t[:4],'laterHeaderMedianMs':statistics.median(x['responseHeaderOffsetMs']-x['startOffsetMs'] for x in t[4:]),
 'sortedEndToNextRequestStartGapsMs':gaps,'gapMedianMs':statistics.median(gaps),'gapMaxMs':max(gaps),
 'endCallbackSynchronousSumMs':a['endEventHandlerSynchronousSumMs'],'bodyHeaderToEndBeforeHandlerSumMs':a['bodyHeaderToEndEventBeforeHandlerCombinedSumMs'],
 'postLastNativeEndToResponseEndCombinedMs':a['postLastNativeEndToResponseEndCombinedMs'],
 'codePointers':{'slot':'src/lib/secret-client.ts slot/release: active<=4 and bounded FIFO<=64; one operation starts four namespace workers',
 'settlement':'src/lib/secret-client.ts request response end resolves after complete parser/deadline checks; finally releases immediately without awaiting socket close',
 'agent':'src/lib/secret-client.ts listAgent: operation-owned equal-options direct pool, four sockets; first request wave must authenticate and establish TLS, remaining wave reuses it',
 'workers':'src/lib/cluster-secrets.ts SecretStore.list worker awaits complete namespace projection before claiming next scope',
 'metadata':'src/lib/secret-summary-json.ts captured metadata calls skip grammar then fatal decode and JSON.parse; each selected object is both grammar-scanned and materialized'},
 'findings':['The observation has no end-wait for TLS/socket closure in request source. Four TLS handshakes serve18 requests; no additional handshakes on later requests in this profile.',
 'Sorted completions versus replenishments expose small scheduler/auth gaps, not a measured35ms queue stall. This is aggregate matching, not correlated transport slot identity.',
 'Later header delays are near the frozen12ms wait. Initial TLS/request headers and synchronous end callbacks are the concrete remaining targets.',
 'Captured metadata grammar+fatal decode+JSON.parse is a plausible per-namespace processing target: capture inclusive13.254ms/skip inclusive10.185ms in sampled profile, overlapping not additive. No proposed bypass of complete validation or metadata identity.',
 'Long native-value scanner improvement addresses large-page CPU; it cannot by itself close the small1k endpoint gap.'],
 'missingEvidence':['No per-request slot-admission or release timestamp, socket-free/close timestamp, peer-request arrival correlation or isolated selected-metadata timing in retained observer.','Single instrumented observation includes Inspector/JSON wrapper overhead and startup/JIT effects.'],
 'recommendation':'Finish current exact source qualification. If endpoint regression persists, isolate existing first-wave transport scheduling and selected metadata capture under same bounds, rather than increase request concurrency or skip scopes.'}
(b/'native-distinct-span-preparation/remaining-1k-gap-review.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['requestCount','tlsConnections','sdkAsyncSumMs','laterHeaderMedianMs','gapMedianMs','gapMaxMs','sortedEndToNextRequestStartGapsMs','endCallbackSynchronousSumMs','bodyHeaderToEndBeforeHandlerSumMs','postLastNativeEndToResponseEndCombinedMs']},indent=2))
