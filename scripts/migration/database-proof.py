#!/usr/bin/env python3
"""Start a copied MySQL database and check SQL metadata across restart."""
import argparse,datetime,json,pathlib,subprocess,time,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
def main():
 p=argparse.ArgumentParser();p.add_argument('--chart',required=True);args=p.parse_args();directory=ROOT/'k8s-rewrite/charts'/args.chart
 values=yaml.safe_load((directory/'values.yaml').read_text());name=yaml.safe_load((directory/'Chart.yaml').read_text())['name'];deployment=next(o for o in values['resources'] if o['kind']=='Deployment');ns=deployment['metadata']['namespace']
 copy=json.loads((ROOT/'evidence'/('copy-'+name+'.json')).read_text())
 if not copy['source_writers_stopped'] or not all(c['manifest_equal'] for c in copy['copies']):raise SystemExit('Accepted cold copy required')
 k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')];h=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')]
 subprocess.run(h+['upgrade','--install',name,str(directory),'-n',ns,'--set','enabled=true,migration.staging=true,replicaCount=1','--wait','--timeout','5m'],capture_output=True,check=True)
 query="SELECT table_schema,COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN ('mysql','sys','performance_schema','information_schema') GROUP BY table_schema;"
 # Both source databases use a generated root password. Validate through the
 # retained application account instead of assuming an available root secret.
 command='MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP -h127.0.0.1 -u"$MYSQL_USER" -N -e '+__import__('shlex').quote(query)
 def inspect():
  for _ in range(90):
   r=subprocess.run(k+['exec','-n',ns,'deployment/'+name,'--','sh','-c',command],capture_output=True,text=True)
   if r.returncode==0 and r.stdout.strip():return {line.split('\t')[0]:int(line.split('\t')[1]) for line in r.stdout.strip().splitlines()}
   time.sleep(2)
  raise RuntimeError('SQL metadata check failed; raw diagnostics suppressed')
 initial=inspect();subprocess.run(k+['rollout','restart','deployment/'+name,'-n',ns],capture_output=True,check=True);subprocess.run(k+['rollout','status','deployment/'+name,'-n',ns,'--timeout=300s'],capture_output=True,check=True);after=inspect()
 if initial!=after:raise RuntimeError('SQL schema table counts changed after restart')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'chart':args.chart,'namespace':ns,'sql_access_passed':True,'schema_table_counts':initial,'restart_sql_metadata_equal':True,'copied_source_manifest_verified':True,'production_routing_accepted':False,'source_originals_retained':True}
 (ROOT/'evidence'/('private-'+name+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
