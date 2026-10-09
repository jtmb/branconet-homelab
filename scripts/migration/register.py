#!/usr/bin/env python3
"""Build evidence-backed service coverage without exposing runtime secrets."""
import json
import pathlib
import yaml

REPO=pathlib.Path(__file__).resolve().parents[2]
MAP={
 'bot_ruckus':('apps/ruckus-bot','ruckus'), 'bot_ruckus-db':('apps/ruckus-db','ruckus'),
 'cicd_server-bootstrap':(None,None),'cicd_vault':(None,None),
 'gamesrv_mc-exporter':('apps/minecraft-exporter','games'),
 'mealie_mealie':('apps/mealie','mealie'),
 'media_bazarr':('media-stack/bazarr','plex'),'media_flaresolverr':('media-stack/flaresolverr','plex'),
 'media_jackett':('media-stack/jackett','plex'),'media_overseerr':('media-stack/overseerr','plex'),
 'media_radarr':('media-stack/radarr','plex'),'media_sonarr':('media-stack/sonarr','plex'),
 'media_tautulli':('media-stack/tautulli','plex'),'media_unpackerr':('media-stack/unpackerr','plex'),
 'media_xteve':('apps/xteve','plex'),'media_ytdl':('media-stack/ytdl','plex'),
 'pi_exporter':('apps/pihole-exporter','pihole'),'pi_pihole':('apps/pihole','pihole'),
 'portainer_agent':(None,None),'portainer_portainer':(None,None),
 'proxy_traefik':('@foundation/ingress','traefik'),'proxy_whoami':('test-stack/whoami','whoami'),
 'vault_vaultwarden':('apps/vaultwarden','vaultwarden'),
 'wordpress_db':('apps/wordpress-db','wordpress'),'wordpress_phpmyadmin':('apps/phpmyadmin','wordpress'),
 'wordpress_redis-db':('apps/wordpress-redis','wordpress'),'wordpress_wp-app':('apps/wordpress','wordpress'),
 'ws_aplb':('web-app-stack/aplb','web-apps'),'ws_homepage':('homepage','homepage'),
 'ws_lucinda':('web-app-stack/lucinda-art-gallery','web-apps'),
 'ws_mcwebsite':('apps/minecraft-website','web-apps'),'ws_santos':('web-app-stack/santos-web','web-apps')}
RETIRE={
 'cicd_server-bootstrap':'Vault Consul backend: retain consistent recovery data; retire only after native Secrets verification and user confirmation.',
 'cicd_vault':'Replace secrets function with native Kubernetes Secrets and BORTUS; retain recovery until final acceptance.',
 'portainer_agent':'Replace cluster-management function with BORTUS; record agent/socket dependency checks before retirement.',
 'portainer_portainer':'Replace management function with BORTUS; retain Portainer database and verify feature coverage before retirement.'}

def main():
 inventory=json.loads((REPO/'evidence/live-inventory.json').read_text())
 entries=[]
 for service in inventory['nodes']['192.168.0.4']['services']:
  name=service['name']
  if name not in MAP:raise RuntimeError('Unmapped live service: '+name)
  chart,namespace=MAP[name]
  instances=[{'host':host,**container} for host,node in inventory['nodes'].items() for container in node['containers'] if container['service']==name]
  entry={'source':name,'source_type':'swarm','chart':chart,'namespace':namespace,'status':'pending','source_image':service['image'],'source_declared_mounts':service['mounts'],'source_instances':instances,'source_ports':service['ports'],'source_routes':service['routes'],'environment_keys':service['environment_keys'],'backup':None,'copy_restore':None,'functional_checks':None,'restart_relocation':None,'rollback':None}
  if not chart:entry['replacement_contract']=RETIRE[name]
  entries.append(entry)
 for host,node in inventory['nodes'].items():
  for container in node['containers']:
   if container['service']:continue
   name=container['name']
   if name=='plex-plex-1':chart,namespace='media-stack/plex','plex';note='Consolidate to one active service; master configuration selected, worker configurations retained.'
   elif name=='qbittorrent':chart,namespace='media-stack/qbittorrent','plex';note='Preserve VPN sidecar attachment, config, downloads and port forwarding.'
   elif name=='GlueTun-proton':chart,namespace='apps/gluetun','plex';note='One VPN container in qBittorrent pod; own chart/values manage VPN PVC and integration parameters. Preserve ProtonVPN WireGuard.'
   elif name=='ets2-server':chart,namespace='apps/ets2','games';note='Preserve config and demonstrate game connectivity.'
   else:raise RuntimeError('Unmapped standalone container: '+name)
   entries.append({'source':host+'/'+name,'source_type':'standalone','chart':chart,'namespace':namespace,'status':'pending','source_instance':container,'contract':note,'backup':None,'copy_restore':None,'functional_checks':None,'restart_relocation':None,'rollback':None})
 represented={e['chart'] for e in entries if e['chart']}
 for path in sorted((REPO/'k8s-rewrite/charts').rglob('deployment.yaml')):
  chart=str(path.parent.relative_to(REPO/'k8s-rewrite/charts'))
  if chart in represented:continue
  objects=list(yaml.safe_load_all(path.read_text()))
  images=[c['image'] for o in objects if o and o.get('kind') in ['Deployment','DaemonSet','StatefulSet'] for c in o['spec']['template']['spec']['containers']]
  entries.append({'source':'repository/'+chart,'source_type':'repository-only','chart':chart,'namespace':next((o.get('metadata',{}).get('namespace') for o in objects if o),None),'source_images':images,'status':'pending','contract':'Repository application included even when absent from current Docker inventory. Validate its own values and dependencies.'})
 entries.append({'source':'repository/BORTUS','source_type':'management-dependency','chart':'apps/bortus','namespace':'bortus','status':'delegated-pending','contract':'Application code developed in separate chat; migration owns deployment and live native Secrets acceptance.'})
 report={'source_inventory_timestamp':inventory['captured_at'],'scope':'32 Swarm services, six standalone instances, repository-only workloads and BORTUS','entries':entries}
 (REPO/'evidence/service-register.json').write_text(json.dumps(report,indent=2)+'\n')
 lines=['# Migration service coverage','', 'Source: evidence/live-inventory.json. Every entry is pending until data/application checks are recorded. Application replacement is a contract to validate, not permission to discard source data.','','| Source | Chart / replacement | Namespace | Status |','|---|---|---|---|']
 for e in entries:lines.append('| '+e['source']+' | '+(e['chart'] or e['replacement_contract'])+' | '+(e['namespace'] or '—')+' | '+e['status']+' |')
 lines+=['','Detailed image, mount, route and test fields: [service-register.json](evidence/service-register.json).']
 (REPO/'SERVICE_REGISTER.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'entries':len(entries),'swarm':sum(e['source_type']=='swarm' for e in entries),'standalone':sum(e['source_type']=='standalone' for e in entries),'output':'SERVICE_REGISTER.md'}))

if __name__=='__main__':main()
