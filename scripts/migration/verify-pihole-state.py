#!/usr/bin/env python3
"""Observe all Pi-hole original data with bounded readonly native SQLite; never scale writers."""
import argparse
import base64
import copy
import datetime
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tomllib
import uuid
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
RUNTIME=Path('/home/brajam/.local/share/branconet-migration')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
cold=module('pihole_cold_contract',HERE/'cold-pihole-state-backup.py')
sql=module('pihole_readonly_sql',HERE/'pihole-sql-observer.py')
network=module('pihole_network_bookkeeping',HERE/'pihole-network-bookkeeping.py')
SCHEMA=HERE/'pihole-schema-contract.json'
CONTRACT=json.loads(SCHEMA.read_bytes())
shared=cold.shared


def need(ok,reason):
    if not ok:raise ValueError(reason)


def sha(path):return shared.file_hash(path)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def mac(key,domain,value):return hmac.new(key,canonical(['pihole-state-v1',domain,value]),hashlib.sha256).hexdigest()


def private(path,wanted=None):
    shared.protected(path,True)
    need(not any((p/'.git').exists() for p in [path.parent,*path.parent.parents]),'receipt_outside_git')
    if wanted is not None:need(re.fullmatch('[0-9a-f]{64}',wanted) and sha(path)==wanted,'receipt_fingerprint')
    need(path.stat().st_size<=4*1024**2,'receipt_size')


def load_receipt(path,wanted):
    private(path,wanted);return json.loads(path.read_bytes())


def call(argv,body=None,timeout=60):
    io={'stdin':subprocess.DEVNULL} if body is None else {'input':body}
    p=subprocess.run(shared.SSH+[shlex.join(argv)],capture_output=True,timeout=timeout,**io)
    need(p.returncode==0 and len(p.stdout)<=8*1024**2,'cluster_read_refused_output_withheld')
    return p.stdout


def kube(*args,ns='pihole',body=None,timeout=60):
    return call(['kubectl','--request-timeout=30s','-n',ns,*args],body,timeout)


def get(kind,name=None,ns='pihole'):
    return json.loads(kube('get',kind,*([name] if name else []),'-o','json',ns=ns))


def fence(phase,image,own=None):
    dep=get('deployment','pihole');hr=get('helmrelease','pihole','flux-system')
    need(dep['metadata']['uid']==cold.DEPLOYMENT_UID and hr['metadata']['uid']==cold.RELEASE_UID,'original_workload_identity')
    need(not dep['metadata'].get('deletionTimestamp') and not hr['metadata'].get('deletionTimestamp'),'existing_workload')
    replicas=0 if phase=='baseline' else 1
    need(dep['spec'].get('replicas',1)==replicas and dep['status'].get('observedGeneration')==dep['metadata']['generation'],'observed_writer_count')
    need(all(dep['status'].get(k,0)==replicas for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas']),'writer_readiness')
    containers=dep['spec']['template']['spec']['containers']
    need(len(containers)==1 and containers[0]['name']=='pihole' and containers[0]['image']==image,'exact_writer_image')
    need(containers[0].get('envFrom')==[{'secretRef':{'name':'pihole-runtime'}}],'original_native_secret_reference')
    secret_meta=kube('get','secret','pihole-runtime','-o','jsonpath={.metadata.uid}{"|"}{.metadata.resourceVersion}').decode().split('|')
    need(len(secret_meta)==2 and secret_meta[0]=='123afa26-222a-4a8f-85fe-a54ae6e6587c','original_native_secret_identity')
    need(hr['spec'].get('values',{}).get('replicaCount')==replicas and not hr['spec'].get('suspend',False)
         and hr['status'].get('observedGeneration')==hr['metadata']['generation']
         and any(c['type']=='Ready' and c['status']=='True' for c in hr['status'].get('conditions',[])),'flux_observed_writer_count')
    claims={}
    for alias,t in cold.CLAIMS.items():
        pvc=get('pvc',t['name']);pv=get('pv','pvc-'+t['uid'])
        need(pvc['metadata']['uid']==t['uid'] and pvc['status']['phase']=='Bound' and pvc['spec'].get('storageClassName')=='longhorn'
             and pvc['spec']['volumeName']=='pvc-'+t['uid'] and pv['metadata']['uid']==t['pv_uid'],'original_claim_pv_identity')
        need(pv['spec'].get('csi',{}).get('driver')=='driver.longhorn.io' and pv['spec']['csi'].get('volumeHandle')=='pvc-'+t['uid']
             and pv['spec'].get('claimRef',{}).get('uid')==t['uid'],'original_longhorn_binding')
        need(any(v['name']==alias and v.get('persistentVolumeClaim',{}).get('claimName')==t['name'] for v in dep['spec']['template']['spec']['volumes'])
             and any(m['name']==alias and m['mountPath']==t['app_mount'] and not m.get('subPath') for m in containers[0]['volumeMounts']),'original_mounts')
        claims[alias]={'name':t['name'],'uid':t['uid'],'pv_uid':t['pv_uid']}
    writers=[]
    for pod in get('pods')['items']:
        if own and pod['metadata']['uid']==own['uid']:continue
        if not any(v.get('persistentVolumeClaim',{}).get('claimName') in {t['name'] for t in cold.CLAIMS.values()} for v in pod['spec'].get('volumes',[])):continue
        if pod['status'].get('phase') in ['Succeeded','Failed'] and not any('running' in c.get('state',{}) for c in pod['status'].get('containerStatuses',[])):continue
        writers.append(pod)
    need(len(writers)==replicas,'no_other_claim_consumer')
    result={'deployment_uid':cold.DEPLOYMENT_UID,'helmrelease_uid':cold.RELEASE_UID,'claims':claims,
            'deployment_generation':dep['metadata']['generation'],'helmrelease_generation':hr['metadata']['generation'],'image':image,
            'native_secret_uid':secret_meta[0],'native_secret_resource_version':secret_meta[1]}
    if replicas:
        pod=writers[0];cs=pod['status'].get('containerStatuses',[])
        need(not pod['metadata'].get('deletionTimestamp') and len(cs)==1 and cs[0]['ready']
             and cs[0]['imageID'].rsplit('@',1)[-1]==image.rsplit('@',1)[-1],'ready_actual_writer')
        owners=[o for o in pod['metadata'].get('ownerReferences',[]) if o.get('controller')]
        need(len(owners)==1 and owners[0]['kind']=='ReplicaSet','writer_replicaset_owner')
        rs=get('replicaset',owners[0]['name'])
        need(rs['metadata']['uid']==owners[0]['uid'] and any(o.get('controller') and o['kind']=='Deployment' and o['uid']==cold.DEPLOYMENT_UID for o in rs['metadata'].get('ownerReferences',[])),'writer_deployment_owner')
        actual=pod['spec']['containers']
        need(len(actual)==1 and actual[0]['name']=='pihole' and actual[0]['image']==image
             and not pod['spec'].get('initContainers') and not pod['spec'].get('ephemeralContainers'),'one_owned_writer_container')
        for alias,target in cold.CLAIMS.items():
            need(any(v['name']==alias and v.get('persistentVolumeClaim',{}).get('claimName')==target['name'] for v in pod['spec']['volumes'])
                 and any(m['name']==alias and m['mountPath']==target['app_mount'] and not m.get('subPath') for m in actual[0]['volumeMounts']),'actual_writer_original_claims')
        result.update(pod_uid=pod['metadata']['uid'],pod_name=pod['metadata']['name'],node=pod['spec']['nodeName'],restart_count=cs[0].get('restartCount',0))
    return result


def clock_observation(binding,actual_pod=None):
    # Only the existing benign TZ key is decoded in operator RAM. No native
    # credential value is fetched or returned, and the SQL reader has no Secret.
    raw=kube('get','secret','pihole-runtime','-o','jsonpath={.metadata.uid}{"|"}{.metadata.resourceVersion}{"|"}{.data.TZ}').decode().split('|')
    need(len(raw)==3 and raw[:2]==[binding['native_secret_uid'],binding['native_secret_resource_version']],'same_clock_reference')
    zone=base64.b64decode(raw[2],validate=True).decode();need(len(zone)<=128 and re.fullmatch(r'[A-Za-z0-9_+./-]+',zone),'existing_zone_reference')
    configured=ZoneInfo(zone);now=datetime.datetime.now(datetime.timezone.utc)
    if actual_pod:
        text=call(['kubectl','-n','pihole','exec',actual_pod,'-c','pihole','--','date','+%Y-%m-%dT%H:%M:%S%z']).decode().strip()
        local=datetime.datetime.fromisoformat(text)
        need(local.tzinfo is not None and abs((local-now).total_seconds())<=30
             and local.utcoffset()==local.astimezone(configured).utcoffset(),'actual_writer_clock_matches_reference')
        source='actual-writer-local-clock-and-unchanged-native-TZ-reference'
    else:local=now.astimezone(configured);source='current-configured-TZ-clock-before-first-entrypoint'
    need(local.hour!=3,'nightly_gc_window_active')
    return {'local_time':local.isoformat(),'observed_utc':now.isoformat(),'basis':source,'native_secret_resource_version':raw[1],
            'zone_value_returned':False,'gc_window':'03:00:00 through 03:59:59 local (conservative)'}


def clock_interval(before,after):
    start=datetime.datetime.fromisoformat(before['local_time']);end=datetime.datetime.fromisoformat(after['local_time'])
    need(start.utcoffset()==end.utcoffset() and end>=start,'stable_forward_local_clock')
    day=start.date()
    while day<=end.date():
        window=datetime.datetime.combine(day,datetime.time(3),tzinfo=start.tzinfo)
        need(not(start<window+datetime.timedelta(hours=1) and end>=window),'nightly_gc_window_opened_during_observation')
        day+=datetime.timedelta(days=1)


def metadata_program():
    return r"""set -eu
for f in gravity.db pihole-FTL.db pihole-FTL.db-wal pihole-FTL.db-shm; do
 p=/source/pihole/$f
 if [ -e "$p" ]; then test ! -L "$p"; stat -c '%n|%d|%i|%s|%a|%u|%g' "$p"; else printf '%s|absent\n' "$p"; fi
done
"""


def file_metadata(exec_read):
    rows={}
    for line in exec_read(['sh','-c',metadata_program()]).decode().splitlines():
        fields=line.split('|');name=Path(fields[0]).name
        need(name in ['gravity.db','pihole-FTL.db','pihole-FTL.db-wal','pihole-FTL.db-shm'],'fixed_database_file')
        rows[name]=None if fields[1:] == ['absent'] else [int(v) for v in fields[1:]]
    need(set(rows)=={'gravity.db','pihole-FTL.db','pihole-FTL.db-wal','pihole-FTL.db-shm'}
         and rows['gravity.db'] and rows['pihole-FTL.db'],'database_files_present')
    need(sum(v[2] for v in rows.values() if v)<=4*1024**3,'database_size_bound')
    need(bool(rows['pihole-FTL.db-wal'])==bool(rows['pihole-FTL.db-shm']),'complete_wal_pair')
    return rows


def projected_config(raw,key,phase):
    need(len(raw)<=8*1024**2,'config_size')
    values=tomllib.loads(raw.decode('utf-8-sig'));flat={}
    def walk(value,path):
        if isinstance(value,dict):
            for k,v in value.items():walk(v,path+[k])
        else:flat['.'.join(path)]=value
    walk(values,[])
    need(flat.get('webserver.api.pwhash') and isinstance(flat['webserver.api.pwhash'],str),'preserved_password_hash_present')
    need(flat.get('database.maxDBdays')==91,'existing_91_day_retention_policy_unchanged')
    changes={}
    if phase=='baseline':
        need(flat.get('files.pid')=='/run/pihole-FTL.pid','retired_pid_must_be_original_default')
        flat.pop('files.pid');changes['retired_default_pid_removed_from_projection']=True
        for name,value in [('resolver.macNames',True),('debug.performance',False)]:
            need(name not in flat,'new_config_key_must_not_preexist');flat[name]=value
    else:need('files.pid' not in flat,'retired_pid_removed_by_vendor')
    entries={mac(key,'config-key',name):mac(key,['config-value',name],value) for name,value in flat.items()}
    return {'entries':entries,'count':len(entries),'projection_changes':changes,'retention_days':flat.get('database.maxDBdays'),
            'old_values_including_password_hash_preserved':phase!='baseline'}


def protect_digests(snapshot,key,db):
    def walk(value):
        if isinstance(value,list):return [walk(v) for v in value]
        if isinstance(value,dict):
            return {k:(mac(key,['sqlite-native-digest',db],v) if k.endswith('digest') and isinstance(v,str) else walk(v)) for k,v in value.items()}
        return value
    return walk(snapshot)


def compare(old,new,bookkeeping=None,label='baseline'):
    changes={}
    for db in old:
        a,b=old[db],new[db]
        need(a['tables'].keys()==b['tables'].keys(),'same_original_tables')
        mutable={'counters','network','network_addresses','sqlite_sequence'} if db=='pihole-FTL.db' else set()
        for name,row in a['tables'].items():
            current=b['tables'][name]
            need(current['original_count']==row['original_count'] if name not in mutable else True,'original_row_count')
            if name not in mutable:need(current['digest']==row['digest'],'original_typed_rows_'+name)
            if name in sql.APPEND and db=='pihole-FTL.db':need(current['count']>=row['count'],'append_only_row_count')
        if db=='gravity.db':
            need(b['removed_stat_rows']==0,'source_rebuilt_table_stats_removed')
            changes['gravity_statistics_rows_removed']=a['removed_stat_rows']
            continue
        def indexed(rows,field):return {r[field]:r for r in rows}
        for field in ['counter_rows','sequence_rows','network_rows','address_rows']:
            identity={'counter_rows':'id','sequence_rows':'name','network_rows':'id','address_rows':'key_digest'}[field]
            aa,bb=indexed(a[field],identity),indexed(b[field],identity)
            replacements={int(k):v for k,v in bookkeeping['networkReplacements'].items()} if bookkeeping and field=='network_rows' else bookkeeping['addressReplacements'][label] if bookkeeping and field=='address_rows' else {}
            need(aa.keys()<=bb.keys()|replacements.keys() and all(k in bb for k in replacements.values()),'original_runtime_identities_'+field)
            altered=0
            for identifier,before in aa.items():
                replaced=identifier not in bb and identifier in replacements
                after=bb[replacements[identifier] if replaced else identifier]
                if field=='counter_rows':need(after['value']>=before['value'],'monotonic_counters')
                elif field=='sequence_rows':need(after['seq']>=before['seq'],'monotonic_sequences')
                elif field=='network_rows':
                    need(replaced or after['stable_digest']==before['stable_digest'],'original_network_identity')
                    need(all(after[k]>=before[k] for k in ['lastQuery','numQueries']),'monotonic_network_counters')
                else:
                    need(after['lastSeen']>=before['lastSeen'],'monotonic_address_lastSeen')
                    need(before['nameUpdated'] is None or after['nameUpdated'] is not None and after['nameUpdated']>=before['nameUpdated'],'monotonic_resolver_update_time')
                altered+=before!=after
            changes[field]={'old_rows':len(aa),'new_rows':len(bb)-len(aa),'source_runtime_rows_changed':altered}
        need(b['last_timestamp']>=a['last_timestamp'],'monotonic_last_query_timestamp')
        changes['old_query_rows_preserved']=a['tables']['query_storage']['original_count']
        changes['new_query_rows']=b['tables']['query_storage']['count']-a['tables']['query_storage']['original_count']
    return changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['baseline','window','verify'])
    parser.add_argument('--cold-receipt',type=Path,required=True);parser.add_argument('--cold-receipt-sha256',required=True)
    parser.add_argument('--baseline-receipt',type=Path);parser.add_argument('--baseline-receipt-sha256',default='')
    parser.add_argument('--previous-live-receipt',type=Path);parser.add_argument('--previous-live-receipt-sha256',default='')
    parser.add_argument('--candidate-image',default='');parser.add_argument('--node',choices=['workernode1','workernode2'],default='workernode2')
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();need(args.apply and os.name=='posix','explicit_native_observation');os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
    need(bool(args.baseline_receipt)==bool(args.baseline_receipt_sha256) and bool(args.previous_live_receipt)==bool(args.previous_live_receipt_sha256),'paired_receipts')
    need(not args.previous_live_receipt or args.phase=='verify','restart_proof_only_for_live_verification')
    need(args.phase in ['verify','window'] if args.baseline_receipt else args.phase=='baseline','baseline_phase_contract')
    backup=load_receipt(args.cold_receipt,args.cold_receipt_sha256)
    need(backup.get('status')=='completed' and backup.get('application')=='pihole' and backup.get('cold_archive_verified') is True and backup.get('temporary_pod_deleted') is True,'completed_cold_archive')
    need(backup['deployment_uid']==cold.DEPLOYMENT_UID and backup['helmrelease_uid']==cold.RELEASE_UID and backup['original_image']==cold.ORIGINAL_IMAGE,'original_cold_binding')
    archive=Path(backup['archive_path']);shared.protected(archive,True)
    need(archive.stat().st_size==backup['archive_bytes'] and sha(archive)==backup['archive_sha256'],'retained_original_ciphertext')
    pins=[(p,shared.protected(p,p==shared.IDENTITY)) for p in [shared.AGE,shared.RECIPIENT,shared.IDENTITY]]
    need(sha(shared.AGE)==shared.AGE_SHA256,'pinned_age')
    image=cold.ORIGINAL_IMAGE if args.phase=='baseline' or args.phase=='window' and not args.candidate_image else args.candidate_image
    need(image==cold.ORIGINAL_IMAGE or re.fullmatch(r'docker.io/library/pihole[a-z0-9._-]{0,64}@sha256:[0-9a-f]{64}',image),'qualified_immutable_image_required')
    output=args.output_dir;need(output.is_absolute() and output.resolve()==output and RUNTIME in output.parents,'native_output')
    need(not any((p/'.git').exists() for p in [output,*output.parents]),'output_outside_git')
    output.mkdir(mode=0o700,parents=True,exist_ok=True);need(output.stat().st_uid==os.getuid() and not output.stat().st_mode&0o077,'private_output')
    run=output/('pihole-data-'+args.phase+'-'+uuid.uuid4().hex);run.mkdir(mode=0o700)
    receipt={'schema_version':1,'application':'pihole','phase':args.phase,'status':'started','started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'cold_receipt_sha256':args.cold_receipt_sha256,'archive_sha256':backup['archive_sha256'],'writer_scaled_or_restarted':False,
             'full_database_byte_equivalence_claimed':False,'api_dns_or_browser_accepted':False,'temporary_pod_deleted':False,'full_goal_complete':False,
             'source_sha256':{p.name:sha(p) for p in [Path(__file__),HERE/'pihole-sql-observer.py',HERE/'pihole-network-bookkeeping.py',SCHEMA,HERE/'cold-pihole-state-backup.py']}}
    def save():
        temp=run/('receipt-'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');os.replace(temp,run/'receipt.json')
    own=None;save()
    try:
        baseline=None;previous=None
        if args.phase=='window':
            baseline=load_receipt(args.baseline_receipt,args.baseline_receipt_sha256)
            need(baseline['status']=='completed' and baseline['phase']=='baseline' and baseline['cold_receipt_sha256']==args.cold_receipt_sha256,'completed_baseline_before_entrypoint')
            before=fence('baseline',image)
            local=clock_observation(before)
            receipt.update(writer=before,clock_before_first_candidate=local,baseline_receipt_sha256=args.baseline_receipt_sha256,
                           status='completed',temporary_pod_created=False,temporary_pod_deleted=False,
                           completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            save();print(json.dumps({'status':'completed','receipt':str(run/'receipt.json'),'receipt_sha256':sha(run/'receipt.json')}));return 0
        if args.phase=='baseline':key=os.urandom(32)
        else:
            baseline=load_receipt(args.baseline_receipt,args.baseline_receipt_sha256)
            need(baseline['status']=='completed' and baseline['phase']=='baseline' and baseline['cold_receipt_sha256']==args.cold_receipt_sha256,'exact_completed_baseline')
            encrypted=Path(baseline['key_ciphertext']);private(encrypted,baseline['key_ciphertext_sha256'])
            result=subprocess.run([str(shared.AGE),'-d','-i',str(shared.IDENTITY),str(encrypted)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
            need(result.returncode==0 and len(result.stdout)<=4096,'verification_key_authentication')
            packet=json.loads(result.stdout);key=base64.b64decode(packet['key'],validate=True)
            need(len(key)==32 and packet['cold_receipt_sha256']==args.cold_receipt_sha256,'verification_key_binding')
        before=fence(args.phase,image);receipt['writer']=before
        if args.phase=='verify':receipt['clock_start']=clock_observation(before,before['pod_name'])
        if args.previous_live_receipt:
            previous=load_receipt(args.previous_live_receipt,args.previous_live_receipt_sha256)
            need(args.phase=='verify' and previous['status']=='completed' and previous['cold_receipt_sha256']==args.cold_receipt_sha256
                 and previous['baseline_receipt_sha256']==args.baseline_receipt_sha256
                 and previous['writer']['image']==image and previous['writer']['pod_uid']!=before['pod_uid'],'separate_restart_identity')
            receipt.update(previous_live_receipt_sha256=args.previous_live_receipt_sha256,different_writer_pod_verified=True)
        node=args.node if args.phase=='baseline' else before['node']
        n=get('node',node);need(n['status'].get('features',{}).get('supplementalGroupsPolicy') is True and not n['spec'].get('unschedulable',False)
             and any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']),'ready_strict_reader_node')
        need(not any(c['type'] in ['DiskPressure','MemoryPressure','PIDPressure','NetworkUnavailable'] and c['status']=='True' for c in n['status']['conditions']),'reader_node_no_pressure')
        # First a tiny public stat command in the original writer (live) or via
        # an RO-mounted reader. A baseline reader first uses complete RO roots;
        # SQLite file subPath binds below are fixed after that metadata proof.
        name='pihole-sql-'+uuid.uuid4().hex[:12]
        volumes=[{'name':a,'persistentVolumeClaim':{'claimName':t['name'],'readOnly':True}} for a,t in cold.CLAIMS.items()]
        volumes.append({'name':'sql-tmp','emptyDir':{'medium':'Memory','sizeLimit':'64Mi'}})
        mounts=[{'name':a,'mountPath':t['reader_mount'],'readOnly':True} for a,t in cold.CLAIMS.items()]
        mounts.append({'name':'sql-tmp','mountPath':'/sql'})
        for db in ['gravity.db','pihole-FTL.db']:
            mounts.append({'name':'data-1','mountPath':'/sql/'+db,'subPath':db,'readOnly':True})
        # Existing live WAL files must be bound too; a missing pair in a live
        # writer refuses rather than ignoring WAL or copying the huge database.
        if args.phase=='verify':
            probe=call(['kubectl','-n','pihole','exec',before['pod_name'],'-c','pihole','--','sh','-c',metadata_program().replace('/source/pihole/','/etc/pihole/')])
            lines=probe.decode().splitlines();need(all(not line.endswith('|absent') for line in lines if '-wal|' in line or '-shm|' in line),'live_wal_pair_required')
            for suffix in ['-wal','-shm']:mounts.append({'name':'data-1','mountPath':'/sql/pihole-FTL.db'+suffix,'subPath':'pihole-FTL.db'+suffix,'readOnly':True})
        command="""set -eu
ulimit -c 0
test "$(id -u)" = 1000
test "$(id -g)" = 0
test "$(id -G)" = 0
awk '/^(CapEff|CapPrm|CapAmb|CapBnd):/ {if ($2 != "0000000000000000") exit 1; n++} /^NoNewPrivs:/ {if ($2 != "1") exit 1; n++} END {if(n != 5) exit 1}' /proc/self/status
test "$(stat -c %s /usr/bin/pihole-FTL)" = 27867849
test "$(sha256sum /usr/bin/pihole-FTL | cut -d ' ' -f 1)" = 771bc4e23aec29eb95969272fbc13ca26a18a13285b9c4cd0078bfcc6f828c22
cp /usr/bin/pihole-FTL /sql/pihole-sql
test "$(sha256sum /sql/pihole-sql | cut -d ' ' -f 1)" = 771bc4e23aec29eb95969272fbc13ca26a18a13285b9c4cd0078bfcc6f828c22
test -z "$(getcap /sql/pihole-sql)"
test "$(/sql/pihole-sql --version)" = v6.5
exec sleep 1800
"""
        pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'pihole','labels':{'migration-task':'pihole-sql-read'}},
             'spec':{'nodeName':node,'restartPolicy':'Never','activeDeadlineSeconds':1800,'automountServiceAccountToken':False,'enableServiceLinks':False,
                     'securityContext':{'runAsUser':1000,'runAsGroup':0,'runAsNonRoot':True,'supplementalGroupsPolicy':'Strict','seccompProfile':{'type':'RuntimeDefault'}},
                     'containers':[{'name':'reader','image':cold.ORIGINAL_IMAGE,'imagePullPolicy':'IfNotPresent','command':['sh','-c',command],
                                    'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
                                    'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'volumeMounts':mounts}],
                     'volumes':volumes}}
        created=json.loads(kube('create','-f','-','-o','json',body=canonical(pod)));own={'name':name,'uid':created['metadata']['uid']};receipt['reader']=own;save()
        kube('wait','pod/'+name,'--for=condition=Ready','--timeout=180s',timeout=200)
        def execute(argv,body=None,timeout=60):
            current=get('pod',name);need(current['metadata']['uid']==own['uid'] and current['status']['containerStatuses'][0]['ready'],'same_ready_owned_reader')
            need(current['status']['containerStatuses'][0]['imageID'].rsplit('@',1)[-1]==cold.ORIGINAL_IMAGE.rsplit('@',1)[-1],'actual_old_sql_binary')
            spec=current['spec'];container=spec['containers'][0]
            need(len(spec['containers'])==1 and not spec.get('initContainers') and not spec.get('ephemeralContainers')
                 and spec.get('automountServiceAccountToken') is False and not container.get('env') and not container.get('envFrom')
                 and spec['nodeName']==node and not spec.get('hostNetwork',False) and not spec.get('hostPID',False) and not spec.get('hostIPC',False)
                 and spec['securityContext']==pod['spec']['securityContext'] and spec['volumes']==volumes
                 and container['securityContext']==pod['spec']['containers'][0]['securityContext']
                 and container['volumeMounts']==mounts and container['resources']==pod['spec']['containers'][0]['resources']
                 and container['command']==['sh','-c',command],'exact_bounded_readonly_reader')
            need(fence(args.phase,image,own)==before,'writer_fence_during_read')
            return call(['kubectl','--request-timeout=930s','-n','pihole','exec','-i',name,'-c','reader','--',*argv],body,timeout)
        source_files=file_metadata(execute);receipt['database_file_metadata']=source_files
        if args.phase=='baseline':need(not source_files['pihole-FTL.db-wal'] and not source_files['pihole-FTL.db-shm'],'cold_closed_database_without_sidecars')
        def mounted_inodes():
            bound={}
            raw=execute(['sh','-c',metadata_program().replace('/source/pihole/','/sql/')])
            for line in raw.decode().splitlines():
                fields=line.split('|');filename=Path(fields[0]).name
                if fields[1:]!=['absent']:bound[filename]=[int(v) for v in fields[1:]]
            for filename,value in source_files.items():
                if value:need(filename in bound and bound[filename][:2]==value[:2],'same_bound_database_inode')
        mounted_inodes()
        snapshots={}
        for db,contract in CONTRACT['databases'].items():
            query=sql.build(db,contract['old'],baseline['snapshots'][db] if baseline else None,previous['snapshots'][db] if previous else None)
            raw=execute(['timeout','-s','KILL','900','/sql/pihole-sql','sqlite3','-readonly','-bail','-batch','-json','-init','/dev/null','/sql/'+db],query.encode(),timeout=930)
            observation=sql.decode(raw)
            expected=contract['old' if args.phase=='baseline' else 'new']
            need(observation['schema']==expected['schema'] and observation['table_xinfo']==expected['table_xinfo'],'exact_source_schema_'+db)
            need(observation['version']==contract['old_version' if args.phase=='baseline' else 'new_version'],'source_schema_version_'+db)
            snapshots[db]=protect_digests(observation,key,db)
            for table,row in snapshots[db]['tables'].items():
                if db=='pihole-FTL.db' and table in sql.APPEND:
                    if args.phase=='baseline':row['checkpoint_digest']=row['digest']
                    if previous:
                        prior=previous['snapshots'][db]['tables'][table]
                        need(row['previous_checkpoint_digest']==prior['checkpoint_digest'] and row['previous_checkpoint_count']==prior['count'],'initial_live_checkpoint_preserved_'+table)
        raw=execute(['cat','/source/pihole/pihole.toml']);config=projected_config(raw,key,args.phase);del raw
        receipt.update(snapshots=snapshots,configuration=config)
        if args.phase=='baseline':
            days=config.get('retention_days');oldest=snapshots['pihole-FTL.db']['oldest_query_timestamp']
            receipt['retention_review']={'configured_days':days,'oldest_query_timestamp':oldest,
                'older_than_configured_positive_retention':bool(isinstance(days,int) and days>0 and oldest is not None
                    and oldest<datetime.datetime.now(datetime.timezone.utc).timestamp()-days*86400),
                'zero_retention_requires_source_review':days==0,'no_history_deletion_waived':True}
        # Original stable settings/TLS/backup files are independently hashed;
        # whole original trees remain preserved in the authenticated archive.
        static=['/source/pihole/custom.list','/source/pihole/local.list','/source/pihole/adlists.list','/source/pihole/dns-servers.conf','/source/pihole/dhcp.leases','/source/pihole/gravity_old.db','/source/pihole/tls.pem','/source/pihole/tls.crt','/source/pihole/tls_ca.crt']
        listing=execute(['find','/source/dnsmasq','-xdev','-type','f','-print0']).split(b'\0')
        static += [x.decode() for x in listing if x]
        need(len(static)<=4096,'static_file_count')
        hashes={}
        for path in static:
            need('\n' not in path and path.startswith(('/source/pihole/','/source/dnsmasq/')),'fixed_static_path')
            value=execute(['sha256sum',path]).decode();need(re.fullmatch('[0-9a-f]{64}',value[:64]),'static_hash')
            hashes[mac(key,'file-path',path)]=mac(key,['file-bytes',path],value[:64])
        receipt['static_files_hmac']=hashes
        after_files=file_metadata(execute)
        need(all(after_files[n] and source_files[n][:2]==after_files[n][:2] for n in source_files if source_files[n]),'database_inodes_retained')
        mounted_inodes()
        if baseline:
            need(config['entries']==baseline['configuration']['entries'],'original_config_and_password_identity')
            need(hashes==baseline['static_files_hmac'],'original_static_settings_tls_backup_files')
            bookkeeping=None
            if {r['id'] for r in baseline['snapshots']['pihole-FTL.db']['network_rows']} - {r['id'] for r in snapshots['pihole-FTL.db']['network_rows']}:
                import sys
                bookkeeping=network.prove_replacement(sys.modules[__name__],backup,baseline,previous,snapshots,execute,key)
                receipt['source_verified_network_bookkeeping']=bookkeeping
            receipt['runtime_changes']=compare(baseline['snapshots'],snapshots,bookkeeping)
            if previous:receipt['restart_runtime_changes']=compare(previous['snapshots'],snapshots,bookkeeping,'previous')
            receipt.update(baseline_receipt_sha256=args.baseline_receipt_sha256,original_rows_and_configuration_preserved=True)
        else:
            cipher=run/'verification-key.json.age'
            packet=canonical({'key':base64.b64encode(key).decode(),'cold_receipt_sha256':args.cold_receipt_sha256})
            with cipher.open('xb') as target:
                p=subprocess.run([str(shared.AGE),'-R',str(shared.RECIPIENT)],input=packet,stdout=target,stderr=subprocess.DEVNULL,timeout=30)
                need(p.returncode==0,'verification_key_encryption');target.flush();os.fsync(target.fileno())
            recovered=subprocess.run([str(shared.AGE),'-d','-i',str(shared.IDENTITY),str(cipher)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
            need(recovered.returncode==0 and recovered.stdout==packet,'verification_key_authenticated_roundtrip')
            receipt.update(key_ciphertext=str(cipher),key_ciphertext_sha256=sha(cipher),verification_key_authenticated=True)
        need(fence(args.phase,image,own)==before,'writer_fence_after_read')
        if args.phase=='verify':
            receipt['clock_end']=clock_observation(before,before['pod_name']);clock_interval(receipt['clock_start'],receipt['clock_end'])
        private(args.cold_receipt,args.cold_receipt_sha256)
        for p,identity in pins:need(shared.protected(p,p==shared.IDENTITY)==identity,'crypto_identity_retained')
        for filename,digest in receipt['source_sha256'].items():need(sha(HERE/filename)==digest,'observer_source_retained')
        options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':own['uid']},'propagationPolicy':'Foreground'}
        kube('delete','--raw','/api/v1/namespaces/pihole/pods/'+name,'-f','-',body=canonical(options))
        kube('wait','pod/'+name,'--for=delete','--timeout=120s',timeout=140)
        receipt.update(status='completed',temporary_pod_deleted=True)
    except Exception as exc:
        receipt.update(status='failed',failure=str(exc) if isinstance(exc,ValueError) and re.fullmatch('[a-zA-Z0-9_.-]+',str(exc)) else type(exc).__name__)
    receipt['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print(json.dumps({'status':receipt['status'],'receipt':str(run/'receipt.json'),'receipt_sha256':sha(run/'receipt.json')}))
    return 0 if receipt['status']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
