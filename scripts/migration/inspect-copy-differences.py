#!/usr/bin/env python3
"""Read-only comparison of retained partial claims; never overwrite either side."""
import argparse,datetime,hashlib,json,pathlib,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--chart',required=True);args=parser.parse_args();directory=ROOT/'k8s-rewrite/charts'/args.chart;values=yaml.safe_load((directory/'values.yaml').read_text());name=yaml.safe_load((directory/'Chart.yaml').read_text())['name']
 copy=values['migration']['dataCopies'][0];deployment=next(o for o in values['resources'] if o['kind']=='Deployment');ns=deployment['metadata']['namespace'];podname='compare-'+name
 k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
 pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':podname,'namespace':ns},'spec':{'nodeName':{'192.168.0.4':'masternode','192.168.0.5':'workernode2','192.168.0.6':'workernode1'}[copy['sourceHost']],'restartPolicy':'Never','automountServiceAccountToken':False,'terminationGracePeriodSeconds':5,'containers':[{'name':'compare','image':'python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1','command':['python3','-c','import time;time.sleep(900)'],'volumeMounts':[{'name':'source','mountPath':'/source','readOnly':True},{'name':'target','mountPath':'/target','readOnly':True}]}],'volumes':[{'name':'source','hostPath':{'path':copy['sourcePath'],'type':'Directory'}},{'name':'target','persistentVolumeClaim':{'claimName':copy['destinationPVC'],'readOnly':True}}]}}
 subprocess.run(k+['create','-f','-'],input=json.dumps(pod).encode(),capture_output=True,check=True)
 try:
  subprocess.run(k+['wait','pod/'+podname,'-n',ns,'--for=condition=Ready','--timeout=300s'],capture_output=True,check=True)
  import importlib.util
  spec=importlib.util.spec_from_file_location('coldcopy',ROOT/'scripts/migration/copy-application-data.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  manifest=m.COPY[m.COPY.index('def manifest('):m.COPY.index('before=manifest(source)')]
  code='import pathlib,stat,hashlib,os,json\nsource=pathlib.Path("/source");target=pathlib.Path("/target")\n'+manifest+'''\na=manifest(source);b=manifest(target)
differences=[]
for name in sorted(set(a)|set(b)):
 if a.get(name)!=b.get(name):
  fields=[key for key in set(a.get(name,{}) or {})|set(b.get(name,{}) or {}) if (a.get(name,{}) or {}).get(key)!=(b.get(name,{}) or {}).get(key)]
  differences.append({'path_hash':hashlib.sha256(name.encode()).hexdigest(),'fields':fields,'source_missing':name not in a,'target_missing':name not in b})
print(json.dumps({'equal':not differences,'source_entries':len(a),'target_entries':len(b),'differences':differences[:30]}))
'''
  r=subprocess.run(k+['exec','-i','-n',ns,podname,'--','python3','-'],input=code.encode(),capture_output=True,check=True);report=json.loads(r.stdout);report['chart']=args.chart
  (ROOT/'evidence'/('compare-'+name+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 finally:subprocess.run(k+['delete','pod',podname,'-n',ns,'--wait=true'],capture_output=True)
if __name__=='__main__':main()
