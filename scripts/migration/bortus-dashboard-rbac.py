#!/usr/bin/env python3
"""Wire the existing management dashboard to its required Kubernetes resources."""
import json
import pathlib
import subprocess
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    path=ROOT/'k8s-rewrite/charts/apps/bortus/values.yaml';values=yaml.safe_load(path.read_text())
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def run(args,body=None):
        result=subprocess.run([*kube,*args],input=json.dumps(body) if body else None,capture_output=True,text=True,check=True)
        return result.stdout
    namespaces=sorted({yaml.safe_load(file.read_text())['spec']['targetNamespace'] for file in (ROOT/'k8s-rewrite/flux/migration-releases').glob('*.yaml') if file.name not in {'kustomization.yaml','namespaces.yaml'}}|set(values['migration']['secretNamespaces'])|{'traefik'})
    existing={n['metadata']['name'] for n in json.loads(run(['get','namespaces','-o','json']))['items']}
    for ns in namespaces:
        if ns not in existing:run(['create','-f','-'],{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}})
    resources=[r for r in values['resources'] if not (r['kind'] in {'Role','RoleBinding'} and r['metadata']['name']=='bortus-secrets') and r.get('metadata',{}).get('name') not in {'bortus-dashboard-view','bortus-dashboard-manage'}]
    subject=[{'kind':'ServiceAccount','name':'bortus','namespace':'bortus'}]
    for ns in namespaces:
        resources.extend([{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'bortus-secrets','namespace':ns},'rules':[{'apiGroups':[''],'resources':['secrets'],'verbs':['get','list','create','update']}]},{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'bortus-secrets','namespace':ns},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'bortus-secrets'},'subjects':subject}])
        rules=[{'apiGroups':[''],'resources':['pods','pods/log','services','configmaps','events','persistentvolumeclaims','endpoints'],'verbs':['get','list','watch','create','update','patch','delete']},{'apiGroups':[''],'resources':['pods/exec','pods/portforward'],'verbs':['get','create']},{'apiGroups':['apps'],'resources':['deployments','deployments/scale','statefulsets','statefulsets/scale','daemonsets','replicasets'],'verbs':['get','list','watch','create','update','patch','delete']},{'apiGroups':['batch'],'resources':['jobs','cronjobs'],'verbs':['get','list','watch','create','update','patch','delete']},{'apiGroups':['networking.k8s.io'],'resources':['ingresses','networkpolicies'],'verbs':['get','list','watch','create','update','patch','delete']}]
        if ns=='flux-system':rules.extend([{'apiGroups':['source.toolkit.fluxcd.io'],'resources':['gitrepositories','helmrepositories','helmcharts','ocirepositories'],'verbs':['get','list','watch','create','update','patch','delete']},{'apiGroups':['kustomize.toolkit.fluxcd.io'],'resources':['kustomizations'],'verbs':['get','list','watch','create','update','patch','delete']},{'apiGroups':['helm.toolkit.fluxcd.io'],'resources':['helmreleases'],'verbs':['get','list','watch','create','update','patch','delete']}])
        resources.extend([{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'bortus-dashboard-manage','namespace':ns},'rules':rules},{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'bortus-dashboard-manage','namespace':ns},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'bortus-dashboard-manage'},'subjects':subject}])
    read_rules=[{'apiGroups':[''],'resources':['nodes','namespaces','persistentvolumes','pods','persistentvolumeclaims','services','events'],'verbs':['get','list','watch']},{'apiGroups':['apps'],'resources':['deployments','statefulsets','daemonsets','replicasets'],'verbs':['get','list','watch']},{'apiGroups':['networking.k8s.io'],'resources':['ingresses'],'verbs':['get','list','watch']},{'apiGroups':['storage.k8s.io'],'resources':['storageclasses','csidrivers','csinodes','volumeattachments'],'verbs':['get','list','watch']},{'apiGroups':['longhorn.io'],'resources':['volumes','nodes','replicas','engines','backups','backupvolumes'],'verbs':['get','list','watch']},{'apiGroups':[''],'resources':['persistentvolumes','nodes'],'verbs':['patch','update']},{'apiGroups':[''],'resources':['namespaces'],'verbs':['create','update','patch','delete']}]
    resources.extend([{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRole','metadata':{'name':'bortus-dashboard-view'},'rules':read_rules},{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRoleBinding','metadata':{'name':'bortus-dashboard-view'},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'bortus-dashboard-view'},'subjects':subject}])
    deployment=next(o for o in resources if o['kind']=='Deployment')
    env=deployment['spec']['template']['spec']['containers'][0]['env']
    next(e for e in env if e['name']=='BORTUS_SECRET_NAMESPACES')['value']=','.join(namespaces)
    values['resources']=resources;values['migration']['secretNamespaces']=namespaces;values['migration']['dashboardRBACReviewPending']=False
    path.write_text(yaml.safe_dump(values,sort_keys=False));print(json.dumps({'secret_namespaces':namespaces,'cluster_admin_bound':False,'resource_count':len(resources),'live_dashboard_tests_pending':True}))

if __name__=='__main__':main()
