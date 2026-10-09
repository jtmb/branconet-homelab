#!/usr/bin/env python3
"""Prepare the separately delivered app's deployment contract, never values."""
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    imported=json.loads((ROOT/'evidence/native-secret-import.json').read_text())
    if not imported['executed'] or not all(s['readback_equal'] for s in imported['secrets']):raise SystemExit('Native import must be verified first')
    namespaces=sorted({s['namespace'] for s in imported['secrets']}|{'default','flux-system','longhorn-system'})
    directory=ROOT/'k8s-rewrite/charts/apps/bortus'
    values=yaml.safe_load((directory/'values.yaml').read_text())
    labels={'app':'bortus'}
    resources=[{'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'bortus','namespace':'bortus'}}]
    for namespace in namespaces:
        resources.append({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'bortus-secrets','namespace':namespace},'rules':[{'apiGroups':[''],'resources':['secrets'],'verbs':['get','list','create','update']}]})
        resources.append({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'bortus-secrets','namespace':namespace},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'bortus-secrets'},'subjects':[{'kind':'ServiceAccount','name':'bortus','namespace':'bortus'}]})
    resources.extend([
        {'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':'bortus-data','namespace':'bortus'},'spec':{'storageClassName':'longhorn','accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'1Gi'}}}},
        {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'bortus','namespace':'bortus'},'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':labels},'template':{'metadata':{'labels':labels},'spec':{'serviceAccountName':'bortus','securityContext':{'fsGroup':1000},'containers':[{'name':'bortus','image':'{{ .Values.image }}','imagePullPolicy':'Never','ports':[{'name':'http','containerPort':4000}],'env':[{'name':'DATABASE_URL','value':'file:/data/bortus.db'},{'name':'BOTRUS_JWT_SECRET','valueFrom':{'secretKeyRef':{'name':'bortus-runtime','key':'jwt-secret'}}},{'name':'BOTRUS_SECRETS_KEY','valueFrom':{'secretKeyRef':{'name':'bortus-runtime','key':'lookup-token'}}},{'name':'BORTUS_SECRET_NAMESPACES','value':','.join(namespaces)},{'name':'BORTUS_SECRET_ALIASES_FILE','value':'/etc/bortus/aliases.json'}],'startupProbe':{'httpGet':{'path':'/api/health/live','port':4000},'periodSeconds':5,'failureThreshold':60},'livenessProbe':{'httpGet':{'path':'/api/health/live','port':4000},'periodSeconds':30},'readinessProbe':{'httpGet':{'path':'/api/health/ready','port':4000},'periodSeconds':30,'timeoutSeconds':15},'volumeMounts':[{'name':'data','mountPath':'/data'},{'name':'aliases','mountPath':'/etc/bortus','readOnly':True}],'resources':{'requests':{'cpu':'100m','memory':'256Mi'},'limits':{'memory':'1Gi'}}}],'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'bortus-data'}},{'name':'aliases','configMap':{'name':'bortus-secret-aliases'}}]}}}},
        {'apiVersion':'v1','kind':'Service','metadata':{'name':'bortus','namespace':'bortus'},'spec':{'selector':labels,'ports':[{'name':'http','port':4000,'targetPort':4000}]}}
    ])
    values['image']='bortus:migration-1438b27';values['resources']=resources
    values['migration']['state']='delivered-image-live-acceptance-pending'
    values['migration']['sourceCommit']='1438b278cdf21e98429b4836c018636b01b982a3'
    values['migration']['secretNamespaces']=namespaces
    values['migration']['dashboardRBACReviewPending']=True
    values['migration']['newPersistentNonsecretDatabase']='Existing operator/development databases remain retained; this first cluster deployment uses a new PVC. Never reset an existing production database.'
    (directory/'values.yaml').write_text(yaml.safe_dump(values,sort_keys=False))
    print(json.dumps({'chart':'apps/bortus','resources':len(resources),'native_secret_namespaces':namespaces,'enabled':False}))

if __name__=='__main__':main()
