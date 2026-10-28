"""HTTP Echo detach/reattach canary through private charts -> validated -> Flux.

No direct replica patch, controller suspension, image change or forced deletion.
Only the existing release replicaCount is changed, then restored through Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess

import yaml

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-runtime-retirement-20261028'
W = F / 'charts-longhorn-maintenance-20261028'
WIN = '//wsl.localhost/Ubuntu' + str(W)
GIT = '/mnt/c/Program Files/Git/cmd/git.exe'
NAME = 'pvc-9edde4e3-5a0c-4c0c-b317-47b045ee199e'
IMAGE = 'docker.io/longhornio/longhorn-engine:v1.13.0@sha256:b0cc5090889d57705acd69c5106492992e84560170ac3bec4a1cc8dd3fe83ca6'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fingerprint(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()


def save(name, value):
    with (H / name).open('x') as out:
        json.dump(value, out, indent=2)


def git(*args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
        TMPDIR=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'), TEMP=str(F / 'operator-control/tmp'))
    # Windows Git cannot map the Linux UID on this task-owned UNC checkout.
    # Trust only this verified exact root for this invocation, never globally.
    need(W.stat().st_uid == 1000 and W.resolve() == W and (W / '.git').is_file(), 'verified_owned_private_worktree')
    p = subprocess.run([GIT, '-c', 'safe.directory=%(prefix)/' + WIN, '-C', WIN, *args], capture_output=True, timeout=90, env=env)
    need(p.returncode == 0 and len(p.stdout) <= 1024**2 and len(p.stderr) <= 1024**2, 'windows_git_operation_failed_preserve_source')
    return p.stdout.decode().strip()


def remote_main():
    return git('ls-remote', 'origin', 'refs/heads/main').split()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'stop', 'detached', 'resume', 'verify'])
    a = parser.parse_args()
    need(F.is_mount() and os.geteuid() == 1000 and H.resolve() == H and W.resolve() == W, 'original_controller_storage_and_owned_source')
    for p in (F, Path('/mnt/c')):
        fs = os.statvfs(p)
        need(fs.f_bavail * fs.f_frsize >= 16 * 1024**3, 'complete_one_gib_canary_peak_and_original_floors')
    os.umask(0o077)
    repo = Path(__file__).resolve().parents[5]
    source = repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'
    lib = runpy.run_path(str(source), run_name='accepted_engine_read_and_mount_probes')
    get = lib['get']
    lib['controls']()
    release = get('helmreleases.helm.toolkit.fluxcd.io', 'http-echo', 'flux-system')
    dep = get('deployments', 'http-echo', 'http-echo')
    volume = get('volumes.longhorn.io', NAME)
    claim = next(c for c in get('pvc', namespace=None) if c['spec'].get('volumeName') == NAME)
    pv = get('pv', NAME, namespace=None)
    rs, es = lib['associated']('replicas', NAME), lib['associated']('engines', NAME)
    need(not release['spec'].get('suspend') and release['spec']['chart']['spec']['chart'] == './charts/http-echo'
        and release['spec']['chart']['spec']['sourceRef']['name'] == 'branconet-charts', 'original_unsuspended_Flux_delivery_owner')
    need(git('remote', 'get-url', 'origin') == 'https://github.com/jtmb/branconet-charts.git'
        and git('branch', '--show-current') == 'codex/longhorn-runtime-maintenance-20261028', 'owned_isolated_chart_source')
    if a.phase == 'prepare':
        need(not (H / 'http-echo-plan.json').exists() and not git('status', '--porcelain'), 'clean_new_source_and_preserved_prior_receipts')
        need(remote_main() == git('rev-parse', 'HEAD') == 'ba46a95c7eb6b5126aace677780878640240adab', 'reviewed_current_source_base')
        need(dep['spec']['replicas'] == release['spec']['values']['replicaCount'] == 1 and lib['healthy'](volume, es, rs), 'healthy_original_one_replica_canary')
        mounts = lib['pod_mounts'](volume)
        need(len(mounts) == 1 and mounts[0]['imageID'] == 'docker.io/hashicorp/http-echo@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186', 'original_exact_distroless_canary')
        # Prior accepted engine qualification includes real reads of this same
        # unchanged Pod/mount. Resume verification performs a fresh real read.
        old = json.loads((F / 'platform-upstream-review-20261027/longhorn-engine-upgrade-20261028/plan-v3.json').read_text())
        record = next(r for r in old['records'] if r['name'] == NAME)
        need(mounts == record['mounts'] and json.loads((F / 'platform-upstream-review-20261027/longhorn-engine-upgrade-20261028' / (NAME + '-result.json')).read_text())['status'] == 'completed', 'same_previously_read_original_mount')
        file = W / 'flux/releases/http-echo.yaml'
        save('http-echo-plan.json', {'sourceSHA256': sha(Path(__file__)), 'engineProbeSourceSHA256': sha(source),
            'baseSHA': git('rev-parse', 'HEAD'), 'releaseUID': release['metadata']['uid'], 'deploymentUID': dep['metadata']['uid'],
            'templateSHA256': fingerprint(dep['spec']['template']), 'claimUID': claim['metadata']['uid'],
            'claimSpecSHA256': fingerprint(claim['spec']), 'pvUID': pv['metadata']['uid'], 'pvSpecSHA256': fingerprint(pv['spec']),
            'volumeUID': volume['metadata']['uid'], 'dataDirectories': lib['data_directories'](rs), 'originalMounts': mounts,
            'releaseFileSHA256': sha(file), 'releaseDocument': yaml.safe_load(file.read_bytes()),
            'originalInstanceManager': es[0]['status'].get('instanceManagerName'), 'originalReplicaCount': 1})
        print(json.dumps({'status': 'prepared', 'canary': 'http-echo', 'directClusterWrites': False}))
        return
    plan = json.loads((H / 'http-echo-plan.json').read_text())
    need(sha(Path(__file__)) == plan['sourceSHA256'] and sha(source) == plan['engineProbeSourceSHA256'], 'unchanged_prepared_worker_sources')
    need(volume['metadata']['uid'] == plan['volumeUID'] and claim['metadata']['uid'] == plan['claimUID']
        and fingerprint(claim['spec']) == plan['claimSpecSHA256'] and pv['metadata']['uid'] == plan['pvUID']
        and fingerprint(pv['spec']) == plan['pvSpecSHA256'] and dep['metadata']['uid'] == plan['deploymentUID']
        and fingerprint(dep['spec']['template']) == plan['templateSHA256'] and release['metadata']['uid'] == plan['releaseUID'], 'all_original_data_owner_and_application_definitions_preserved')
    if a.phase in ('stop', 'resume'):
        to = 0 if a.phase == 'stop' else 1
        previous = 1 - to
        need(not (H / ('http-echo-' + a.phase + '-intent.json')).exists(), 'no_blind_source_submission_replay')
        need(not git('status', '--porcelain'), 'owned_source_must_be_clean')
        current_main = remote_main()
        if current_main != git('rev-parse', 'HEAD'):
            git('fetch', 'origin', current_main)
            git('merge', '--ff-only', current_main)
        file = W / 'flux/releases/http-echo.yaml'
        document = yaml.safe_load(file.read_bytes())
        expected = json.loads(json.dumps(plan['releaseDocument']))
        expected['spec']['values']['replicaCount'] = previous
        need(document == expected and document['spec'].get('suspend') is False, 'only_reviewed_original_canary_replica_field_can_change')
        if a.phase == 'resume':
            need((H / 'http-echo-detached.json').exists() and volume['status']['state'] == 'detached', 'original_volume_deliberately_detached_first')
        else:
            need(lib['healthy'](volume, es, rs), 'healthy_canary_before_stop')
        raw = file.read_bytes()
        old, new = ('    replicaCount: ' + str(previous)).encode(), ('    replicaCount: ' + str(to)).encode()
        need(raw.count(old) == 1, 'one_exact_replica_value')
        file.write_bytes(raw.replace(old, new))
        doc = W / 'docs/LONGHORN-RUNTIME-MAINTENANCE-20261028.md'
        text = ('# Longhorn runtime maintenance\n\nHTTP Echo is the first serial detach/reattach canary after the supported V1\n'
            'engine upgrade. Only its existing Flux release replicaCount changes\n'
            'temporarily to zero and then returns to one through validated charts.\n'
            'Images, resource settings, native Secret references, claims, data and\n'
            'all release holds remain. No direct scale patch or forced Pod deletion.\n\n'
            'Current desired HTTP Echo replicas: ' + str(to) + '.\n')
        doc.write_text(text)
        need(set(git('diff', '--name-only').splitlines()) <= {'flux/releases/http-echo.yaml', 'docs/LONGHORN-RUNTIME-MAINTENANCE-20261028.md'}, 'exact_source_change_scope')
        git('add', '--', 'flux/releases/http-echo.yaml', 'docs/LONGHORN-RUNTIME-MAINTENANCE-20261028.md')
        git('diff', '--cached', '--check')
        git('commit', '-m', ('Stop' if to == 0 else 'Restore') + ' HTTP Echo for Longhorn runtime maintenance')
        commit = git('rev-parse', 'HEAD')
        save('http-echo-' + a.phase + '-intent.json', {'sourceSHA': commit, 'previousMain': current_main,
            'replicaCount': to, 'existingLocalCIAndFluxRequired': True, 'directClusterWrite': False})
        git('push', 'origin', 'HEAD:refs/heads/main')
        need(remote_main() == commit, 'exact_new_main_observed')
        save('http-echo-' + a.phase + '-pushed.json', {'sourceSHA': commit, 'replicaCount': to})
        print(json.dumps({'status': 'pushed_wait_for_existing_local_validation_and_Flux', 'phase': a.phase, 'sourceSHA': commit}))
        return
    if a.phase == 'detached':
        need(dep['spec']['replicas'] == 0 and release['spec']['values']['replicaCount'] == 0
            and any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status']['conditions']), 'Flux_applied_and_accepted_canary_stop')
        need(volume['status']['state'] == 'detached' and all(r['status']['currentState'] == 'stopped' for r in rs)
            and all(e['status']['currentState'] == 'stopped' for e in es)
            and not get('volumeattachments.longhorn.io', NAME)['spec'].get('attachmentTickets')
            and not lib['pod_mounts'](volume), 'native_volume_fully_detached_without_forcing')
        need(lib['data_directories'](rs) == [tuple(r) for r in plan['dataDirectories']], 'same_retained_replica_data_directories')
        save('http-echo-detached.json', {'status': 'Flux_stop_and_native_detach_observed', 'volumeUID': volume['metadata']['uid'],
            'dataDirectoriesPreserved': True, 'releaseUID': release['metadata']['uid']})
        print(json.dumps({'status': 'Flux_stop_and_native_detach_observed'}))
        return
    need(dep['spec']['replicas'] == release['spec']['values']['replicaCount'] == 1
        and dep['status'].get('availableReplicas') == 1 and lib['healthy'](volume, es, rs), 'Flux_restored_one_healthy_instance_and_two_actual_RW_replicas')
    im = get('instancemanagers.longhorn.io', es[0]['status']['instanceManagerName'])
    need(':v1.13.0@sha256:' in im['spec']['image'] and es[0]['status']['currentImage'] == IMAGE, 'actual_engine_now_managed_by_the_new_instance_manager')
    mounts = lib['pod_mounts'](volume)
    need(len(mounts) == 1 and mounts[0]['podUID'] != plan['originalMounts'][0]['podUID']
        and mounts[0]['imageID'] == plan['originalMounts'][0]['imageID'] and mounts[0]['restartCount'] == 0,
        'new_healthy_pod_same_original_application_image')
    lib['probe'](mounts)
    need(lib['data_directories'](rs) == [tuple(r) for r in plan['dataDirectories']], 'same_original_data_directories_after_restart')
    save('http-echo-acceptance.json', {'status': 'same_data_and_application_on_new_runtime', 'volumeUID': volume['metadata']['uid'],
        'deploymentUID': dep['metadata']['uid'], 'claimUID': claim['metadata']['uid'], 'newMounts': mounts,
        'instanceManager': im['metadata']['name'], 'instanceManagerImage': im['spec']['image'],
        'originalDataAndTemplatePreserved': True, 'mountedDataReadPassed': True, 'twoActualRWReplicas': True,
        'sourceSHA': json.loads((H / 'http-echo-resume-pushed.json').read_text())['sourceSHA'], 'fullGoalComplete': False})
    print(json.dumps({'status': 'same_data_and_application_on_new_runtime', 'canary': 'http-echo'}))


if __name__ == '__main__':
    main()
