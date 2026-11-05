PROFILES=['audit-small','metadata-200','metadata-1000','metadata-10000','kv-sized-native-25','maximum-flat-native-3']
CALLS={'baseline':[18,18,18,54,18,18],'candidate':[18,18,18,54,21,22]}
def validate(raw,processes,label):
 assert raw['passed'] and raw['diagnostic_only'] and not raw['failures'] and label in CALLS
 assert [profile['fixture']['name'] for profile in raw['profiles']]==PROFILES
 assert [len(profile['startups']) for profile in raw['profiles']]==[5,2,2,2,2,2]
 assert len(processes)==15 and all(not process['capped'] and process['node']=='v22.23.3' and process['tls']['open']==0 for process in processes)
 entries=[entry for process in processes for entry in process['request_records']]
 assert len(entries)==6 and len({entry['id'] for entry in entries})==6
 lookup={entry['id']:entry for entry in entries};expected=[]
 for index,profile in enumerate(raw['profiles']):
  assert profile['completed']
  phase=[phase for phase in profile['phases'] if phase['name']=='native-secret-metadata'];assert len(phase)==1 and len(phase[0]['requests'])==1
  assert phase[0]['equivalent_expected_inventory'] and phase[0]['expected_count']==profile['fixture']['secret_objects']
  request=phase[0]['requests'][0];expected.append(request['request_id']);assert request['status']==200 and request['response_body_bytes']>0
  assert request['request_id'] in lookup;entry=lookup[request['request_id']];assert entry['finished'] and entry['status']==200
  for name in ['native.factory','native.storeFactory','native.list','auth.authorize','auth.role','auth.session','response.envelope']+(['auth.middleware','auth.headerSession'] if label=='candidate' else []):
   assert entry['stages'][name]['calls']==1 and entry['stages'][name]['failed']==0
  if label=='baseline':assert 'auth.middleware' not in entry['stages'] and 'auth.headerSession' not in entry['stages']
  assert entry['stages']['auth.jwt']['calls']==(2 if label=='candidate' else 1) and entry['stages']['auth.accountSQL']['calls']==(3 if label=='candidate' else 1)
  assert entry['stages']['auth.jwt']['failed']==entry['stages']['auth.accountSQL']['failed']==0
  assert entry['stages']['native.summary']['calls']==profile['fixture']['secret_objects']
  attempts=entry['attempts'];assert len(attempts)==CALLS[label][index]==phase[0]['native_api_calls'] and [attempt['id'] for attempt in attempts]==list(range(1,len(attempts)+1))
  for attempt in attempts:
   assert attempt['finished'] and attempt['response_closed'] and attempt['status']==200 and 1<=attempt['limit']<=200 and isinstance(attempt['continued'],bool) and attempt['socket_id']>0
   auth='sdk.applyToHTTPSOptions' if label=='candidate' else 'sdk.applySecurityAuthentication'
   assert attempt['stages'][auth]['calls']==1 and attempt['stages']['sdk.applyOptions']['calls']==1
   assert attempt['stages'][auth]['failed']==attempt['stages']['sdk.applyOptions']['failed']==0
   if attempt['failed']:
    assert label=='candidate' and index>=4 and attempt['delivered_body_bytes']>4*1024*1024
   else:
    assert attempt['body_complete'] and attempt['body_end_ms']>=attempt['headers_ms'] and attempt['decoded_body_utf8_bytes']>0
  assert sum(attempt['failed'] for attempt in attempts)==([0,0,0,0,1,3][index] if label=='candidate' else 0)
  if label=='candidate':assert [attempt['limit'] for attempt in attempts if attempt['failed']]==([200] if index==4 else [200,10,5] if index==5 else [])
 assert len(set(expected))==6 and set(expected)==set(lookup)
 return lookup
