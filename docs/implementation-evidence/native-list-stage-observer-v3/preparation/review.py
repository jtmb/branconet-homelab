import argparse,hashlib,json,pathlib,subprocess
from coverage import validate
parser=argparse.ArgumentParser();parser.add_argument('work',type=pathlib.Path);parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args();assert not args.output.exists()
record=json.loads((args.work/'record.json').read_bytes());terminal=json.loads((args.work/'terminal.json').read_bytes())
handle=json.loads((args.work/'handle.json').read_bytes());launcher_handle=json.loads((args.work/'launcher-handle.json').read_bytes())
assert handle['owner']==launcher_handle['owner']==terminal['owner']==record['owner']
assert handle['supervisor_pid']==launcher_handle['supervisor_pid'] and launcher_handle['launcher_pid']==record['launcher_pid']
assert terminal['terminal'] and terminal['actual_launcher_exit_code']==0 and record['terminal'] and record['passed'] and not record['owned_live_containers']
assert record['image']=='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
assert [step['phase'] for step in record['steps']]==['inspect-image','build-baseline','build-candidate','runtime-baseline','runtime-candidate'] and all(step['exit_code']==0 for step in record['steps'])
owned=subprocess.run(['wsl','-d','Ubuntu','--exec','docker','ps','--format','{{.Names}}'],check=True,stdout=subprocess.PIPE).stdout.decode().splitlines()
assert not any(name.startswith('bortus-native-stage-') and name.endswith(record['owner']) for name in owned)
assert not (pathlib.Path(r'\\wsl.localhost\Ubuntu\proc')/str(record['launcher_pid'])).exists()
assert not (pathlib.Path(r'\\wsl.localhost\Ubuntu\proc')/str(handle['supervisor_pid'])).exists()
result={'scope':'Instrumented native stage explanation only, no acceptance pass','owner':record['owner'],'actual_launcher_exit_code':0,'closed_owned_resources':True,'sources':{},'unobserved_baseline_edge_stages':['auth.middleware','auth.headerSession','auth.jwt in Edge middleware'],'limitations':['Baseline Edge middleware/auth calls pass through; unobserved is never zero latency','Node/Edge differences are not causally attributed','Nested spans are inclusive','Observer overhead and concurrent stages prevent treating timing as acceptance','SDK processor residual is not proven deserialization cost','TLS open counts include sockets awaiting close events, not application request admission counts','No values/credentials/cache or auth weakening']}
for label in ['baseline','candidate']:
 expected_commit={'baseline':'51e8cd66379c1f40a95ea02f4da7c8aed848f2a4','candidate':'15786222e4b01b0692ad9aebab99b8734b505c7b'}[label]
 assert record['sources'][label]['commit']==expected_commit
 binding_folder=pathlib.Path(__file__).parent/('baseline-v3-51e8cd6' if label=='baseline' else 'candidate-v2-15786222')
 assert record['sources'][label]['binding_manifest']==json.loads((binding_folder/'manifest.json').read_bytes())
 assert hashlib.sha256((args.work/(label+'-original.tar.gz')).read_bytes()).hexdigest()==record['sources'][label]['archive_sha256']
 for name,digest in record['sources'][label]['instrumented_manifest'].items():
  assert hashlib.sha256((args.work/label/name).read_bytes()).hexdigest()==digest
 folder=args.work/(label+'-results');raw_bytes=(folder/(label+'-run-1.json')).read_bytes();raw=json.loads(raw_bytes)
 assert raw['source_commit']==record['sources'][label]['commit']
 processes=[json.loads(file.read_bytes()) for file in sorted(folder.glob('native-spans-*.json'))]
 lookup=validate(raw,processes,label)
 assert raw['enforced_limits']['memory_max']=='1073741824' and raw['enforced_limits']['swap_max']=='0' and raw['enforced_limits']['cpu_max']=='200000 100000' and raw['enforced_limits']['pids_max']=='256'
 result['sources'][label]={'commit':raw['source_commit'],'raw_sha256':hashlib.sha256(raw_bytes).hexdigest(),'native_HTTP_requests':6,'profiles':[{'name':profile['fixture']['name'],'http':next(phase for phase in profile['phases'] if phase['name']=='native-secret-metadata')['requests'][0],'observation':lookup[next(phase for phase in profile['phases'] if phase['name']=='native-secret-metadata')['requests'][0]['request_id']]} for profile in raw['profiles']]}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'native_stage_coverage_passed':True,'sources':2,'native_HTTP_requests_per_source':6,'actual_launcher_exit_code':0}))
