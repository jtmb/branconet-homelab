import copy,unittest
from coverage import validate,PROFILES,CALLS
def fixture(label):
 profiles=[];processes=[]
 for index,name in enumerate(PROFILES):
  objects=[334,200,1000,10000,25,3][index];identity='native-diag-'+str(index+1);stages={}
  for stage in ['native.factory','native.storeFactory','native.list','auth.authorize','auth.role','auth.session','response.envelope']+(['auth.middleware','auth.headerSession'] if label=='candidate' else []):stages[stage]={'calls':1,'failed':0}
  stages['auth.jwt']={'calls':2 if label=='candidate' else 1,'failed':0};stages['auth.accountSQL']={'calls':3 if label=='candidate' else 1,'failed':0};stages['native.summary']={'calls':objects}
  failures=[0,0,0,0,1,3][index] if label=='candidate' else 0;attempts=[]
  for number in range(CALLS[label][index]):
   auth='sdk.applyToHTTPSOptions' if label=='candidate' else 'sdk.applySecurityAuthentication'
   attempts.append({'id':number+1,'finished':True,'response_closed':True,'failed':number<failures,'status':200,'limit':[200,10,5][number] if number<failures else 200,'continued':False,'socket_id':1,'stages':{auth:{'calls':1,'failed':0},'sdk.applyOptions':{'calls':1,'failed':0}},'delivered_body_bytes':4*1024*1024+1 if number<failures else 123,'body_complete':number>=failures,'body_end_ms':2,'headers_ms':1,'decoded_body_utf8_bytes':123})
  entry={'id':identity,'finished':True,'status':200,'stages':stages,'attempts':attempts};processes.append({'capped':False,'node':'v22.23.3','tls':{'open':0},'request_records':[entry]})
  phase={'name':'native-secret-metadata','equivalent_expected_inventory':True,'expected_count':objects,'native_api_calls':CALLS[label][index],'requests':[{'request_id':identity,'status':200,'response_body_bytes':123}]}
  profiles.append({'fixture':{'name':name,'secret_objects':objects},'completed':True,'startups':[{}]*(5 if index==0 else 2),'phases':[phase]})
 processes.extend([{'capped':False,'node':'v22.23.3','tls':{'open':0},'request_records':[]} for _ in range(9)])
 return {'passed':True,'diagnostic_only':True,'failures':[],'profiles':profiles},processes
class Coverage(unittest.TestCase):
 def test_baseline_edge_scope_cannot_replace_required_node_coverage(self):
  for change in ['missing_node_jwt','invented_edge_middleware','invented_edge_header','missing_candidate_middleware']:
   with self.subTest(change=change):
    label='candidate' if change=='missing_candidate_middleware' else 'baseline';raw,processes=fixture(label);stages=processes[0]['request_records'][0]['stages']
    if change=='missing_node_jwt':stages['auth.jwt']['calls']=0
    elif change=='invented_edge_middleware':stages['auth.middleware']={'calls':1,'failed':0}
    elif change=='invented_edge_header':stages['auth.headerSession']={'calls':1,'failed':0}
    else:stages.pop('auth.middleware')
    with self.assertRaises((AssertionError,KeyError)):validate(raw,processes,label)
 def test_actual_fixed_shapes_both_sources(self):
  for label in CALLS:
   raw,processes=fixture(label);self.assertEqual(len(validate(raw,processes,label)),6)
 def test_omitted_extra_mismatched_ids_refused(self):
  for change in ['omitted','extra','mismatched','duplicate']:
   with self.subTest(change=change):
    raw,processes=fixture('candidate')
    if change=='omitted':processes[0]['request_records'].clear()
    elif change=='extra':processes[-1]['request_records'].append(copy.deepcopy(processes[0]['request_records'][0]))
    elif change=='mismatched':processes[0]['request_records'][0]['id']='native-diag-999'
    else:processes[1]['request_records'][0]['id']=processes[0]['request_records'][0]['id']
    with self.assertRaises(AssertionError):validate(raw,processes,'candidate')
 def test_missing_auth_prefix_inventory_or_closed_resources_refused(self):
  for change in ['auth','sdk_auth','prefix','inventory','capped','open_tls','process_count','incomplete_body','response_not_closed','failed_auth','wrong_reduction']:
   with self.subTest(change=change):
    raw,processes=fixture('candidate')
    if change=='auth':processes[0]['request_records'][0]['stages']['auth.accountSQL']['calls']=2
    elif change=='sdk_auth':processes[0]['request_records'][0]['attempts'][0]['stages']['sdk.applyToHTTPSOptions']['calls']=0
    elif change=='prefix':processes[4]['request_records'][0]['attempts'][0]['delivered_body_bytes']=0
    elif change=='inventory':raw['profiles'][0]['phases'][0]['expected_count']-=1
    elif change=='capped':processes[0]['capped']=True
    elif change=='open_tls':processes[0]['tls']['open']=1
    elif change=='process_count':processes.pop()
    elif change=='incomplete_body':processes[0]['request_records'][0]['attempts'][0]['body_complete']=False
    elif change=='response_not_closed':processes[0]['request_records'][0]['attempts'][0]['response_closed']=False
    elif change=='failed_auth':processes[0]['request_records'][0]['stages']['auth.jwt']['failed']=1
    else:processes[5]['request_records'][0]['attempts'][1]['limit']=20
    with self.assertRaises(AssertionError):validate(raw,processes,'candidate')
if __name__=='__main__':unittest.main()
