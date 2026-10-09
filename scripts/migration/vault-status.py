#!/usr/bin/env python3
"""Authorized Vault unseal and metadata-only verification; credentials on stdin."""
import datetime
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

def main():
 request=json.load(sys.stdin);base='http://192.168.0.4:8200'
 def call(path,method='GET',body=None,authenticated=False):
  headers={'Content-Type':'application/json'}
  if authenticated:headers['X-Vault-Token']=request['root_token']
  operation=urllib.request.Request(base+'/v1/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
  try:
   with urllib.request.urlopen(operation,timeout=15) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as error:
   if path=='sys/health':return error.code,json.load(error)
   raise RuntimeError('Vault '+path+' returned HTTP '+str(error.code)) from None
 code,health=call('sys/health')
 if health.get('sealed'):
  call('sys/unseal','PUT',{'key':request['unseal_key']})
  code,health=call('sys/health')
 for attempt in range(15):
  if code==200 and not health.get('sealed') and not health.get('standby'):break
  time.sleep(1);code,health=call('sys/health')
 if code!=200 or health.get('sealed'):raise SystemExit('Vault is not active and unsealed')
 _,listing=call('kv/metadata/','LIST',authenticated=True)
 records=[]
 def walk(prefix,keys):
  for key in keys:
   path=prefix+key
   if key.endswith('/'):
    _,nested=call('kv/metadata/'+path,'LIST',authenticated=True);walk(path,nested['data']['keys'])
   else:
    _,value=call('kv/data/'+path,authenticated=True)
    fields=value['data']['data'];metadata=value['data']['metadata']
    records.append({'path':path,'version':metadata['version'],'keys':sorted(fields),'types':{name:type(item).__name__ for name,item in fields.items()}})
 walk('',listing['data']['keys'])
 report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'health_http_status':code,'initialized':health.get('initialized'),'sealed':health.get('sealed'),'standby':health.get('standby'),'records':records,'record_count':len(records),'value_count':sum(len(r['keys']) for r in records),'redaction':'Values, tokens and unseal material omitted'}
 path=pathlib.Path(request['evidence_output']);path.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'evidence':str(path),'health_http_status':code,'sealed':health['sealed'],'record_count':len(records),'value_count':report['value_count']}))

if __name__=='__main__':main()
