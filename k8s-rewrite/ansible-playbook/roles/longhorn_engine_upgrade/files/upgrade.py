"""Serial healthy V1 engine upgrades; retain claims, data directories and backups.

The supported v1.12.x to v1.13 live path uses spec.image only. UID/resourceVersion
tests prevent racing another writer. A submitted incomplete volume is inspected,
never automatically patched again or downgraded. Unused WordPress is excluded.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import time

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
E = O / 'longhorn-engine-upgrade-20261028'
IMAGE = 'docker.io/longhornio/longhorn-engine:v1.13.0@sha256:b0cc5090889d57705acd69c5106492992e84560170ac3bec4a1cc8dd3fe83ca6'
OLD = 'docker.io/longhornio/longhorn-engine:v1.12.1'
UNUSED = 'pvc-49df631b-614f-4180-b6e5-f719db4bfe2c'
AUTH = None
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
    '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
    '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']

# No exec/injection into the distroless container and no new Pod, mount, file or
# helper process inside its namespace. Only the original /data directory is read.
DISTROLESS_READ = r'''
import hashlib,json,os,pathlib,subprocess,re
r=json.load(__import__('sys').stdin)
assert os.geteuid()==0 and set(r)=={'containerID','podUID','volume','imageID'}
assert re.fullmatch('[0-9a-f]{64}',r['containerID']) and re.fullmatch('[0-9a-f-]{36}',r['podUID'])
assert r['volume']=='pvc-9edde4e3-5a0c-4c0c-b317-47b045ee199e'
assert r['imageID']=='docker.io/hashicorp/http-echo@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186'
ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
assert hashlib.sha256(ctr.read_bytes()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
base=[str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
def cmd(a):
 p=subprocess.run(base+a,capture_output=True,timeout=15);assert p.returncode==0 and len(p.stdout)<=1048576;return p.stdout
info=json.loads(cmd(['containers','info',r['containerID']]))
labels=info.get('Labels',info.get('labels',{}))
assert labels['io.kubernetes.pod.uid']==r['podUID'] and labels['io.kubernetes.pod.namespace']=='http-echo' and labels['io.kubernetes.container.name']=='http-echo'
rows=[s.split() for s in cmd(['tasks','list']).decode().splitlines()]
row=[x for x in rows if x[0]==r['containerID']];assert len(row)==1 and row[0][2]=='RUNNING'
pid=int(row[0][1]);proc=pathlib.Path('/proc')/str(pid)
start=(proc/'stat').read_text().rsplit(')',1)[1].split()[19]
mounts=[x.split(' - ',1) for x in (proc/'mountinfo').read_text().splitlines()]
mount=[(a.split(),b.split()) for a,b in mounts if a.split()[4]=='/data']
assert len(mount)==1 and mount[0][1][0]=='ext4' and mount[0][1][1] in ['/dev/mapper/'+r['volume'],'/dev/longhorn/'+r['volume']]
fd=os.open(str(proc/'root/data'),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 before=os.fstat(fd);count=0
 with os.scandir(fd) as entries:
  for entry in entries:
   count+=1;assert count<=10000
 after=os.fstat(fd);assert(before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
finally:os.close(fd)
assert (proc/'stat').read_text().rsplit(')',1)[1].split()[19]==start
assert json.loads(cmd(['containers','info',r['containerID']]))==info
print(json.dumps({'status':'existing_distroless_mount_read_passed','containerID':r['containerID'],'podUID':r['podUID'],'volume':r['volume'],'directoryEntriesRead':count,'mountSourceVerified':True,'processStartPreserved':True,'filesWritten':False,'newPodOrMountCreated':False}))
'''


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, value):
    with (E / name).open('x') as out:
        json.dump(value, out, indent=2)


def call(args, data=None, timeout=60):
    p = subprocess.run(SSH + [shlex.join(['kubectl', *args])],
        input=None if data is None else json.dumps(data).encode(), capture_output=True, timeout=timeout)
    need(len(p.stdout) <= 16 * 1024**2 and len(p.stderr) <= 1024**2, 'bounded_native_operation')
    return p


def get(kind, name=None, namespace='longhorn-system'):
    args = ['get', kind, *(['-n', namespace] if namespace else ['-A']), *([name] if name else []), '-o', 'json']
    p = call(args)
    need(p.returncode == 0, 'native_nonsecret_read_failed')
    v = json.loads(p.stdout)
    return v if name else v['items']


def associated(kind, name):
    return [v for v in get(kind + '.longhorn.io') if v['spec'].get('volumeName') == name]


def data_directories(replicas):
    return sorted((r['spec'].get('nodeID'), r['spec'].get('diskID'), r['spec'].get('dataDirectoryName'),
        r['spec'].get('diskPath')) for r in replicas)


def healthy(v, engines, replicas):
    return v['status'].get('state') == 'attached' and v['status'].get('robustness') == 'healthy' \
        and len(engines) == 1 and engines[0]['status'].get('currentState') == 'running' \
        and len(engines[0]['status'].get('replicaModeMap') or {}) == 2 \
        and list((engines[0]['status'].get('replicaModeMap') or {}).values()).count('RW') == 2 \
        and len(replicas) == 2 and all(r['status'].get('currentState') == 'running' and not r['spec'].get('failedAt') for r in replicas) \
        and len({r['spec']['nodeID'] for r in replicas}) == 2


def controls():
    settings = {s['metadata']['name']: s.get('value') for s in get('settings.longhorn.io')}
    need(settings['current-longhorn-version'] == 'v1.13.0' and settings['default-engine-image'] == IMAGE
        and settings['concurrent-automatic-engine-upgrade-per-node-limit'] == '0'
        and settings['storage-minimal-available-percentage'] == '25', 'qualified_manager_and_original_manual_storage_controls')
    nodes = get('nodes', namespace=None)
    need(len(nodes) == 3 and all(any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions'])
        and not any(c['type'].endswith('Pressure') and c['status'] == 'True' for c in n['status']['conditions']) for n in nodes), 'three_ready_nodes_without_pressure')
    for n in get('nodes.longhorn.io'):
        for d in n['status'].get('diskStatus', {}).values():
            need(d['storageAvailable'] >= d['storageMaximum'] // 4 + 1 + 512 * 1024**2,
                'unchanged_longhorn_floor_and_operating_margin_after_host_payload_installed')
    images = [i for i in get('engineimages.longhorn.io') if i['spec']['image'] == IMAGE]
    need(len(images) == 1 and images[0]['status']['state'] == 'deployed'
        and set(images[0]['status']['nodeDeploymentMap']) == {n['metadata']['name'] for n in nodes}
        and all(images[0]['status']['nodeDeploymentMap'].values()), 'new_engine_installed_and_ready_on_every_node')


def pod_mounts(v):
    claims = get('pvc', namespace=None)
    pvs = get('pv', namespace=None)
    pv_names = {p['metadata']['name'] for p in pvs if p['spec'].get('csi', {}).get('driver') == 'driver.longhorn.io'
        and p['spec']['csi'].get('volumeHandle') == v['metadata']['name']}
    pairs = {(c['metadata']['namespace'], c['metadata']['name']) for c in claims if c['spec'].get('volumeName') in pv_names}
    mounts = []
    for pod in get('pods', namespace=None):
        if pod['status'].get('phase') != 'Running' or pod['metadata'].get('deletionTimestamp'):
            continue
        ns = pod['metadata']['namespace']
        names = {p['name'] for p in pod['spec'].get('volumes', []) if (ns, p.get('persistentVolumeClaim', {}).get('claimName')) in pairs}
        if not names:
            continue
        statuses = {c['name']: c for c in pod['status'].get('containerStatuses', [])}
        for c in pod['spec']['containers']:
            if c['name'] not in statuses or not statuses[c['name']].get('ready'):
                continue
            for m in c.get('volumeMounts', []):
                if m['name'] in names:
                    mounts.append({'namespace': ns, 'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'],
                        'container': c['name'], 'path': m['mountPath'], 'imageID': statuses[c['name']]['imageID'],
                        'restartCount': statuses[c['name']]['restartCount']})
    return sorted(mounts, key=lambda m: (m['namespace'], m['pod'], m['container'], m['path']))


def probe(mounts):
    global AUTH
    command = 'if [ -d "$1" ]; then ls -A "$1" >/dev/null; else test -r "$1" && head -c 1 "$1" >/dev/null; fi'
    for m in mounts:
        if m['imageID'] == 'docker.io/hashicorp/http-echo@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186':
            need(m['namespace'] == m['container'] == 'http-echo' and m['path'] == '/data', 'finite_known_distroless_mount')
            pod = get('pods', m['pod'], m['namespace'])
            c = next(c for c in pod['status']['containerStatuses'] if c['name'] == m['container'])
            need(pod['metadata']['uid'] == m['podUID'] and c['imageID'] == m['imageID']
                and c['ready'] and c['restartCount'] == m['restartCount'], 'same_original_distroless_container')
            if AUTH is None:
                source = Path(__file__).resolve().parents[3] / 'roles/legacy_plex_preservation/files/controller.py'
                library = runpy.run_path(str(source), run_name='existing_protected_tty_input')
                AUTH = library['privilege_input']()
            node = {'masternode': '192.168.0.4', 'workernode2': '192.168.0.5', 'workernode1': '192.168.0.6'}[pod['spec']['nodeName']]
            request = {'containerID': c['containerID'].removeprefix('containerd://'), 'podUID': m['podUID'],
                'volume': 'pvc-9edde4e3-5a0c-4c0c-b317-47b045ee199e', 'imageID': m['imageID']}
            p = subprocess.run(SSH[:-1] + ['james@' + node, shlex.join(['sudo', '-S', '-k', '-p', '',
                '/usr/bin/python3', '-B', '-c', DISTROLESS_READ])], input=AUTH + b'\n' + json.dumps(request).encode(),
                capture_output=True, timeout=45)
            need(p.returncode == 0 and len(p.stdout) <= 65536, 'verified_existing_distroless_mount_read_required')
            value = json.loads(p.stdout)
            need(value['status'] == 'existing_distroless_mount_read_passed' and value['mountSourceVerified']
                and value['processStartPreserved'] and not value['filesWritten'], 'distroless_read_accepted')
            save('distroless-read-' + str(time.time_ns()) + '.json', value)
            continue
        p = call(['-n', m['namespace'], 'exec', m['pod'], '-c', m['container'], '--', '/bin/sh', '-c', command, '--', m['path']], timeout=30)
        need(p.returncode == 0, 'existing_application_mount_read_probe_failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'prepare-distroless-probe', 'reconcile-rejected-patch', 'apply', 'observe'])
    parser.add_argument('--limit', type=int, default=43)
    a = parser.parse_args()
    need(os.geteuid() == 1000 and F.is_mount() and 1 <= a.limit <= 43, 'existing_controller_owner_and_bounded_scope')
    for p in (F, Path('/mnt/c')):
        st = os.statvfs(p)
        need(st.f_bavail * st.f_frsize >= 15 * 1024**3 + 64 * 1024**2, 'complete_metadata_peak_and_original_floors')
    repo = Path(__file__).resolve().parents[5]
    manager = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_manager_upgrade/files/upgrade.py'), run_name='qualified_manager_recovery')
    controls()
    if a.mode == 'prepare':
        need(not E.exists(), 'preserve_prior_engine_operation')
        accepted = json.loads((O / 'longhorn-manager-upgrade-20261028/manager-acceptance.json').read_text())
        need(accepted['status'] == 'manager_rollout_completed' and accepted['twoActualRWOnEveryAttachedVolume'], 'manager_accepted_first')
        recovery = manager['recovery']()
        volumes = get('volumes.longhorn.io')
        need(len(volumes) == 44 and {v['metadata']['name'] for v in volumes} ==
            {v['name'] for v in json.loads((O / 'longhorn-manager-upgrade-20261028/after.json').read_text())['volumes']}, 'original_exact_volume_scope')
        backups = get('backups.longhorn.io')
        records = []
        for v in volumes:
            if v['metadata']['name'] == UNUSED:
                continue
            name = v['metadata']['name']
            need(v['spec']['image'] == OLD and v['spec']['dataEngine'] == 'v1' and v['spec']['encrypted']
                and v['spec']['numberOfReplicas'] == 2 and v['spec']['frontend'] == 'blockdev', 'supported_original_encrypted_two_replica_v1_block_device')
            need(any(b.get('status', {}).get('volumeName') == name and b['status'].get('state') == 'Completed'
                and not b['status'].get('error') for b in backups), 'completed_native_data_backup')
            replicas, engines = associated('replicas', name), associated('engines', name)
            state = v['status']['state']
            need(state in ('attached', 'detached') and len(replicas) == 2 and len({r['spec']['nodeID'] for r in replicas}) == 2
                and all(not r['spec'].get('failedAt') for r in replicas), 'original_two_replica_data_directories')
            if state == 'attached':
                need(healthy(v, engines, replicas), 'healthy_live_upgrade_only')
                mounts = pod_mounts(v)
                need(bool(mounts), 'active_application_mount_known_before_live_upgrade')
            else:
                mounts = []
            records.append({'name': name, 'uid': v['metadata']['uid'], 'spec': v['spec'], 'state': state,
                'dataDirectories': data_directories(replicas), 'mounts': mounts, 'size': int(v['spec']['size'])})
        need(len(records) == 43, 'all_and_only_initialized_volumes')
        records.sort(key=lambda v: (v['state'] != 'attached', v['size'], v['name']))
        os.umask(0o077)
        E.mkdir(mode=0o700)
        save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(E)],
            'completePeakBytes': 64 * 1024**2, 'regeneration': 'Same reviewed source and retained exact before/intent/result metadata; never reapply an incomplete intent',
            'protected': 'All original claim/volume identities, two replica data directories, native keys, NAS and all original failures/backups',
            'endCondition': 'All 43 initialized volumes observed on the new image with state/data directories and live mount checks preserved',
            'excludedVolume': UNUSED, 'automaticEngineUpgradeLimit': 0})
        save('plan.json', {'sourceSHA256': sha(Path(__file__)), 'managerSourceSHA256': sha(Path(manager['__file__'])),
            'targetImage': IMAGE, 'records': records, 'recovery': recovery,
            'supportedProcedure': 'https://longhorn.io/docs/1.13.0/deploy/upgrade/upgrade-engine/'})
        print(json.dumps({'status': 'prepared', 'volumes': len(records), 'attached': sum(v['state'] == 'attached' for v in records)}))
        return
    if a.mode == 'prepare-distroless-probe':
        plan = json.loads((E / 'plan.json').read_text())
        need(sha(E / 'first-source-frozen.py') == plan['sourceSHA256']
            and not (E / 'plan-v2.json').exists(), 'preserved_original_source_and_new_bounded_probe_revision')
        failure = json.loads((E / 'distroless-preprobe-failure.json').read_text())
        need(not failure['intentCreated'] and not failure['volumePatched']
            and not (E / (failure['volume'] + '-intent.json')).exists(), 'failed_probe_preceded_any_volume_mutation')
        completed = list(E.glob('*-result.json'))
        need(len(completed) == 12 and all(json.loads(p.read_text())['status'] == 'completed' for p in completed), 'preserve_all_prior_accepted_volume_receipts')
        plan.update(sourceSHA256=sha(Path(__file__)), previousPlanSHA256=sha(E / 'plan.json'),
            previousSourceSHA256=sha(E / 'first-source-frozen.py'),
            probeRevision='Exact existing distroless HTTP Echo container /data read through verified live host PID/mount; no relaxation of image/state/replica/Pod/data-directory checks')
        save('plan-v2.json', plan)
        print(json.dumps({'status': 'distroless_probe_revision_prepared', 'priorAcceptedVolumes': 12, 'recordsUnchanged': True}))
        return
    if a.mode == 'reconcile-rejected-patch':
        plan = json.loads((E / 'plan-v2.json').read_text())
        need(sha(E / 'distroless-source-frozen.py') == plan['sourceSHA256']
            and not (E / 'plan-v3.json').exists(), 'preserved_second_executed_source_and_new_reconciliation')
        name = 'pvc-7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec'
        failed = json.loads((E / (name + '-result.json')).read_text())
        original = json.loads((E / (name + '-intent.json')).read_text())
        need(failed['status'] == 'failed_inspect_actual_state_no_replay'
            and failed['errorCategory'] == 'patch_not_confirmed_inspect_actual_state_no_replay', 'exact_prior_submission_failure')
        record = next(r for r in plan['records'] if r['name'] == name)
        current = get('volumes.longhorn.io', name)
        rs, es = associated('replicas', name), associated('engines', name)
        need(current['metadata']['uid'] == record['uid'] == original['volumeUID']
            and current['spec'] == record['spec'] == original['beforeSpec']
            and current['status']['currentImage'] == OLD and healthy(current, es, rs)
            and data_directories(rs) == [tuple(x) for x in record['dataDirectories']]
            and pod_mounts(current) == record['mounts'], 'old_image_and_original_complete_data_spec_and_application_still_healthy')
        probe(record['mounts'])
        save('rejected-patch-qualified-reconciliation.json', {'status': 'original_atomic_image_change_not_applied',
            'volume': name, 'uid': record['uid'], 'currentImage': OLD, 'specImage': OLD,
            'originalDataDirectoriesAndApplicationPreserved': True, 'currentResourceVersion': current['metadata']['resourceVersion'],
            'previousResourceVersion': original['resourceVersion'],
            'firstErrorDiagnosticsRetained': False, 'firstErrorCause': 'Not established; controller resourceVersion changed, which is consistent with a failed atomic test',
            'nextOperation': 'One separately named fresh atomic intent after refreshing resourceVersion immediately after read probes; original failed intent/result are retained'})
        plan.update(sourceSHA256=sha(Path(__file__)), previousPlanSHA256=sha(E / 'plan-v2.json'),
            previousSourceSHA256=sha(E / 'distroless-source-frozen.py'), reconciledRejectedVolume=name)
        save('plan-v3.json', plan)
        print(json.dumps({'status': 'actual_original_healthy_state_reconciled', 'nextVolume': name, 'originalFailurePreserved': True}))
        return
    plan = json.loads((E / ('plan-v3.json' if (E / 'plan-v3.json').exists() else 'plan-v2.json' if (E / 'plan-v2.json').exists() else 'plan.json')).read_text())
    need(plan['sourceSHA256'] == sha(Path(__file__)) and plan['managerSourceSHA256'] == sha(Path(manager['__file__'])), 'unchanged_prepared_engine_and_recovery_sources')
    def keyname(record):
        return record['name'] + ('-rv-reconciled' if record['name'] == plan.get('reconciledRejectedVolume') else '')
    if a.mode == 'observe':
        volumes = {v['metadata']['name']: v for v in get('volumes.longhorn.io')}
        need(all((E / (keyname(r) + '-result.json')).exists() for r in plan['records']), 'every_initialized_volume_has_terminal_result')
        need(all(json.loads((E / (keyname(r) + '-result.json')).read_text())['status'] == 'completed' for r in plan['records']), 'all_serial_volume_checks_passed')
        need(all(volumes[r['name']]['metadata']['uid'] == r['uid'] and volumes[r['name']]['spec']['image'] == IMAGE
            and volumes[r['name']]['status']['currentImage'] == IMAGE for r in plan['records']), 'all_43_initialized_volume_images_upgraded')
        need(volumes[UNUSED]['spec']['image'] == OLD and volumes[UNUSED]['status']['state'] == 'detached', 'unused_wordpress_untouched_and_unattached')
        save('acceptance.json', {'status': 'all_43_initialized_engines_upgraded', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'targetImage': IMAGE, 'automaticEngineUpgradeLimit': 0, 'unusedWordPressUntouched': True,
            'allDataDirectoryAndApplicationReadChecksPassed': True, 'fullGoalComplete': False})
        print(json.dumps({'status': 'all_43_initialized_engines_upgraded'}))
        return
    need(manager['recovery']() == plan['recovery'], 'same_qualified_recovery_checkpoints')
    count = 0
    for record in plan['records']:
        name = record['name']
        operation = keyname(record)
        result_path = E / (operation + '-result.json')
        if result_path.exists():
            need(json.loads(result_path.read_text())['status'] == 'completed', 'failed_prior_volume_requires_inspection')
            continue
        need(not (E / (operation + '-intent.json')).exists(), 'incomplete_submitted_volume_requires_inspection_no_replay')
        controls()
        v = get('volumes.longhorn.io', name)
        replicas, engines = associated('replicas', name), associated('engines', name)
        need(v['metadata']['uid'] == record['uid'] and v['spec'] == record['spec']
            and v['status']['state'] == record['state'] and data_directories(replicas) == [tuple(x) for x in record['dataDirectories']], 'same_prepared_volume_spec_state_and_data_directories')
        if record['state'] == 'attached':
            need(healthy(v, engines, replicas), 'healthy_canary_or_serial_live_volume')
            need(pod_mounts(v) == record['mounts'], 'same_live_application_pods_before_upgrade')
            probe(record['mounts'])
        # Read probes and controller health reads can legitimately advance the
        # status resourceVersion. Refresh immediately before the atomic write,
        # preserving full spec/UID/state and all existing safety checks.
        v = get('volumes.longhorn.io', name)
        need(v['metadata']['uid'] == record['uid'] and v['spec'] == record['spec']
            and v['status']['state'] == record['state'], 'same_original_spec_and_state_after_probes')
        patch = [{'op': 'test', 'path': '/metadata/uid', 'value': record['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': v['metadata']['resourceVersion']},
            {'op': 'test', 'path': '/spec/image', 'value': OLD}, {'op': 'replace', 'path': '/spec/image', 'value': IMAGE}]
        save(operation + '-intent.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'volumeUID': record['uid'],
            'oldImage': OLD, 'newImage': IMAGE, 'resourceVersion': v['metadata']['resourceVersion'],
            'beforeSpec': v['spec'], 'dataDirectories': record['dataDirectories'], 'mounts': record['mounts']})
        result = {'status': 'started', 'volume': name, 'volumeUID': record['uid'], 'sourceSHA256': sha(Path(__file__))}
        try:
            p = call(['-n', 'longhorn-system', 'patch', 'volumes.longhorn.io', name, '--type=json', '--patch-file=/dev/stdin', '-o', 'json'], patch)
            result.update(patchExitCode=p.returncode, patchDiagnosticsSHA256=hashlib.sha256(p.stderr).hexdigest())
            if p.returncode:
                save(operation + '-patch-error.json', {'exitCode': p.returncode, 'diagnostic': p.stderr.decode(errors='replace')[:4096]})
            need(p.returncode == 0, 'patch_not_confirmed_inspect_actual_state_no_replay')
            deadline = time.monotonic() + 300
            while True:
                current = get('volumes.longhorn.io', name)
                rs, es = associated('replicas', name), associated('engines', name)
                ready = current['metadata']['uid'] == record['uid'] and current['status'].get('currentImage') == IMAGE
                ready = ready and current['status'].get('state') == record['state']
                ready = ready and (healthy(current, es, rs) if record['state'] == 'attached' else all(r['status'].get('currentState') == 'stopped' for r in rs))
                if ready and len(rs) == 2:
                    break
                need(time.monotonic() < deadline, 'volume_upgrade_observation_deadline_inspect_without_rollback')
                time.sleep(3)
            spec = dict(current['spec'])
            spec['image'] = OLD
            need(spec == record['spec'] and data_directories(rs) == [tuple(x) for x in record['dataDirectories']], 'only_image_changed_and_same_original_data_directories')
            if record['state'] == 'attached':
                need(all(e['status'].get('currentImage') == IMAGE for e in es)
                    and all(r['status'].get('currentImage') == IMAGE for r in rs), 'actual_new_engine_and_replica_process_images')
                need(pod_mounts(current) == record['mounts'], 'application_UID_image_restart_and_mount_identities_preserved')
                probe(record['mounts'])
            result.update(status='completed', originalState=record['state'], currentImage=IMAGE,
                originalDataDirectoriesPreserved=True, applicationReadChecksPassed=True,
                UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
        except Exception as error:
            result.update(status='failed_inspect_actual_state_no_replay', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
            raise
        finally:
            save(operation + '-result.json', result)
        count += 1
        print(json.dumps({'status': result['status'], 'volume': name, 'completedThisRun': count}), flush=True)
        if count >= a.limit:
            break


if __name__ == '__main__':
    try:
        main()
    finally:
        AUTH = None
