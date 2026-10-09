#!/usr/bin/env python3
"""Test existing Arr indexer configurations without saving changes or values."""
import argparse,base64,datetime,json,pathlib,shlex,subprocess,sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
parser=argparse.ArgumentParser()
parser.add_argument('--source-history',action='store_true',help='Read retained source SQLite status; sudo password on stdin only')
args=parser.parse_args()
source_history={}
if args.source_history:
    password=sys.stdin.readline().rstrip('\r\n')
    source_code='''import json,sqlite3
connection=sqlite3.connect('file:/mnt/nfs-container-volumes/radarr/radarr.db?mode=ro',uri=True)
tables={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
report={'source_read_only':True,'table_present':'IndexerStatus' in tables,'records':[]}
if 'IndexerStatus' in tables:
 columns=[row[1] for row in connection.execute('PRAGMA table_info(IndexerStatus)')]
 allowed=[column for column in columns if column in ['ProviderId','IndexerId','InitialFailure','MostRecentFailure','EscalationLevel','DisabledTill']]
 report['columns']=allowed
 if allowed:
  report['records']=[dict(zip(allowed,row)) for row in connection.execute('SELECT '+','.join(allowed)+' FROM IndexerStatus')]
print(json.dumps(report))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','sudo -S -p "" python3 -c '+shlex.quote(source_code)],input=(password+'\n').encode(),capture_output=True,timeout=30)
    del password
    if result.returncode:raise RuntimeError('Retained source read-only status query failed; details withheld')
    source_history=json.loads(result.stdout)
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
runtime=json.loads(subprocess.check_output(K+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
checks=[]
for app in ['sonarr','radarr']:
    service=json.loads(subprocess.check_output(K+['get','service',app,'-n','plex','-o','json']))
    base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
    key=base64.b64decode(runtime['data']['UN_'+app.upper()+'_0_API_KEY']).decode()
    code='''import copy,json,urllib.request,urllib.error,urllib.parse
base=BASE
headers={'X-Api-Key':KEY,'Content-Type':'application/json'}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(base+'/api/v3/'+path,headers=headers),timeout=20) as response:return json.loads(response.read())
indexers=get('indexer')
try:statuses=get('indexerstatus');status_metadata_http=200
except urllib.error.HTTPError as error:statuses=[];status_metadata_http=error.code
results=[]
def test(indexer):
 request=urllib.request.Request(base+'/api/v3/indexer/test',data=json.dumps(indexer).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(request,timeout=90) as response:response.read();return {'http_status':response.status,'reason_categories':[]}
 except urllib.error.HTTPError as error:
  try:body=json.loads(error.read());text=' '.join(str(e.get('errorMessage','')) for e in body) if isinstance(body,list) else str(body.get('message',''))
  except Exception:text=''
  lower=text.lower();categories=[name for name,terms in [('connection',['unable to connect','connection refused']),('timeout',['timed out','timeout']),('no_results',['no results']),('unsupported_categories',['categor']),('auth',['api key','unauthorized','authentication']),('challenge',['cloudflare','challenge','flaresolverr']),('rate_limit',['rate limit','too many requests']),('upstream_403',['403']),('upstream_404',['404']),('upstream_5xx',['500','502','503']),('dns',['name or service not known','name resolution','no such host']),('tracker_disabled',['disabled']),('tracker_unavailable',['indexer is unavailable','indexer not available']),('upstream_indexer_exception',['exception (','jackettindexerexception'])] if any(term in lower for term in terms)]
  return {'http_status':error.code,'reason_categories':categories or ['unclassified_validation_failure']}
 except (TimeoutError,urllib.error.URLError):return {'http_status':None,'reason_categories':['network_timeout_or_unreachable']}
for indexer in indexers:
 if not (indexer.get('enableRss') or indexer.get('enableAutomaticSearch') or indexer.get('enableInteractiveSearch')):continue
 fields=indexer.get('fields',[]);addresses=[]
 for field in fields:
  value=field.get('value')
  if isinstance(value,str) and value.startswith(('http://','https://')):
   parsed=urllib.parse.urlsplit(value);addresses.append({'hostname':parsed.hostname,'port':parsed.port,'scheme':parsed.scheme})
 tested=test(indexer);candidate_result=None
 if tested['http_status']!=200:
  candidate=copy.deepcopy(indexer);changed=False
  for field in candidate.get('fields',[]):
   value=field.get('value')
   if isinstance(value,str) and value.startswith(('http://','https://')):
    parsed=urllib.parse.urlsplit(value)
    if parsed.hostname in ['192.168.0.4','192.168.0.5','192.168.0.6']:
     field['value']=urllib.parse.urlunsplit(parsed._replace(netloc='jackett'+(':'+str(parsed.port) if parsed.port else '')));changed=True
  if changed:candidate_result=test(candidate)
 historic=next((s for s in statuses if s.get('providerId',s.get('indexerId'))==indexer['id']),{})
 results.append({'implementation':indexer.get('implementation'),'indexer_id':indexer['id'],'addresses':addresses,'test':tested,'internal_service_candidate_test':candidate_result,'status_metadata_http':status_metadata_http,'initial_failure':historic.get('initialFailure'),'most_recent_failure':historic.get('mostRecentFailure')})
print(json.dumps(results))
'''.replace('BASE',repr(base)).replace('KEY',repr(key))
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=240)
    if result.returncode:raise RuntimeError('Indexer metadata/test failed on '+app+'; response values withheld')
    checks.append({'application':app,'indexers':json.loads(result.stdout)})
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'retained_radarr_source_status':source_history,'configuration_saved':False,'downloads_started':False,'credentials_or_response_values_reported':False}
(ROOT/'evidence/media-indexer-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
