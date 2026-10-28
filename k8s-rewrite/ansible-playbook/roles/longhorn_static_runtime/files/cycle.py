"""Cycle only the four existing static websites through validated charts/Flux.

No image/template changes, direct scale patches, forced detach or PVC mutations.
The prepared source and data identities are immutable throughout this cohort.
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
H = F / 'platform-upstream-review-20261027/longhorn-static-runtime-20261028'
W = F / 'charts-longhorn-maintenance-20261028'
NAMES = ('aplb', 'lucinda-art-gallery', 'minecraft-website', 'santos-web')
APP_IMAGE = 'docker.io/library/nginx:1.30.6-alpine3.24-slim@sha256:dede8895648b461178c3bc604f7eed4423efe5220b2c4d839f5eb3d34ac3f8f7'
IM_IMAGE = 'docker.io/longhornio/longhorn-instance-manager:v1.13.0@sha256:fc9e1c15e81988b04c146866ce7010b6df3a70f88302809bf53e19b27d1658a3'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(name, value):
    with (H / name).open('x') as out:
        json.dump(value, out, indent=2)


def ready(obj):
    return any(c['type'] == 'Ready' and c['status'] == 'True'
        and c.get('observedGeneration') == obj['metadata']['generation']
        for c in obj.get('status', {}).get('conditions', []))


def contents(lib, pod, name):
    statuses = pod['status']['containerStatuses']
    need(len(statuses) == 1 and statuses[0]['ready'] and statuses[0]['restartCount'] == 0,
        'one_ready_original_static_application_container')
    # Hash actual file bytes, filenames and symlink targets; emit hashes only.
    # pipefail prevents any find/read error from being hidden by the sorter.
    script = ('set -eu; set -o pipefail; cd /usr/share/nginx/html; '
        'find . -type f -exec sha256sum {} + | LC_ALL=C sort; '
        'find . -type l -exec readlink {} \\; | LC_ALL=C sort')
    p = lib['call'](['-n', 'web-apps', 'exec', pod['metadata']['name'], '-c', name,
        '--', '/bin/sh', '-c', script], timeout=90)
    need(p.returncode == 0, 'all_existing_static_files_and_symlinks_read_successfully')
    return {'manifestSHA256': hashlib.sha256(p.stdout).hexdigest(),
        'manifestLines': len(p.stdout.splitlines()), 'manifestBytes': len(p.stdout)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['prepare', 'stop', 'observe', 'detached', 'resume', 'verify'])
    a = p.parse_args()
    need(F.is_mount() and os.geteuid() == 1000 and F.resolve() == F, 'original_F_storage_and_controller_owner')
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 16 * 1024**3, 'one_gib_peak_and_fifteen_gib_floors')
    os.umask(0o077)
    repo = Path(__file__).resolve().parents[5]
    engine_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'
    git_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_runtime_canary/files/cycle.py'
    lib = runpy.run_path(str(engine_source))
    gitlib = runpy.run_path(str(git_source))
    git = gitlib['git']
    native_get = lib['get']
    # One fresh snapshot per kind in each invocation; no repeated fleet scans.
    cache = {}

    def get(kind, name=None, namespace='longhorn-system'):
        key = (kind, namespace)
        if key not in cache:
            cache[key] = native_get(kind, namespace=namespace)
        rows = cache[key]
        if name:
            matches = [v for v in rows if v['metadata']['name'] == name]
            need(len(matches) == 1, 'one_exact_existing_object_' + kind)
            return matches[0]
        return rows

    for name in ('controls', 'associated', 'pod_mounts'):
        lib[name].__globals__['get'] = get
    lib['controls']()
    need(git('remote', 'get-url', 'origin') == 'https://github.com/jtmb/branconet-charts.git'
        and git('branch', '--show-current') == 'codex/longhorn-runtime-maintenance-20261028',
        'existing_isolated_private_chart_owner')
    records = []
    for name in NAMES:
        release = get('helmreleases.helm.toolkit.fluxcd.io', name, 'flux-system')
        dep = get('deployments', name, 'web-apps')
        spec = release['spec']
        need(spec.get('suspend') is False and spec['chart']['spec']['chart'] == './charts/' + name
            and spec['targetNamespace'] == 'web-apps' and spec['chart']['spec']['sourceRef']['name'] == 'branconet-charts',
            'existing_unsuspended_static_Flux_owner')
        vols = dep['spec']['template']['spec']['volumes']
        need(len(vols) == 1 and set(vols[0]) == {'name', 'persistentVolumeClaim'}, 'one_existing_static_data_claim')
        claim = get('pvc', vols[0]['persistentVolumeClaim']['claimName'], 'web-apps')
        pv = get('pv', claim['spec']['volumeName'], namespace=None)
        need(pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_Longhorn_claim')
        volume = get('volumes.longhorn.io', pv['spec']['csi']['volumeHandle'])
        rs, es = lib['associated']('replicas', volume['metadata']['name']), lib['associated']('engines', volume['metadata']['name'])
        need(dep['spec']['template']['spec']['containers'][0]['image'] == APP_IMAGE
            and len(dep['spec']['template']['spec']['containers']) == 1
            and volume['spec']['image'] == lib['IMAGE'], 'same_qualified_static_application_and_engine')
        pods = [x for x in get('pods', namespace='web-apps') if x['metadata'].get('labels', {}).get('app.kubernetes.io/instance') == name
            and not x['metadata'].get('deletionTimestamp')]
        # The source chart's actual selector is authoritative, including older
        # charts which do not use app.kubernetes.io/instance.
        selector = dep['spec']['selector']['matchLabels']
        pods = [x for x in get('pods', namespace='web-apps') if all(x['metadata'].get('labels', {}).get(k) == v for k, v in selector.items())]
        record = {'name': name, 'releaseUID': release['metadata']['uid'], 'deploymentUID': dep['metadata']['uid'],
            'templateSHA256': fp(dep['spec']['template']), 'claimUID': claim['metadata']['uid'], 'claimSpecSHA256': fp(claim['spec']),
            'pvUID': pv['metadata']['uid'], 'pvSpecSHA256': fp(pv['spec']), 'volume': volume['metadata']['name'],
            'volumeUID': volume['metadata']['uid'], 'dataDirectories': lib['data_directories'](rs)}
        records.append((record, release, dep, volume, rs, es, pods))
    if a.phase == 'observe':
        print(json.dumps([{'name': r['name'], 'desired': d['spec']['replicas'], 'available': d.get('status', {}).get('availableReplicas', 0),
            'releaseReady': ready(h), 'volumeState': v['status']['state'], 'robustness': v['status']['robustness'],
            'instanceManagers': [e['status'].get('instanceManagerName') for e in es],
            'pods': [{'name': p['metadata']['name'], 'phase': p['status']['phase'], 'deleting': bool(p['metadata'].get('deletionTimestamp'))} for p in ps]}
            for r, h, d, v, rs, es, ps in records]))
        return
    sources = {'worker': sha(Path(__file__)), 'engine': sha(engine_source), 'git': sha(git_source)}
    if a.phase == 'prepare':
        need(not H.exists() and not git('status', '--porcelain'), 'new_cohort_and_clean_protected_source')
        head = git('rev-parse', 'HEAD')
        need(gitlib['remote_main']() == head == 'b5286ec8bf287ca4c248356ee59e860fccb43749', 'reviewed_current_source')
        H.mkdir(mode=0o700)
        save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(H)],
            'peakBytes': 1024**3, 'regeneration': 'Tracked worker, original reachable Git blobs and unchanged local charts validation publisher',
            'protected': 'All original PVC/PV/volume identities, replica directories, website files, images, templates, native Secrets and rollback evidence',
            'endCondition': 'Four original static websites read successfully with unchanged content hashes on the new instance managers; reconcile terminal publisher exports'})
        saved = []
        for r, h, d, v, rs, es, ps in records:
            need(d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1 and ready(h)
                and lib['healthy'](v, es, rs) and len(ps) == 1, 'healthy_original_static_site')
            r.update({'releaseDocument': yaml.safe_load((W / ('flux/releases/' + r['name'] + '.yaml')).read_bytes()),
                'originalPodUID': ps[0]['metadata']['uid'], 'originalImageID': ps[0]['status']['containerStatuses'][0]['imageID'],
                'originalInstanceManager': es[0]['status']['instanceManagerName'], 'contents': contents(lib, ps[0], r['name'])})
            saved.append(r)
        save('plan.json', {'sources': sources, 'baseSHA': head, 'records': saved})
        print(json.dumps({'status': 'prepared', 'sites': list(NAMES), 'directClusterWrites': False}))
        return
    plan = json.loads((H / 'plan.json').read_text())
    need(sources == plan['sources'], 'unchanged_prepared_sources')
    for (r, h, d, v, rs, es, ps), original in zip(records, plan['records'], strict=True):
        need(json.loads(json.dumps(r)) == {k: original[k] for k in r}, 'original_data_and_template_identities_preserved')
    if a.phase in ('stop', 'resume'):
        desired = 0 if a.phase == 'stop' else 1
        previous = 1 - desired
        need(not (H / (a.phase + '-intent.json')).exists() and not git('status', '--porcelain'), 'no_blind_submission_replay_or_dirty_source')
        current = gitlib['remote_main']()
        if current != git('rev-parse', 'HEAD'):
            git('fetch', 'origin', current)
            git('merge', '--ff-only', current)
        for (r, h, d, v, rs, es, ps), original in zip(records, plan['records'], strict=True):
            if a.phase == 'stop':
                need(ready(h) and lib['healthy'](v, es, rs) and len(ps) == 1
                    and ps[0]['metadata']['uid'] == original['originalPodUID']
                    and contents(lib, ps[0], r['name']) == original['contents'], 'unchanged_healthy_original_before_stop')
            else:
                need((H / 'detached.json').exists() and v['status']['state'] == 'detached' and not ps,
                    'accepted_full_native_detach_before_restore')
            file = W / ('flux/releases/' + r['name'] + '.yaml')
            document = yaml.safe_load(file.read_bytes())
            expected = json.loads(json.dumps(original['releaseDocument']))
            expected['spec']['values']['replicaCount'] = previous
            need(document == expected, 'only_original_static_release_replica_field_changes')
        for r, *_ in records:
            file = W / ('flux/releases/' + r['name'] + '.yaml')
            old, new = ('    replicaCount: ' + str(previous)).encode(), ('    replicaCount: ' + str(desired)).encode()
            raw = file.read_bytes()
            need(raw.count(old) == 1, 'single_replica_value')
            file.write_bytes(raw.replace(old, new))
        paths = ['flux/releases/' + n + '.yaml' for n in NAMES]
        need(set(git('diff', '--name-only').splitlines()) == set(paths), 'exact_four_release_source_scope')
        git('add', '--', *paths)
        git('diff', '--cached', '--check')
        git('commit', '-m', ('Stop' if desired == 0 else 'Restore') + ' four static websites for Longhorn runtime maintenance')
        commit = git('rev-parse', 'HEAD')
        save(a.phase + '-intent.json', {'sourceSHA': commit, 'previousMain': current, 'replicaCount': desired,
            'sites': list(NAMES), 'existingValidationAndFluxRequired': True, 'directClusterWrite': False})
        git('push', 'origin', 'HEAD:refs/heads/main')
        need(gitlib['remote_main']() == commit, 'exact_main_commit_observed')
        save(a.phase + '-pushed.json', {'sourceSHA': commit, 'replicaCount': desired})
        print(json.dumps({'status': 'pushed_wait_for_existing_validation_and_Flux', 'sourceSHA': commit, 'replicas': desired}))
        return
    if a.phase == 'detached':
        for r, h, d, v, rs, es, ps in records:
            need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 0
                and not ps and v['status']['state'] == 'detached'
                and all(x['status']['currentState'] == 'stopped' for x in rs + es)
                and not get('volumeattachments.longhorn.io', r['volume'])['spec'].get('attachmentTickets'),
                'Flux_stop_and_native_detach_all_four_sites')
        save('detached.json', {'status': 'all_four_Flux_stopped_and_natively_detached', 'originalDataIdentitiesPreserved': True})
        print(json.dumps({'status': 'all_four_Flux_stopped_and_natively_detached'}))
        return
    accepted = []
    for (r, h, d, v, rs, es, ps), original in zip(records, plan['records'], strict=True):
        need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1
            and d['status'].get('availableReplicas') == 1 and lib['healthy'](v, es, rs) and len(ps) == 1,
            'Flux_restored_healthy_original_static_site_and_two_RW_replicas')
        im = get('instancemanagers.longhorn.io', es[0]['status']['instanceManagerName'])
        need(im['spec']['image'] == IM_IMAGE and es[0]['status']['currentImage'] == lib['IMAGE']
            and ps[0]['metadata']['uid'] != original['originalPodUID']
            and ps[0]['status']['containerStatuses'][0]['imageID'] == original['originalImageID']
            and contents(lib, ps[0], r['name']) == original['contents'], 'new_runtime_same_application_and_all_static_file_hashes')
        accepted.append({'name': r['name'], 'volume': r['volume'], 'volumeUID': r['volumeUID'], 'claimUID': r['claimUID'],
            'podUID': ps[0]['metadata']['uid'], 'imageID': original['originalImageID'], 'instanceManager': im['metadata']['name'],
            'instanceManagerImage': IM_IMAGE, 'contents': original['contents'], 'twoActualRWReplicas': True, 'originalDataAndTemplatePreserved': True})
    save('acceptance.json', {'status': 'four_original_sites_on_new_runtime_with_identical_file_hashes', 'sites': accepted,
        'sourceSHA': json.loads((H / 'resume-pushed.json').read_text())['sourceSHA'],
        'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'fullGoalComplete': False})
    print(json.dumps({'status': 'four_original_sites_on_new_runtime_with_identical_file_hashes'}))


if __name__ == '__main__':
    main()
