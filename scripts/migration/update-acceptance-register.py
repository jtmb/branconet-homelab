#!/usr/bin/env python3
"""Enrich the retained source register with scoped evidence and live metadata.

Never regenerate the source inventory or alter application acceptance reports.
No Secret values, workload environments, raw arguments or response bodies are read.
"""
import datetime,json,pathlib,subprocess,yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]

def read(name):
    return json.loads((ROOT/'evidence'/name).read_text())

def live(kind):
    return json.loads(subprocess.check_output(K+['get',kind,'-A','-o','json']))['items']

claims={(o['metadata']['namespace'],o['metadata']['name']):o for o in live('pvc')}
releases={(o['spec'].get('targetNamespace',o['metadata']['namespace']),o['spec'].get('releaseName',o['metadata']['name'])):o for o in live('helmrelease')}
backups=read('native-volume-backups.json')['volumes']
monitor=read('monitor-state-backup.json')
routes={o['host']:o for o in read('final-routing-proof.json')['checks']}
ports=read('application-port-cutover.json')
extra={
 'plex':['plex-library-proof.json','plex-relocation-proof.json','plex-playback-proof.json'],
 'qbittorrent':['qbittorrent-api-proof.json','qbittorrent-credential-review.json','media-download-client-proof.json','final-vpn-egress.json'],
 'gluetun':['vpn-proof.json','final-vpn-egress.json'],
 'qbit-monitor':['private-qbit-monitor.json','monitor-state-backup.json'],
 'unpackerr':['unpackerr-extraction-proof.json'],
 'sonarr':['media-download-client-proof.json','media-import-prerequisites.json','media-indexer-proof.json'], 'radarr':['media-download-client-proof.json','media-import-prerequisites.json','media-indexer-proof.json'],
 'ets2':['ets2-query-proof.json'], 'xteve':['xteve-tuner-proof.json'],
 'pihole':['native-dns-proof.json','native-lan-forwarding.json'],
 'pihole-exporter':['pihole-exporter-integration.json'],
 'bortus':['bortus-live-proof.json','bortus-dashboard-proof.json','native-bortus-restore.json'],
 'http-echo':['pipeline-rollback-proof.json'], 'wordpress':['native-acme-proof.json'],
 'flaresolverr':['flaresolverr-browser-proof.json'], 'wordpress-redis':['redis-current-backup.json','redis-persistence.json'],
}
limitations={
 'wordpress-redis':['Original source writable /data state removed before archival; unrecovered; user acceptance exception unresolved.'],
 'qbit-monitor':['Discord delivery untested; notifications disabled during acceptance.'],
 'ets2':['Real game-client join untested.'],
 'xteve':['SSDP/multicast discovery untested; original TCP 1901 has no observed backend listener.'],
 'unpackerr':['Owned SMB fixture extracted successfully; completed real Arr download/import untested.'],
 'sonarr':['API/download-client checks passed; completed real download/import untested.'],
 'radarr':['API/download-client checks passed; completed real download/import untested.','Two enabled indexers fail current configuration tests and have retained pre-migration failure history; settings unchanged.'],
}

def secret_refs(value,result):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('secretKeyRef','secretRef') and isinstance(item,dict) and item.get('name'):
                result.add((item['name'],item.get('key','*')))
            elif key=='secretName' and isinstance(item,str):result.add((item,'*'))
            else:secret_refs(item,result)
    elif isinstance(value,list):
        for item in value:secret_refs(item,result)

register=read('service-register.json')
for e in register['entries']:
    chart=e.get('chart');ns=e.get('namespace');name=chart.rsplit('/',1)[-1] if chart else None
    e['acceptance_scope']='Recorded checks only; running/HTTP/TCP do not imply untested application integrations.'
    e['rollback']={'instructions':'docs/MIGRATION-OPERATIONS.md','after_destination_writes':'Stop destination writers, checkpoint and reconcile changed data into a reviewed recovery copy before restoring source traffic.','original_configuration':'evidence/config-backups.json','source_data_retirement_confirmed':False}
    if not chart or chart.startswith('@'):
        e['backup']={'evidence':['evidence/data-backups.json','evidence/config-backups.json','evidence/archive-verification.json'],'originals_retained':True}
        e['copy_restore']={'replacement_contract':e.get('replacement'),'evidence':['evidence/native-secret-import.json','evidence/bortus-live-proof.json','evidence/bortus-dashboard-proof.json'] if e['source'].startswith(('cicd_','portainer_')) else ['evidence/ingress-certificates.json','evidence/network-port-cutover.json']}
        e['functional_checks']={'status':'Replacement evidence recorded; source retirement pending','legacy_route_gap':['proxy.branconet.lan dashboard equivalence not established'] if chart else []}
        if chart=='@foundation/ingress' and (ROOT/'evidence/traefik-dashboard-proof.json').exists():
            dashboard=read('traefik-dashboard-proof.json')
            e['functional_checks']={'status':'Original dashboard route/auth hashes restored; authenticated login/API proof pending' if not dashboard['live_dashboard_accepted'] else 'Original dashboard authenticated/API proof passed','evidence':['evidence/traefik-dashboard-proof.json','evidence/final-routing-proof.json','evidence/inotify-instance-recovery.json'],'legacy_route_gap':[] if dashboard['live_dashboard_accepted'] else ['Working dashboard credential required for authenticated UI/API proof']}
            e['copy_restore']['evidence'].append('evidence/etcd-recovery.json')
            e['status']=e['functional_checks']['status']
            e['migration_status']=e['status']
            e['restart_relocation']={'evidence':'evidence/inotify-instance-recovery.json','status':'Actual two-replica ingress restart after watcher-limit recovery; see live dashboard proof'}
        e['restart_relocation']={'status':'See replacement evidence; retained source not retired'}
        continue
    values=yaml.safe_load((ROOT/'k8s-rewrite/charts'/chart/'values.yaml').read_text())
    resources=values.get('resources',[]);refs=set();secret_refs(resources,refs)
    claim_names=[o['metadata']['name'] for o in resources if o['kind']=='PersistentVolumeClaim']
    destinations=[]
    for claim in claim_names:
        actual=claims.get((ns,claim));spec=actual['spec'] if actual else {}
        destinations.append({'namespace':ns,'claim':claim,'bound':bool(actual and actual.get('status',{}).get('phase')=='Bound'),'storage_class':spec.get('storageClassName'),'volume':spec.get('volumeName')})
    native_backups=[{'claim':b['claim'],'volume':b['volume'],'backup':b['backup'],'state':b['backup_state']} for b in backups if b['namespace']==ns and b['claim'] in claim_names]
    if name=='qbit-monitor':native_backups.append({'claim':monitor['claim'],'volume':monitor['volume'],'backup':monitor['backup'],'state':'Completed' if monitor['nas_backup_completed'] else 'Pending'})
    longhorn_claims=[c['claim'] for c in destinations if c['storage_class']=='longhorn']
    backed={b['claim'] for b in native_backups if b['state']=='Completed'}
    e['destination_storage']=destinations
    e['native_secret_references']=[{'namespace':ns,'name':n,'key':key} for n,key in sorted(refs)]
    e['backup']={'source_evidence':['evidence/data-backups.json','evidence/config-backups.json'],'native_evidence':['evidence/native-volume-backups.json']+(['evidence/monitor-state-backup.json'] if name=='qbit-monitor' else []),'native_backups':native_backups,'unbacked_active_longhorn_claims':sorted(set(longhorn_claims)-backed),'originals_retained':True,'scope_exception':limitations.get(name,[]) if name=='wordpress-redis' else []}
    copy=e.get('copy_evidence');copied=read(pathlib.Path(copy).name) if copy else None
    e['copy_restore']={'evidence':copy,'full_manifest_equal':all(c.get('manifest_equal',False) for c in copied.get('copies',[])) if copied and copied.get('copies') else None,'source_stable':all(c.get('source_stable',False) for c in copied.get('copies',[])) if copied and copied.get('copies') else None,'restore_evidence':['evidence/native-bortus-restore.json'] if name=='bortus' else [],'historical_redis_recovered':False if name=='wordpress-redis' else None}
    private=e.get('private_evidence');proof=read(pathlib.Path(private).name) if private else {}
    e['functional_checks']={'evidence':([private] if private else [])+['evidence/'+f for f in extra.get(name,[]) if (ROOT/'evidence'/f).exists()],'recorded_boolean_checks':{key:value for key,value in proof.items() if isinstance(value,bool)},'limitations':limitations.get(name,[])}
    e['restart_relocation']={'evidence':private,'restart_passed':any(proof.get(key) is True for key in ('restart_http_passed','restart_sql_metadata_equal','actual_restart_passed','actual_process_restart_passed')),'relocation_passed':proof.get('relocation_http_passed') is True,'additional_evidence':['evidence/plex-relocation-proof.json'] if name=='plex' else [],'claim_identity_evidence':proof.get('persistent_claim_identity_verified',[])}
    ingress_hosts=[r['host'] for o in resources if o['kind']=='Ingress' for r in o.get('spec',{}).get('rules',[])]
    route_checks=[{'host':host,'responding':routes.get(host,{}).get('responding',False),'https_status':routes.get(host,{}).get('https_status')} for host in ingress_hosts]
    published=next((s for s in ports['services'] if s['source']==e['source']),None)
    tcp=[c for c in ports['tcp_checks'] if published and c['port'] in published['published_ports']]
    ready=any(c['type']=='Ready' and c['status']=='True' for c in releases.get((ns,name),{}).get('status',{}).get('conditions',[]))
    e['production_routing']={'ingress_checks':route_checks,'legacy_tcp_checks':tcp,'evidence':['evidence/final-routing-proof.json','evidence/application-port-cutover.json'],'scope':'HTTP response and TCP connectivity; full application behavior uses separate evidence.'}
    e['production_routing_accepted']=bool((route_checks or tcp) and all(c['responding'] for c in route_checks) and all(c['tcp_open'] for c in tcp))
    e['native_helmrelease_ready']=ready
    e['migration_status']='Native HelmRelease Ready; recorded checks passed; source retirement pending' if ready else 'Native HelmRelease readiness requires investigation'
    if name=='wordpress-redis':e['migration_status']='Native current Redis works; historical data acceptance unresolved'
    e['status']=e['migration_status']
register['acceptance_refreshed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
register['full_data_preservation_accepted']=False
register['source_retirement_confirmed']=False
(ROOT/'evidence/service-register.json').write_text(json.dumps(register,indent=2)+'\n')
states=read('release-state.json')
for state in states:
    e=next(e for e in register['entries'] if e.get('chart') and e['chart'].rsplit('/',1)[-1]==state['release'])
    state.update({'status':e['migration_status'],'helmrelease_ready':e.get('native_helmrelease_ready',False),'routing_checks_passed':e.get('production_routing_accepted',False),'evidence_limits':e['functional_checks'].get('limitations',[])})
(ROOT/'evidence/release-state.json').write_text(json.dumps(states,indent=2)+'\n')
lines=['# Migration service coverage','','Baseline source metadata is retained. Current evidence and remaining limits are recorded per service in [the register](evidence/service-register.json). No source retirement is accepted.','','| Source | Chart / replacement | Namespace | Current status | Evidence |','|---|---|---|---|---|']
for e in register['entries']:
    links='; '.join('['+pathlib.Path(f).stem+']('+f+')' for f in e['functional_checks'].get('evidence',[]))
    lines.append('| '+ ' | '.join([e['source'],e.get('chart') or str(e.get('replacement','Explicit retained replacement contract')),e.get('namespace') or '—',e['status'],links or 'Retained; see replacement evidence'])+' |')
(ROOT/'SERVICE_REGISTER.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'entries':len(register['entries']),'application_releases':len(states),'ready':sum(s['helmrelease_ready'] for s in states),'full_data_preservation_accepted':False,'source_retirement_confirmed':False}))
