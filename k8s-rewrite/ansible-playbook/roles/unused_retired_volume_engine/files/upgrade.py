"""Update only an unused retired volume's future engine image, without attaching.

Fresh physical absence on both original replica hosts is mandatory before and
after. Preserve every original claim, replica, engine, key and data directory.
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
H = O / 'unused-retired-engine-update-20261028'
NAME = 'pvc-49df631b-614f-4180-b6e5-f719db4bfe2c'
UID = '4d5c0099-2068-4268-aa7f-98ab37c26001'
OLD = 'docker.io/longhornio/longhorn-engine:v1.12.1'
NEW = 'docker.io/longhornio/longhorn-engine:v1.13.0@sha256:b0cc5090889d57705acd69c5106492992e84560170ac3bec4a1cc8dd3fe83ca6'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, value):
    with (H / name).open('x') as out:
        json.dump(value, out, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    a = parser.parse_args()
    need(a.apply and os.geteuid() == 1000 and F.is_mount() and not H.exists(), 'deliberate_original_owner_once_only_operation')
    repo = Path(__file__).resolve().parents[5]
    for p in (F, Path('/mnt/c')):
        s = os.statvfs(p)
        need(s.f_bavail * s.f_frsize >= 15 * 1024**3 + 1024**2, 'original_capacity_floors_and_complete_metadata_peak')
    engine_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'
    engine = runpy.run_path(str(engine_source), run_name='accepted_engine_readonly_library')
    original_source = repo / 'scripts/migration/verify-unused-retired-volume.py'
    original = runpy.run_path(str(original_source), run_name='original_unused_volume_metadata_library')
    lineage = json.loads((O / 'unused-wordpress-lineage-20261027/result.json').read_text())
    need(lineage['status'] == 'unused_retired_volume_has_no_initialized_payload'
        and lineage['sourceSHA256'] == sha(original_source), 'unchanged_original_unused_volume_lineage')
    accepted = json.loads((O / 'longhorn-engine-upgrade-20261028/final-acceptance.json').read_text())
    need(accepted['initializedEnginesUpgraded'] == 43 and accepted['liveVolumesHealthyWithTwoActualRW'] == 28,
        'initialized_data_already_qualified_separately')
    engine['controls']()
    os.umask(0o077)
    H.mkdir(mode=0o700)
    sources = {str(p): sha(p) for p in [Path(__file__), engine_source, original_source]}
    save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
        'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(H)],
        'completePeakBytes': 1024**2, 'sources': sources,
        'regeneration': 'Same fixed single-volume metadata and original physical-absence checks; never replay a submitted patch',
        'endCondition': 'Only future image reference updated; original stopped resources, claim identity and physical absence preserved',
        'protected': 'All WordPress original datasets, all claims, native keys, backup data, replica directories and running applications'})
    password = None
    result = {'status': 'started', 'volume': NAME, 'volumeUID': UID, 'volumeAttachedOrInitialized': False,
        'applicationOrSecretChanged': False, 'sources': sources}
    try:
        get = original['get']
        before_claim = get('pvc', 'wordpress-db-upstream-20261026', 'wordpress')
        before_pv = get('pv', NAME, None)
        before = get('volumes.longhorn.io', NAME)
        need(before['metadata']['uid'] == UID and before_claim['metadata']['uid'] == lineage['claimUID']
            and before_pv['metadata']['uid'] == lineage['pvUID'] and before_claim['status']['phase'] == 'Bound', 'original_exact_unused_identity_chain')
        prior_proofs = {p['replicaUID']: p for p in lineage['physicalReplicaProofs']}

        def scope(expected):
            v = get('volumes.longhorn.io', NAME)
            need(v['metadata']['uid'] == UID and v['spec']['image'] == expected
                and v['spec']['encrypted'] and v['spec']['dataEngine'] == 'v1'
                and v['spec']['numberOfReplicas'] == 2 and v['status']['state'] == 'detached'
                and int(v['status'].get('actualSize', -1)) == 0 and not v['spec']['nodeID']
                and not v['spec'].get('lastAttachedBy') and not v['status'].get('lastBackup'), 'unused_stopped_never_attached_volume')
            need(not get('volumeattachments.longhorn.io', NAME)['spec'].get('attachmentTickets'), 'no_attachment_ticket')
            all_pods = engine['get']('pods', namespace=None)
            need(not any(p['metadata']['namespace'] == 'wordpress'
                and any(m.get('persistentVolumeClaim', {}).get('claimName') == before_claim['metadata']['name'] for m in p['spec'].get('volumes', []))
                for p in all_pods), 'no_application_consumer')
            rs = [r for r in get('replicas.longhorn.io')['items'] if r['spec']['volumeName'] == NAME]
            es = [e for e in get('engines.longhorn.io')['items'] if e['spec']['volumeName'] == NAME]
            need(len(rs) == 2 and {r['metadata']['uid'] for r in rs} == set(prior_proofs)
                and all(r['status']['currentState'] == 'stopped' and not r['spec'].get('healthyAt')
                    and not r['spec'].get('failedAt') for r in rs)
                and len(es) == 1 and es[0]['status']['currentState'] == 'stopped'
                and int(es[0]['status'].get('currentSize', -1)) == 0 and not es[0]['spec']['nodeID'], 'same_uninitialized_stopped_replicas_and_engine')
            return v, rs, es

        before, rs, es = scope(OLD)
        save('before.json', {'volume': before, 'claim': before_claim, 'persistentVolume': before_pv, 'replicas': rs, 'engines': es})
        lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'), run_name='protected_operator_input')
        password = lib['privilege_input']()

        def physical(replicas):
            proofs = []
            for r in replicas:
                previous = prior_proofs[r['metadata']['uid']]
                path = '/var/lib/longhorn/replicas/' + r['spec']['dataDirectoryName']
                need(path == previous['path'] and r['spec']['diskPath'] == '/var/lib/longhorn/', 'original_fixed_directory')
                host = previous['hostname']
                ip = {'workernode1': '192.168.0.6', 'workernode2': '192.168.0.5'}[host]
                code = ('import os,json,socket;from pathlib import Path;p=Path(' + repr(path) + ');'
                    + 'assert socket.gethostname()==' + repr(host) + ';assert p.parent.resolve()==p.parent and p.parent.is_dir();'
                    + 'assert not os.path.lexists(p);print(json.dumps({"hostname":socket.gethostname(),"path":str(p),"absent":True}))')
                p = subprocess.run(original['SSH'] + ['james@' + ip, shlex.join(['sudo', '-S', '-k', '-p', '',
                    '/usr/bin/python3', '-B', '-c', code])], input=password + b'\n', capture_output=True, timeout=45)
                need(p.returncode == 0 and len(p.stdout) < 4096, 'original_physical_directory_still_absent_' + host)
                proofs.append(json.loads(p.stdout))
            return proofs

        save('physical-before.json', physical(rs))
        fresh, _, _ = scope(OLD)
        need(fresh['spec'] == before['spec'], 'unchanged_complete_spec_before_patch')
        patch = [{'op': 'test', 'path': '/metadata/uid', 'value': UID},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': fresh['metadata']['resourceVersion']},
            {'op': 'test', 'path': '/spec/image', 'value': OLD}, {'op': 'replace', 'path': '/spec/image', 'value': NEW}]
        args = ['-n', 'longhorn-system', 'patch', 'volumes.longhorn.io', NAME, '--type=json', '--patch-file=/dev/stdin', '-o', 'json']
        dry = engine['call'](args + ['--dry-run=server'], patch)
        need(dry.returncode == 0 and json.loads(dry.stdout)['spec']['image'] == NEW, 'server_accepted_future_image_only_change')
        save('intent.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'patch': patch,
            'beforeSpecSHA256': hashlib.sha256(json.dumps(before['spec'], sort_keys=True).encode()).hexdigest(),
            'sourceSHA256': sha(Path(__file__)), 'attachOrInitializeRequested': False})
        p = engine['call'](args, patch)
        result.update(patchExitCode=p.returncode, diagnosticsSHA256=hashlib.sha256(p.stderr).hexdigest())
        need(p.returncode == 0, 'patch_unconfirmed_inspect_actual_state_no_replay')
        deadline = time.monotonic() + 60
        while True:
            after, ar, ae = scope(NEW)
            if after['status'].get('currentImage') == NEW and all(x['spec']['image'] == NEW for x in ar + ae):
                break
            need(time.monotonic() < deadline, 'metadata_reconciliation_deadline_no_attach_or_retry')
            time.sleep(2)
        spec = dict(after['spec'])
        spec['image'] = OLD
        need(spec == before['spec'] and engine['data_directories'](ar) == engine['data_directories'](rs)
            and ae[0]['metadata']['uid'] == es[0]['metadata']['uid'], 'only_future_image_changed_and_original_data_metadata_preserved')
        save('physical-after.json', physical(ar))
        claim = get('pvc', before_claim['metadata']['name'], 'wordpress')
        pv = get('pv', NAME, None)
        need(claim['metadata']['uid'] == before_claim['metadata']['uid'] and claim['spec'] == before_claim['spec']
            and pv['metadata']['uid'] == before_pv['metadata']['uid'] and pv['spec'] == before_pv['spec'], 'original_claim_and_PV_complete_identity_and_spec_preserved')
        result.update(status='unused_future_engine_updated_without_initialization', UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            allOriginalUIDsPreserved=True, claimAndPVSpecPreserved=True, physicalDirectoriesAbsentBeforeAndAfter=True,
            originalReplicasAndEngineStopped=True, futureImage=NEW, oldReferenceRetirementPendingController=True)
    except Exception as error:
        result.update(status='failed_preserve_originals_inspect_actual_state', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        password = None
        result['sourcesUnchanged'] = all(sha(Path(p)) == digest for p, digest in sources.items())
        save('result.json', result)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
