#!/usr/bin/env python3
"""Prepare one validated-source Flux path, with per-chart gated values."""
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    target=ROOT/'k8s-rewrite/flux/migration-releases';target.mkdir(parents=True,exist_ok=True)
    resources=[];namespaces=set();summary=[]
    for chart in sorted((ROOT/'k8s-rewrite/charts').rglob('Chart.yaml')):
        directory=chart.parent;metadata=yaml.safe_load(chart.read_text());values=yaml.safe_load((directory/'values.yaml').read_text());name=metadata['name']
        namespace=next((obj['metadata']['namespace'] for obj in values['resources'] if obj.get('metadata',{}).get('namespace')),None)
        if not namespace:raise RuntimeError('Chart namespace is not defined: '+name)
        namespaces.add(namespace)
        for obj in values['resources']:
            if obj['kind'] in {'PersistentVolumeClaim','PersistentVolume'}:obj.setdefault('metadata',{}).setdefault('annotations',{})['helm.sh/resource-policy']='keep'
            if obj['kind']=='Service':
                obj['spec']['type']='ClusterIP';obj['spec'].pop('externalIPs',None)
                for port in obj['spec'].get('ports',[]):port.pop('nodePort',None)
        (directory/'values.yaml').write_text(yaml.safe_dump(values,sort_keys=False))
        relative=str(directory.relative_to(ROOT)).replace('\\','/')
        overrides={'enabled':False,'replicaCount':0}
        if name=='bortus':overrides={'enabled':True,'replicaCount':1,'migration':{'staging':True}}
        release={'apiVersion':'helm.toolkit.fluxcd.io/v2','kind':'HelmRelease','metadata':{'name':name,'namespace':'flux-system'},'spec':{'interval':'5m','releaseName':name,'targetNamespace':namespace,'storageNamespace':namespace,'timeout':'8m','chart':{'spec':{'chart':'./'+relative,'sourceRef':{'kind':'GitRepository','name':'migration-validated','namespace':'flux-system'},'reconcileStrategy':'Revision','interval':'1m'}},'install':{'remediation':{'retries':0}},'upgrade':{'remediation':{'retries':0}},'values':overrides}}
        file=name+'.yaml';(target/file).write_text(yaml.safe_dump(release,sort_keys=False));resources.append(file)
        summary.append({'release':name,'namespace':namespace,'chart':relative,'enabled':overrides['enabled']})
    objects=[{'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace,'annotations':{'kustomize.toolkit.fluxcd.io/prune':'disabled'}}} for namespace in sorted(namespaces)]
    (target/'namespaces.yaml').write_text(yaml.safe_dump_all(objects,sort_keys=False));resources.insert(0,'namespaces.yaml')
    (target/'kustomization.yaml').write_text(yaml.safe_dump({'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':resources},sort_keys=False))
    foundation=[{'apiVersion':'source.toolkit.fluxcd.io/v1','kind':'GitRepository','metadata':{'name':'migration-validated','namespace':'flux-system'},'spec':{'interval':'1m','url':'https://github.com/jtmb/branconet-homelab.git','ref':{'branch':'codex/kubernetes-validated'},'ignore':'/.git\n'}},{'apiVersion':'kustomize.toolkit.fluxcd.io/v1','kind':'Kustomization','metadata':{'name':'migration-releases','namespace':'flux-system'},'spec':{'interval':'1m','path':'./k8s-rewrite/flux/migration-releases','prune':False,'sourceRef':{'kind':'GitRepository','name':'migration-validated'},'wait':True,'timeout':'8m'}}]
    (ROOT/'k8s-rewrite/flux/migration-source.yaml').write_text(yaml.safe_dump_all(foundation,sort_keys=False))
    print(json.dumps({'releases':len(summary),'namespaces':sorted(namespaces),'enabled':[item for item in summary if item['enabled']],'source_branch':'codex/kubernetes-validated','activated':False}))

if __name__=='__main__':main()
