"""Normal runtime cycle for the fixed 14-app / 17-volume maintenance batch.

Only release replica counts change through the existing validated Flux pipeline.
Data is neither copied nor rewritten. Pi-hole, Ingenium and held BORTUS stay up.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import runpy

import yaml

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-application-batch-20261028'
W = F / 'charts-longhorn-maintenance-20261028'
OWNERS = F / 'platform-upstream-review-20261027/longhorn-helper-runtime-20261028/remaining-runtime-owners.json'
APPS = {'vaultwarden': 'vaultwarden', 'ruckus-db': 'ruckus', 'overseerr': 'plex', 'ytdl': 'plex',
    'bazarr': 'plex', 'jackett': 'plex', 'radarr': 'plex', 'tautulli': 'plex', 'qbittorrent': 'plex',
    'qbit-monitor': 'plex', 'mealie': 'mealie', 'xteve': 'plex', 'plex': 'plex', 'sonarr': 'plex'}
IM = 'docker.io/longhornio/longhorn-instance-manager:v1.13.0@sha256:fc9e1c15e81988b04c146866ce7010b6df3a70f88302809bf53e19b27d1658a3'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['prepare', 'stop', 'observe', 'detached', 'resume', 'verify'])
    phase = p.parse_args().phase
    repo = Path(__file__).resolve().parents[5]
    engine_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'
    git_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_runtime_canary/files/cycle.py'
    helper_source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_app_runtime/files/cycle.py'
    lib, transport, helpers = runpy.run_path(str(engine_source)), runpy.run_path(str(git_source)), runpy.run_path(str(helper_source))
    need, sha, fp, ready = lib['need'], lib['sha'], helpers['fp'], helpers['ready']
    git = transport['git']

    def save(name, value):
        with (H / name).open('x') as out:
            json.dump(value, out, indent=2)

    need(os.geteuid() == 1000 and F.is_mount() and F.resolve() == F, 'original_controller_and_F_storage')
    os.umask(0o077)
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 16 * 1024**3, 'one_gib_complete_peak_and_original_floors')
    cache, native = {}, lib['get']

    def get(kind, name=None, namespace='longhorn-system'):
        key = (kind, namespace)
        if key not in cache:
            cache[key] = native(kind, namespace=namespace)
        if name:
            matched = [x for x in cache[key] if x['metadata']['name'] == name]
            need(len(matched) == 1, 'one_exact_existing_object_' + kind)
            return matched[0]
        return cache[key]

    for fn in ('controls', 'associated', 'pod_mounts'):
        lib[fn].__globals__['get'] = get
    lib['controls']()
    need(git('remote', 'get-url', 'origin') == 'https://github.com/jtmb/branconet-charts.git'
        and git('branch', '--show-current') == 'codex/longhorn-runtime-maintenance-20261028', 'original_private_chart_owner')
    owner_rows = json.loads(OWNERS.read_text())['volumes']
    expected_volumes = {x['volume'] for x in owner_rows if any(m['deployment'] in APPS for m in x['mounts'])}
    need(len(APPS) == 14 and len(expected_volumes) == 17, 'reviewed_exact_batch_and_shared_volume_scope')
    applications, volumes, all_claims = [], {}, []
    for name, ns in APPS.items():
        hr = get('helmreleases.helm.toolkit.fluxcd.io', name, 'flux-system')
        dep = get('deployments', name, ns)
        need(hr['spec'].get('suspend') is False and hr['spec']['targetNamespace'] == ns
            and hr['spec']['chart']['spec']['chart'] == './charts/' + name
            and hr['spec']['chart']['spec']['sourceRef']['name'] == 'branconet-charts', 'existing_unsuspended_Flux_owner')
        selector = dep['spec']['selector']['matchLabels']
        pods = [x for x in get('pods', namespace=ns) if all(x['metadata'].get('labels', {}).get(k) == v for k, v in selector.items())]
        claims = []
        for v in dep['spec']['template']['spec'].get('volumes', []):
            if 'persistentVolumeClaim' not in v:
                continue
            claim = get('pvc', v['persistentVolumeClaim']['claimName'], ns)
            pv = get('pv', claim['spec']['volumeName'], namespace=None)
            need(claim['status']['phase'] == 'Bound' and pv['spec']['csi']['driver'] in ('driver.longhorn.io', 'smb.csi.k8s.io'), 'original_bound_supported_claim')
            claims.append({'name': claim['metadata']['name'], 'uid': claim['metadata']['uid'], 'specSHA256': fp(claim['spec']),
                'pv': pv['metadata']['name'], 'pvUID': pv['metadata']['uid'], 'pvSpecSHA256': fp(pv['spec']), 'driver': pv['spec']['csi']['driver']})
            if pv['spec']['csi']['driver'] == 'driver.longhorn.io':
                vn = pv['spec']['csi']['volumeHandle']
                need(vn in expected_volumes, 'no_unreviewed_volume_in_batch')
                if vn not in volumes:
                    vol = get('volumes.longhorn.io', vn)
                    rs, es = lib['associated']('replicas', vn), lib['associated']('engines', vn)
                    need(vol['spec']['image'] == lib['IMAGE'] and vol['spec']['dataEngine'] == 'v1'
                        and vol['spec']['encrypted'] and vol['spec']['numberOfReplicas'] == 2, 'qualified_original_storage_controls')
                    identity = {'name': vn, 'uid': vol['metadata']['uid'], 'dataDirectories': lib['data_directories'](rs),
                        'controlsSHA256': fp({k: vol['spec'].get(k) for k in ('image', 'dataEngine', 'encrypted', 'numberOfReplicas', 'frontend', 'size', 'backupTargetName', 'diskSelector', 'nodeSelector')})}
                    volumes[vn] = (identity, vol, rs, es)
        need(claims, 'every_reviewed_application_has_its_original_data_claim')
        identity = {'name': name, 'namespace': ns, 'releaseUID': hr['metadata']['uid'], 'deploymentUID': dep['metadata']['uid'],
            'templateSHA256': fp(dep['spec']['template']), 'claims': claims}
        applications.append((identity, hr, dep, pods))
        all_claims.extend(claims)
    need(set(volumes) == expected_volumes, 'all_and_only_seventeen_reviewed_volumes')
    sources = {str(p.relative_to(repo)): sha(p) for p in (Path(__file__).resolve(), engine_source, git_source, helper_source)}
    sources['originalOwnerInventory'] = sha(OWNERS)
    if phase == 'observe':
        print(json.dumps({'applications': [{'name': r['name'], 'desired': d['spec']['replicas'], 'available': d.get('status', {}).get('availableReplicas', 0),
            'releaseReady': ready(h), 'pods': [{'name': p['metadata']['name'], 'phase': p['status']['phase']} for p in ps]} for r, h, d, ps in applications],
            'volumeStates': {n: v['status']['state'] for n, (_, v, _, _) in volumes.items()}}))
        return
    if phase == 'prepare':
        need(not H.exists() and not git('status', '--porcelain'), 'new_batch_and_clean_source')
        head = git('rev-parse', 'HEAD')
        need(transport['remote_main']() == head == 'bf739c36dc0676f1d8a0e29fd95f40b78bcdb224', 'reviewed_current_private_main')
        H.mkdir(mode=0o700)
        save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(H)], 'peakBytes': 1024**3,
            'regeneration': 'Tracked sources, original reachable chart Git blobs and unchanged local validation publisher',
            'protected': 'All application data, original bindings/replica directories/native Secrets, NAS media, source and failures',
            'endCondition': 'All fourteen original apps restored on seventeen new runtimes; terminal exports reconciled',
            'excluded': ['pihole', 'ingenium', 'bortus']})
        saved_apps = []
        for r, hr, d, ps in applications:
            need(ready(hr) and d['spec']['replicas'] == hr['spec']['values']['replicaCount'] == 1 and len(ps) == 1
                and not ps[0]['metadata'].get('deletionTimestamp') and all(c.get('ready') for c in ps[0]['status']['containerStatuses']), 'original_single_healthy_application')
            r.update({'originalPodUID': ps[0]['metadata']['uid'], 'images': {c['name']: c['imageID'] for c in ps[0]['status']['containerStatuses']},
                'releaseDocument': yaml.safe_load((W / ('flux/releases/' + r['name'] + '.yaml')).read_bytes())})
            saved_apps.append(r)
        pod_uids = {r['originalPodUID'] for r in saved_apps}
        backups = get('backups.longhorn.io')
        for vn, (_, vol, rs, es) in volumes.items():
            need(lib['healthy'](vol, es, rs) and any(b.get('status', {}).get('volumeName') == vn and b['status'].get('state') == 'Completed'
                and not b['status'].get('error') for b in backups), 'healthy_two_RW_replicas_and_completed_native_recovery')
            mounts = lib['pod_mounts'](vol)
            need(mounts and {m['podUID'] for m in mounts} <= pod_uids, 'every_shared_volume_consumer_in_fixed_batch')
            lib['probe'](mounts)
        save('plan.json', {'sources': sources, 'baseSHA': head, 'applications': saved_apps, 'volumes': [r for r, *_ in volumes.values()]})
        print(json.dumps({'status': 'prepared', 'applications': 14, 'volumes': 17, 'directClusterWrites': False}))
        return
    plan = json.loads((H / 'plan.json').read_text())
    need(sources == plan['sources'], 'unchanged_prepared_sources')
    for (r, h, d, ps), old in zip(applications, plan['applications'], strict=True):
        need(r == {k: old[k] for k in r}, 'all_original_application_templates_and_claim_bindings_preserved')
    need(json.loads(json.dumps([r for r, *_ in volumes.values()])) == plan['volumes'], 'all_original_volume_controls_and_replica_directories_preserved')
    if phase in ('stop', 'resume'):
        desired = 0 if phase == 'stop' else 1
        need(not (H / (phase + '-intent.json')).exists() and not git('status', '--porcelain'), 'no_submission_replay_or_dirty_source')
        main = transport['remote_main']()
        if main != git('rev-parse', 'HEAD'):
            git('fetch', 'origin', main)
            git('merge', '--ff-only', main)
        for (r, hr, d, ps), old in zip(applications, plan['applications'], strict=True):
            need(ready(hr) and d['spec']['replicas'] == hr['spec']['values']['replicaCount'] == 1 - desired, 'prior_Flux_state_accepted')
            if desired == 0:
                need(len(ps) == 1 and ps[0]['metadata']['uid'] == old['originalPodUID']
                    and all(c.get('ready') for c in ps[0]['status']['containerStatuses'])
                    and {c['name']: c['imageID'] for c in ps[0]['status']['containerStatuses']} == old['images'], 'same_original_healthy_application_before_stop')
            else:
                need((H / 'detached.json').exists() and not ps, 'accepted_complete_batch_detach_before_restore')
            expected = json.loads(json.dumps(old['releaseDocument']))
            expected['spec']['values']['replicaCount'] = 1 - desired
            need(yaml.safe_load((W / ('flux/releases/' + r['name'] + '.yaml')).read_bytes()) == expected, 'only_existing_replica_counts_change')
        need(all(lib['healthy'](v, es, rs) if desired == 0 else v['status']['state'] == 'detached' for _, v, rs, es in volumes.values()), 'qualified_batch_volume_states')
        paths = ['flux/releases/' + n + '.yaml' for n in APPS]
        for path in paths:
            file = W / path
            raw = file.read_bytes()
            old, new = ('    replicaCount: ' + str(1 - desired)).encode(), ('    replicaCount: ' + str(desired)).encode()
            need(raw.count(old) == 1, 'one_exact_original_replica_value')
            file.write_bytes(raw.replace(old, new))
        need(set(git('diff', '--name-only').splitlines()) == set(paths), 'exact_fourteen_release_change_scope')
        git('add', '--', *paths)
        git('diff', '--cached', '--check')
        git('commit', '-m', ('Stop' if desired == 0 else 'Restore') + ' fourteen applications for Longhorn runtime maintenance')
        commit = git('rev-parse', 'HEAD')
        save(phase + '-intent.json', {'sourceSHA': commit, 'previousMain': main, 'replicas': desired, 'existingLocalValidationAndFluxRequired': True, 'directClusterWrite': False})
        git('push', 'origin', 'HEAD:refs/heads/main')
        need(transport['remote_main']() == commit, 'exact_main_observed')
        save(phase + '-pushed.json', {'sourceSHA': commit, 'replicas': desired})
        print(json.dumps({'status': 'pushed_wait_for_existing_local_validation_and_Flux', 'sourceSHA': commit, 'replicas': desired}))
        return
    if phase == 'detached':
        need(all(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 0 and not ps for _, h, d, ps in applications), 'all_fourteen_Flux_stopped')
        for vn, (_, v, rs, es) in volumes.items():
            need(v['status']['state'] == 'detached' and all(x['status']['currentState'] == 'stopped' for x in rs + es)
                and not get('volumeattachments.longhorn.io', vn)['spec'].get('attachmentTickets') and not lib['pod_mounts'](v), 'all_consumers_gone_and_native_detach_without_forcing')
        save('detached.json', {'status': 'fourteen_apps_stopped_seventeen_volumes_natively_detached', 'allOriginalDataIdentitiesPreserved': True})
        print(json.dumps({'status': 'fourteen_apps_stopped_seventeen_volumes_natively_detached'}))
        return
    accepted_apps = []
    for (r, h, d, ps), old in zip(applications, plan['applications'], strict=True):
        need(ready(h) and d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 1 and d['status'].get('availableReplicas') == 1 and len(ps) == 1
            and ps[0]['metadata']['uid'] != old['originalPodUID'] and not ps[0]['metadata'].get('deletionTimestamp')
            and all(c.get('ready') and c['restartCount'] == 0 for c in ps[0]['status']['containerStatuses'])
            and {c['name']: c['imageID'] for c in ps[0]['status']['containerStatuses']} == old['images'], 'same_images_and_ready_new_application_containers')
        accepted_apps.append({'identity': r, 'podUID': ps[0]['metadata']['uid'], 'images': old['images'], 'allContainersReadyWithZeroRestarts': True})
    accepted_volumes = []
    for vn, (r, v, rs, es) in volumes.items():
        need(lib['healthy'](v, es, rs) and es[0]['status']['currentImage'] == lib['IMAGE']
            and get('instancemanagers.longhorn.io', es[0]['status']['instanceManagerName'])['spec']['image'] == IM, 'healthy_two_RW_replicas_on_new_native_runtime')
        mounts = lib['pod_mounts'](v)
        need(mounts, 'original_data_is_mounted_by_restored_applications')
        lib['probe'](mounts)
        accepted_volumes.append({'identity': r, 'instanceManager': es[0]['status']['instanceManagerName'], 'instanceManagerImage': IM,
            'twoActualRWReplicas': True, 'mountReadsPassed': True})
    save('acceptance.json', {'status': 'fourteen_original_apps_on_seventeen_new_native_runtimes', 'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'applications': accepted_apps, 'volumes': accepted_volumes, 'sourceSHA': json.loads((H / 'resume-pushed.json').read_text())['sourceSHA'],
        'dataCopiedOrRewritten': False, 'applicationSemanticAndFinalBrowserAcceptance': False, 'fullGoalComplete': False})
    print(json.dumps({'status': 'fourteen_original_apps_on_seventeen_new_native_runtimes'}))


if __name__ == '__main__':
    main()
