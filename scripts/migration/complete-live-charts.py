#!/usr/bin/env python3
"""Prepare missing workload manifests from measured, sanitized live sources.

No releases are activated. Source arguments, secret values and BORTUS code are
outside this generator; their integration stays an explicit review requirement.
"""
import json
import argparse
import math
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh-live',action='store_true',help='Replace prepared live manifests from source inventory; retained legacy files remain unchanged')
    args=parser.parse_args()
    register=json.loads((ROOT/'evidence/service-register.json').read_text())
    inventory=json.loads((ROOT/'evidence/live-inventory.json').read_text())
    sizes=json.loads((ROOT/'evidence/source-storage-sizes.json').read_text())
    measured={p['path']:p for items in sizes['nodes'].values() for p in items if p['complete']}
    seen=set();report=[]
    for entry in register['entries']:
        relative=entry.get('chart')
        if not relative or relative.startswith('@') or relative in seen:continue
        seen.add(relative)
        directory=ROOT/'k8s-rewrite/charts'/relative
        path=directory/'values.yaml';values=yaml.safe_load(path.read_text())
        if (values['resources'] and not args.refresh_live) or entry['source_type'] not in {'swarm','standalone'}:continue
        instance=entry.get('source_instance') or next(iter(entry.get('source_instances',[])),None)
        if not instance:continue
        name=yaml.safe_load((directory/'Chart.yaml').read_text())['name'];ns=entry['namespace']
        host=entry['source'].split('/')[0] if entry['source_type']=='standalone' else entry['source_instances'][0]['host']
        image=inventory['nodes'][host]['images'][instance['image_id']]
        digest=next(iter(image['repo_digests']),None)
        values['image']=entry.get('source_image') or digest or instance['image']
        ports=entry.get('source_ports') or [{'TargetPort':int(p.split('/')[0]),'Protocol':p.split('/')[1]} for p in image['exposed_ports'] if '-' not in p]
        unique={(int(p['TargetPort']),p.get('Protocol','tcp').upper()) for p in ports}
        container={'name':name,'image':'{{ .Values.image }}','envFrom':[{'secretRef':{'name':'{{ .Values.environmentSecret }}'}}]}
        if unique:container['ports']=[{'name':'p'+str(p)+'-'+protocol.lower(),'containerPort':p,'protocol':protocol} for p,protocol in sorted(unique)]
        if instance.get('cap_add'):container['securityContext']={'capabilities':{'add':instance['cap_add']}}
        mounts=[];volumes=[];objects=[];copy=[]
        for index,mount in enumerate(instance['mounts']):
            source=mount['Source'];target=mount.get('Destination') or mount.get('Target');volume='data-'+str(index)
            if mount['Type']=='volume':
                if entry['source']=='media_flaresolverr' and target=='/config':volumes.append({'name':volume,'emptyDir':{}})
                else:raise RuntimeError('Unmapped anonymous data: '+entry['source'])
            elif source=='/dev/shm':volumes.append({'name':volume,'emptyDir':{'medium':'Memory'}})
            elif source.startswith(('/var/run/','/var/lib/docker/volumes')):
                # Retained temporarily for source parity; retirement acceptance
                # requires removing this dependency from Homepage configuration.
                volumes.append({'name':volume,'hostPath':{'path':source}})
                values['migration'].setdefault('hostDockerDependencies',[]).append(source)
            elif source.startswith('/mnt/plex_smb_share') and 'ets2' not in source:
                claim=name+'-'+volume;pv=ns+'-'+claim
                smb='//192.168.0.8/plex_smb_share'+source.removeprefix('/mnt/plex_smb_share')
                objects.append({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':pv},'spec':{'capacity':{'storage':'1Gi'},'accessModes':['ReadWriteMany'],'persistentVolumeReclaimPolicy':'Retain','mountOptions':['noserverino','cache=none','uid=1000','gid=1000','file_mode=0755','dir_mode=0755'],'csi':{'driver':'smb.csi.k8s.io','volumeHandle':pv,'volumeAttributes':{'source':smb},'nodeStageSecretRef':{'name':'smb-creds','namespace':ns}}}})
                objects.append({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':claim,'namespace':ns},'spec':{'storageClassName':'','volumeName':pv,'accessModes':['ReadWriteMany'],'resources':{'requests':{'storage':'1Gi'}}}})
                volumes.append({'name':volume,'persistentVolumeClaim':{'claimName':claim}})
            elif source.startswith(('/dev/','/etc/')):
                volumes.append({'name':volume,'hostPath':{'path':source}})
            else:
                measurement=measured.get(source)
                if not measurement:raise RuntimeError('Unmeasured data path: '+source)
                claim=name+'-'+volume
                size=max(1,math.ceil((measurement['bytes']*2+512*1024**2)/1024**3))
                objects.append({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':claim,'namespace':ns},'spec':{'storageClassName':'longhorn','accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':str(size)+'Gi'}}}})
                volumes.append({'name':volume,'persistentVolumeClaim':{'claimName':claim}})
                copy.append({'sourceHost':'192.168.0.5' if source.startswith('/mnt/container-program-files') else host,'sourcePath':source,'destinationPVC':claim,'mountPath':target,'measuredBytes':measurement['bytes'],'allocatedGiB':size,'uid':measurement['uid'],'gid':measurement['gid']})
            mounts.append({'name':volume,'mountPath':target,'readOnly':mount.get('ReadOnly',not mount.get('RW',True))})
        if mounts:container['volumeMounts']=mounts
        pod={'containers':[container]}
        if volumes:pod['volumes']=volumes
        if instance.get('network_mode')=='host':pod.update({'hostNetwork':True,'dnsPolicy':'ClusterFirstWithHostNet'})
        if values['migration'].get('hostDockerDependencies'):pod['nodeSelector']={'kubernetes.io/hostname':inventory['nodes'][host]['hostname']}
        existing_deployment=next((o for o in values['resources'] if o.get('kind')=='Deployment'),None)
        annotations=(existing_deployment or {}).get('spec',{}).get('template',{}).get('metadata',{}).get('annotations',{})
        objects.insert(0,{'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':name,'namespace':ns},'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':name}},'template':{'metadata':{'labels':{'app':name},'annotations':annotations},'spec':pod}}})
        if unique:
            objects.append({'apiVersion':'v1','kind':'Service','metadata':{'name':name,'namespace':ns},'spec':{'selector':{'app':name},'ports':[{'name':'p'+str(p)+'-'+protocol.lower(),'port':p,'targetPort':p,'protocol':protocol} for p,protocol in sorted(unique)]}})
        routes=entry.get('source_routes',[])
        if routes and unique:
            port=next((p for p,protocol in sorted(unique) if protocol=='TCP'),None)
            if port:objects.append({'apiVersion':'networking.k8s.io/v1','kind':'Ingress','metadata':{'name':name,'namespace':ns},'spec':{'ingressClassName':'traefik','rules':[{'host':route,'http':{'paths':[{'path':'/','pathType':'Prefix','backend':{'service':{'name':name,'port':{'number':port}}}}]}} for route in routes]}})
        values['resources']=objects;values['migration']['state']='live-integration-review-pending';values['migration']['dataCopies']=copy
        values['migration']['storageSizingVerified']=True
        values['migration']['requiredEnvironmentKeys']=instance['environment_keys']
        source_service=next((s for s in inventory['nodes'][host]['services'] if s['name']==entry['source']),{})
        values['migration']['sourceCommandArgumentsRequireReview']=bool(source_service.get('command_argument_count'))
        path.write_text(yaml.safe_dump(values,sort_keys=False))
        report.append({'chart':relative,'objects':len(objects),'dataCopies':len(copy),'activated':False})
    # The original Docker container-network attachment becomes one shared pod.
    # The Gluetun chart owns its PVCs; its process runs as qBittorrent's sidecar.
    vpn_path=ROOT/'k8s-rewrite/charts/apps/gluetun/values.yaml'
    torrent_path=ROOT/'k8s-rewrite/charts/media-stack/qbittorrent/values.yaml'
    vpn=yaml.safe_load(vpn_path.read_text());torrent=yaml.safe_load(torrent_path.read_text())
    vpn_deployment=next((o for o in vpn['resources'] if o['kind']=='Deployment'),None)
    if vpn_deployment:
        vpn_pod=vpn_deployment['spec']['template']['spec']
        sidecar=vpn_pod['containers'][0]
        sidecar['image']=vpn['image']
        sidecar['envFrom']=[{'secretRef':{'name':vpn['environmentSecret']}}]
        sidecar['restartPolicy']='Always'
        sidecar['startupProbe']={'exec':{'command':['/gluetun-entrypoint','healthcheck']},'periodSeconds':5,'failureThreshold':60}
        sidecar['readinessProbe']={'exec':{'command':['/gluetun-entrypoint','healthcheck']},'periodSeconds':10}
        remap={v['name']:'vpn-'+v['name'] for v in vpn_pod.get('volumes',[])}
        for mount in sidecar.get('volumeMounts',[]):mount['name']=remap[mount['name']]
        for volume in vpn_pod.get('volumes',[]):volume['name']=remap[volume['name']]
        torrent_deployment=next(o for o in torrent['resources'] if o['kind']=='Deployment')
        torrent_pod=torrent_deployment['spec']['template']['spec']
        torrent_pod['initContainers']=[sidecar]
        torrent_pod.setdefault('volumes',[]).extend(vpn_pod.get('volumes',[]))
        vpn_source=next(e for e in register['entries'] if e['source']=='192.168.0.4/GlueTun-proton')['source_instance']
        forwarded_ports=[{'name':'p'+port.split('/')[0]+'-'+port.split('/')[1], 'port':int(port.split('/')[0]),'targetPort':int(port.split('/')[0]),'protocol':port.split('/')[1].upper()} for port in (vpn_source.get('ports') or {})]
        if forwarded_ports:
            torrent_service=next((o for o in torrent['resources'] if o['kind']=='Service'),None)
            if torrent_service:torrent_service['spec']['ports']=forwarded_ports
        vpn['resources']=[o for o in vpn['resources'] if o['kind'] not in {'Deployment','Service'}]
        vpn['migration']['processOwner']='plex/qbittorrent'
        torrent['migration']['vpnChartDependency']='apps/gluetun'
        torrent['migration']['vpnEgressAndFailureIsolationVerified']=False
        vpn_path.write_text(yaml.safe_dump(vpn,sort_keys=False));torrent_path.write_text(yaml.safe_dump(torrent,sort_keys=False))
    (ROOT/'evidence/live-chart-manifests.json').write_text(json.dumps({'charts':report,'activated':False},indent=2)+'\n')
    print(json.dumps({'charts_prepared':len(report),'activated':False}))

if __name__=='__main__':main()
