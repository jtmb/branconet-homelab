"""Fixed Homepage/Unpackerr native runtime cycles through validated charts/Flux.

Keep every original application, storage binding, native Secret reference and
configuration byte. Only existing release replica counts change temporarily.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy

import yaml

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-helper-runtime-20261028'
W = F / 'charts-longhorn-maintenance-20261028'
APPS = {
    'homepage': {'namespace': 'homepage', 'config': '/app/config', 'excludeLogs': True,
        'imageID': 'ghcr.io/gethomepage/homepage@sha256:19c5c09184458a41b7b5915e71463a39f36cd33540f41bdbed008791b8182d5f'},
    'unpackerr': {'namespace': 'plex', 'config': '/config', 'excludeLogs': False,
        'imageID': 'ghcr.io/unpackerr/unpackerr@sha256:21c6bfa4f4c86ab2dd0232da0dfb3ed4c5d929e42e09894e7b4d2154d0c144f6'},
}
IM_IMAGE = 'docker.io/longhornio/longhorn-instance-manager:v1.13.0@sha256:fc9e1c15e81988b04c146866ce7010b6df3a70f88302809bf53e19b27d1658a3'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def fp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (H / name).open('x') as out:
        json.dump(value, out, indent=2)


def ready(obj):
    return any(c['type'] == 'Ready' and c['status'] == 'True' and c.get('observedGeneration') == obj['metadata']['generation']
        for c in obj.get('status', {}).get('conditions', []))


def config(lib, pod, name):
    target = APPS[name]
    statuses = pod['status'].get('containerStatuses', [])
    need(len(statuses) == 1 and statuses[0]['ready'] and statuses[0]['restartCount'] == 0
        and statuses[0]['imageID'] == target['imageID'], 'one_ready_qualified_original_application')
    script = 'set -eu; set -o pipefail; cd "$1"; find . -type f '
    if target['excludeLogs']:
        script += '! -path "./logs/*" '
    script += '-exec sha256sum {} + | LC_ALL=C sort'
    p = lib['call'](['-n', target['namespace'], 'exec', pod['metadata']['name'], '-c', name,
        '--', '/bin/sh', '-c', script, '--', target['config']], timeout=45)
    need(p.returncode == 0, 'all_persistent_configuration_files_read_without_values_in_output')
    lines = p.stdout.splitlines()
    need(len(lines) == (9 if name == 'homepage' else 1), 'reviewed_complete_configuration_file_scope')
    return {'manifestSHA256': hashlib.sha256(p.stdout).hexdigest(), 'files': len(lines),
        'excluded': '/app/config/logs (native changing runtime logs, retained untouched)' if target['excludeLogs'] else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'stop', 'observe', 'detached', 'resume', 'verify'])
    a = parser.parse_args()
    need(os.geteuid() == 1000 and F.is_mount() and F.resolve() == F, 'original_controller_and_storage')
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 16 * 1024**3, 'one_gib_complete_peak_and_original_floors')
    os.umask(0o077)
    repo = Path(__file__).resolve().parents[5]
    engine_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'
    git_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_runtime_canary/files/cycle.py'
    lib, transport = runpy.run_path(str(engine_source)), runpy.run_path(str(git_source))
    git = transport['git']
    native = lib['get']
    cache = {}

    def get(kind, name=None, namespace='longhorn-system'):
        key = (kind, namespace)
        if key not in cache:
            cache[key] = native(kind, namespace=namespace)
        values = cache[key]
        if name:
            matched = [x for x in values if x['metadata']['name'] == name]
            need(len(matched) == 1, 'one_exact_existing_object_' + kind)
            return matched[0]
        return values

    for fn in ('controls', 'associated', 'pod_mounts'):
        lib[fn].__globals__['get'] = get
    lib['controls']()
    need(git('remote', 'get-url', 'origin') == 'https://github.com/jtmb/branconet-charts.git'
        and git('branch', '--show-current') == 'codex/longhorn-runtime-maintenance-20261028', 'original_private_source_owner')
    records = []
    for name, app in APPS.items():
        ns = app['namespace']
        hr = get('helmreleases.helm.toolkit.fluxcd.io', name, 'flux-system')
        dep = get('deployments', name, ns)
        need(hr['spec'].get('suspend') is False and hr['spec']['targetNamespace'] == ns
            and hr['spec']['chart']['spec']['chart'] == './charts/' + name
            and hr['spec']['chart']['spec']['sourceRef']['name'] == 'branconet-charts', 'existing_unsuspended_application_Flux_owner')
        claims = []
        volumes = []
        for v in dep['spec']['template']['spec'].get('volumes', []):
            if 'persistentVolumeClaim' not in v:
                continue
            claim = get('pvc', v['persistentVolumeClaim']['claimName'], ns)
            pv = get('pv', claim['spec']['volumeName'], namespace=None)
            claims.append({'name': claim['metadata']['name'], 'uid': claim['metadata']['uid'], 'specSHA256': fp(claim['spec']),
                'pv': pv['metadata']['name'], 'pvUID': pv['metadata']['uid'], 'pvSpecSHA256': fp(pv['spec']), 'driver': pv['spec']['csi']['driver']})
            need(claim['status']['phase'] == 'Bound', 'all_original_Longhorn_and_NAS_claims_Bound')
            if pv['spec']['csi']['driver'] == 'driver.longhorn.io':
                vol = get('volumes.longhorn.io', pv['spec']['csi']['volumeHandle'])
                rs, es = lib['associated']('replicas', vol['metadata']['name']), lib['associated']('engines', vol['metadata']['name'])
                need(vol['spec']['image'] == lib['IMAGE'], 'previously_upgraded_supported_engine')
                volumes.append((vol, rs, es))
            else:
                need(name == 'unpackerr' and pv['spec']['csi']['driver'] == 'smb.csi.k8s.io', 'existing_NAS_binding_only')
        need(len(volumes) == 1 and len(claims) == (1 if name == 'homepage' else 2), 'reviewed_exact_existing_storage_scope')
        selector = dep['spec']['selector']['matchLabels']
        pods = [p for p in get('pods', namespace=ns) if all(p['metadata'].get('labels', {}).get(k) == v for k, v in selector.items())]
        identity = {'name': name, 'namespace': ns, 'releaseUID': hr['metadata']['uid'], 'deploymentUID': dep['metadata']['uid'],
            'templateSHA256': fp(dep['spec']['template']), 'claims': claims,
            'volumes': [{'name': v['metadata']['name'], 'uid': v['metadata']['uid'], 'dataDirectories': lib['data_directories'](rs)} for v, rs, es in volumes]}
        records.append((identity, hr, dep, volumes, pods))
    if a.phase == 'observe':
        print(json.dumps([{'name': r['name'], 'desired': d['spec']['replicas'], 'available': d.get('status', {}).get('availableReplicas', 0),
            'releaseReady': ready(h), 'volumeStates': [v['status']['state'] for v, _, _ in vs],
            'instanceManagers': [e['status'].get('instanceManagerName') for _, _, es in vs for e in es],
            'pods': [{'name': p['metadata']['name'], 'phase': p['status']['phase']} for p in ps]} for r, h, d, vs, ps in records]))
        return
    sources = {'worker': sha(Path(__file__)), 'engine': sha(engine_source), 'git': sha(git_source)}
    if a.phase == 'prepare':
        need(not H.exists() and not git('status', '--porcelain'), 'new_metadata_cohort_and_clean_source')
        head = git('rev-parse', 'HEAD')
        need(transport['remote_main']() == head == '70fcccc5c452222bb64f203dc5a225c94bdf0bc5', 'reviewed_current_private_main')
        H.mkdir(mode=0o700)
        save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(H)], 'peakBytes': 1024**3,
            'regeneration': 'Tracked source, reachable original chart Git blobs and unchanged local validation publisher',
            'protected': 'All original source, failures, data, NAS media, native Secrets, PVC/PV/volume identities and replica directories',
            'endCondition': 'Both applications accepted on new native runtimes with identical configuration hashes; terminal exports reconciled'})
        saved = []
        backups = get('backups.longhorn.io')
        for r, h, d, vs, ps in records:
            need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1 and len(ps) == 1
                and all(lib['healthy'](v, es, rs) for v, rs, es in vs), 'healthy_original_applications_and_two_RW_replicas')
            need(all(any(b.get('status', {}).get('volumeName') == v['metadata']['name'] and b['status'].get('state') == 'Completed'
                and not b['status'].get('error') for b in backups) for v, _, _ in vs), 'completed_original_native_recovery_backups')
            r.update({'originalPodUID': ps[0]['metadata']['uid'], 'config': config(lib, ps[0], r['name']),
                'originalInstanceManagers': [e['status']['instanceManagerName'] for _, _, es in vs for e in es],
                'releaseDocument': yaml.safe_load((W / ('flux/releases/' + r['name'] + '.yaml')).read_bytes())})
            saved.append(r)
        save('plan.json', {'sources': sources, 'baseSHA': head, 'records': saved})
        print(json.dumps({'status': 'prepared', 'applications': list(APPS), 'directClusterWrites': False}))
        return
    plan = json.loads((H / 'plan.json').read_text())
    need(sources == plan['sources'], 'unchanged_prepared_sources')
    for (r, h, d, vs, ps), old in zip(records, plan['records'], strict=True):
        need(json.loads(json.dumps(r)) == {k: old[k] for k in r}, 'all_original_application_and_storage_identities_preserved')
    if a.phase in ('stop', 'resume'):
        desired = 0 if a.phase == 'stop' else 1
        need(not (H / (a.phase + '-intent.json')).exists() and not git('status', '--porcelain'), 'no_submission_replay_or_dirty_source')
        main = transport['remote_main']()
        if main != git('rev-parse', 'HEAD'):
            git('fetch', 'origin', main)
            git('merge', '--ff-only', main)
        for (r, h, d, vs, ps), old in zip(records, plan['records'], strict=True):
            if desired == 0:
                need(ready(h) and len(ps) == 1 and ps[0]['metadata']['uid'] == old['originalPodUID']
                    and config(lib, ps[0], r['name']) == old['config'] and all(lib['healthy'](v, es, rs) for v, rs, es in vs),
                    'same_original_healthy_configuration_before_stop')
            else:
                need((H / 'detached.json').exists() and not ps and all(v['status']['state'] == 'detached' for v, _, _ in vs),
                    'accepted_native_detach_before_restore')
            file = W / ('flux/releases/' + r['name'] + '.yaml')
            expected = json.loads(json.dumps(old['releaseDocument']))
            expected['spec']['values']['replicaCount'] = 1 - desired
            need(yaml.safe_load(file.read_bytes()) == expected, 'only_exact_original_release_replica_count_changes')
        paths = ['flux/releases/' + n + '.yaml' for n in APPS]
        for path in paths:
            file = W / path
            raw = file.read_bytes()
            old, new = ('    replicaCount: ' + str(1 - desired)).encode(), ('    replicaCount: ' + str(desired)).encode()
            need(raw.count(old) == 1, 'one_exact_original_replica_value')
            file.write_bytes(raw.replace(old, new))
        need(set(git('diff', '--name-only').splitlines()) == set(paths), 'exact_two_release_change_scope')
        git('add', '--', *paths)
        git('diff', '--cached', '--check')
        git('commit', '-m', ('Stop' if desired == 0 else 'Restore') + ' Homepage and Unpackerr for Longhorn runtime maintenance')
        commit = git('rev-parse', 'HEAD')
        save(a.phase + '-intent.json', {'sourceSHA': commit, 'previousMain': main, 'replicas': desired,
            'existingLocalValidationAndFluxRequired': True, 'directClusterWrite': False})
        git('push', 'origin', 'HEAD:refs/heads/main')
        need(transport['remote_main']() == commit, 'exact_main_commit_observed')
        save(a.phase + '-pushed.json', {'sourceSHA': commit, 'replicas': desired})
        print(json.dumps({'status': 'pushed_wait_for_existing_local_validation_and_Flux', 'sourceSHA': commit, 'replicas': desired}))
        return
    if a.phase == 'detached':
        for r, h, d, vs, ps in records:
            need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 0 and not ps
                and all(v['status']['state'] == 'detached' and all(x['status']['currentState'] == 'stopped' for x in rs + es)
                    and not get('volumeattachments.longhorn.io', v['metadata']['name'])['spec'].get('attachmentTickets') for v, rs, es in vs),
                'both_Flux_stopped_and_native_detach_without_forcing')
        save('detached.json', {'status': 'both_Flux_stopped_and_natively_detached', 'allDataIdentitiesPreserved': True})
        print(json.dumps({'status': 'both_Flux_stopped_and_natively_detached'}))
        return
    accepted = []
    for (r, h, d, vs, ps), old in zip(records, plan['records'], strict=True):
        need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1 and d['status'].get('availableReplicas') == 1
            and len(ps) == 1 and ps[0]['metadata']['uid'] != old['originalPodUID'] and config(lib, ps[0], r['name']) == old['config']
            and all(lib['healthy'](v, es, rs) for v, rs, es in vs), 'same_application_configuration_and_healthy_two_RW_replicas')
        for v, rs, es in vs:
            need(es[0]['status']['currentImage'] == lib['IMAGE'] and get('instancemanagers.longhorn.io', es[0]['status']['instanceManagerName'])['spec']['image'] == IM_IMAGE,
                'actual_native_engine_on_pinned_new_instance_manager')
        # Read the original mounted NAS directory without exposing names or
        # hashing/copying the media corpus. Its original PV binding is above.
        if r['name'] == 'unpackerr':
            p = lib['call'](['-n', r['namespace'], 'exec', ps[0]['metadata']['name'], '-c', r['name'], '--', '/bin/sh', '-c', 'ls -A /downloads >/dev/null'])
            need(p.returncode == 0, 'original_NAS_download_mount_readable')
        accepted.append({'identity': r, 'configuration': old['config'], 'podUID': ps[0]['metadata']['uid'],
            'imageID': APPS[r['name']]['imageID'], 'restartCount': 0, 'twoActualRWReplicas': True,
            'instanceManagers': [e['status']['instanceManagerName'] for _, _, es in vs for e in es], 'instanceManagerImage': IM_IMAGE})
    save('acceptance.json', {'status': 'same_Homepage_and_Unpackerr_data_on_new_runtime', 'applications': accepted,
        'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sourceSHA': json.loads((H / 'resume-pushed.json').read_text())['sourceSHA'], 'fullGoalComplete': False})
    print(json.dumps({'status': 'same_Homepage_and_Unpackerr_data_on_new_runtime'}))


if __name__ == '__main__':
    main()
