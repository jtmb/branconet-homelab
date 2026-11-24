#!/usr/bin/env python3
"""Retain service names embedded in copied application configuration."""
import pathlib,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]
for name,aliases,port in [('wordpress-db',['mysql-db','db'],3306),('wordpress-redis',['redis-db'],6379)]:
 path=ROOT/'k8s-rewrite/charts/apps'/name/'values.yaml';values=yaml.safe_load(path.read_text())
 for alias in aliases:
  if any(o['kind']=='Service' and o['metadata']['name']==alias for o in values['resources']):continue
  values['resources'].append({'apiVersion':'v1','kind':'Service','metadata':{'name':alias,'namespace':'wordpress'},'spec':{'type':'ClusterIP','selector':{'app':name},'ports':[{'name':'tcp','port':port,'targetPort':port}]}})
 if name=='wordpress-redis':
  deployment=next(o for o in values['resources'] if o['kind']=='Deployment');pod=deployment['spec']['template']['spec']
  pod['volumes']=[{'name':'data','persistentVolumeClaim':{'claimName':'wordpress-redis-data'}}]
  pod['containers'][0]['volumeMounts']=[{'name':'data','mountPath':'/data'}]
  if not any(o['kind']=='PersistentVolumeClaim' for o in values['resources']):
   values['resources'].append({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':'wordpress-redis-data','namespace':'wordpress','annotations':{'helm.sh/resource-policy':'keep'}},'spec':{'storageClassName':'longhorn','accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'1Gi'}}}})
 path.write_text(yaml.safe_dump(values,sort_keys=False))
print('Embedded database service aliases and retained Redis claim prepared')
