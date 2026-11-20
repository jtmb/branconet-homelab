#!/usr/bin/env python3
"""Adopt ONLY the reviewed Dockerfile/doc delta in the qualified context.

No frontend, installer, application RUN, compiler or image job is executed.
Original projection and OCI observations remain attributed to their actual run.
"""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess


def need(value, message):
    if not value:
        raise RuntimeError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--extension', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--staged-tempdir-retry', action='store_true')
    modes.add_argument('--staged-installation-config', action='store_true')
    args = parser.parse_args()
    need(os.getuid() == 0, 'Existing exact WORK operator ownership is required')
    path = Path(__file__).with_name('veyra-linux-build.py')
    spec = importlib.util.spec_from_file_location('original_veyra_operator', path)
    o = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(o)
    staged = args.staged_tempdir_retry or args.staged_installation_config
    if staged:
        o.WORK, o.EXECUTOR = o.WORK.with_name('n'), o.OWNER
    need(o.WORK.resolve() == o.WORK, 'Original canonical WORK required')
    lock = (o.WORK / 'executor.lock').open('r+b')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        previous_candidate = '-tempdir' if args.staged_installation_config else ''
        prepared_suffix = '-prepared' if previous_candidate else ''
        receipt = json.loads((o.WORK / ('result' + previous_candidate + prepared_suffix + '.json')).read_text())
        owner = json.loads((o.WORK / ('owner' + previous_candidate + '.json')).read_text())
        previous = (receipt['sourceTransitions'][-1]['currentSource'] if receipt.get('sourceTransitions')
                    else receipt['preflight']['source'])
        projection = receipt['sourceContextProjection']
        need(owner['owner'] == o.OWNER and owner['executor'] == o.EXECUTOR and
             owner['revision'] == previous['revision'] and owner['sourceSha256'] == previous['sourceSha256'],
             'Original owner/source binding differs')
        if args.staged_tempdir_retry:
            failed_path = o.WORK / 'result-retry-controller.json'
            failed = json.loads(failed_path.read_text())
            log = o.WORK / 'rootfs-budget-run-15-controller.log'
            need(failed['sourceSha256'] == previous['sourceSha256'] and failed.get('finishedAt') and
                 failed['streamedBuild']['compiledStages'] == [] and failed['streamedBuild']['state'] == 'building-budget' and
                 failed.get('failureCleanup', {}).get('finishedAt') and not failed['failureCleanup'].get('cleanupSafetyFailure') and
                 b"mktemp: failed to create file via template '/tmp/veyra-build/tmp/" in log.read_bytes() and
                 not (o.WORK / 'rootfs-controller').exists() and not (o.WORK / 'owner-tempdir.json').exists() and
                 not (o.WORK / 'result-tempdir-prepared.json').exists(),
                 'Exact stopped dependency failure and fresh receipt destinations required')
            receipt = {key: failed[key] for key in ('owner', 'executor', 'root', 'revision', 'sourceSha256',
                       'regeneration', 'sourceContextProjection', 'ociIsolationQualification', 'preservedPreparation',
                       'cleanupPasses', 'stages', 'artifacts', 'diagnosticsRootIdentity', 'protectedBaseLayers')}
            receipt.update(state='exact-source-context-prepared-not-full-build', attempt='tempdir',
                           failedDependencyBuild={'path': str(failed_path), 'sha256': o.sha(failed_path),
                                                  'logSha256': o.sha(log)})
        elif args.staged_installation_config:
            need(receipt.get('state') == 'exact-source-context-prepared-not-full-build' and
                 'streamedBuild' not in receipt and not (o.WORK / 'result-tempdir.json').exists() and
                 not (o.WORK / 'rootfs-controller').exists() and
                 not (o.WORK / 'owner-installation-config.json').exists() and
                 not (o.WORK / 'result-installation-config-prepared.json').exists(),
                 'The previous corrected preparation must remain unbuilt')
        else:
            need('streamedBuild' not in receipt and not (o.WORK / 'rootfs').exists() and
                 not (o.WORK / 'qualification-rootfs').exists(), 'An actual producer needs reconciliation')
        need(projection['completed'] and projection['originalDockerignoreFrontend'] and
             projection['clientTerminal'] and projection['daemonTerminal'] and
             projection['originalExitCode'] == 0 and projection['sourceSha256'] == previous['sourceSha256'],
             'Actual original source projection must be complete')
        source, _, report = o.inspect(args.revision, args.extension)
        def git(*parts):
            return subprocess.check_output(['git', '-C', str(o.APP), *parts],
                user=o.APP.stat().st_uid, group=o.APP.stat().st_gid, extra_groups=(),
                env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
        old_tree = []
        for row in git('ls-tree', '-rz', '--full-tree', previous['revision']).split(b'\0'):
            if not row:
                continue
            header, name = row.split(b'\t', 1)
            mode, kind, blob = header.decode().split()
            relative = name.decode()
            need(kind == 'blob' and mode in {'100644', '100755'} and
                 not relative.startswith('/') and '..' not in Path(relative).parts,
                 'Unsupported original tracked source entry')
            old_tree.append((relative, mode, blob))
        current = {row['path']: row for row in source['files']}
        need([x[0] for x in old_tree] == [x['path'] for x in source['files']] and
             all(mode == current[name]['mode'] for name, mode, _ in old_tree),
             'Tracked path or mode selection changed; original frontend qualification cannot be reused')
        changed = [name for name, _, blob in old_tree if blob != current[name]['gitBlob']]
        allowed = {'Dockerfile', 'docs/operations/veyra-mvp.md',
                   'tools/veyra-release/linux-build.lock.json',
                   'tools/veyra-release/reproducible-linux.mjs',
                   'tools/veyra-release/verify-linux-build.mjs'}
        if args.staged_installation_config:
            allowed = {'services/ingenium-api/lib/routes/configs.ts',
                       'services/ingenium-dashboard/src/lib/api.ts',
                       'services/ingenium-dashboard/src/app/components/DashboardShell.tsx',
                       'services/ingenium-dashboard/src/app/config/page.tsx',
                       'services/ingenium-dashboard/src/app/components/settings/panels/ConfigPanel.tsx'}
            need(set(changed) == allowed, 'Exact installation configuration integration required')
        need(bool(changed) and set(changed) <= allowed,
             'Only the reviewed recipe/document/browser selection bytes may change')
        if args.staged_tempdir_retry:
            need(changed == ['Dockerfile'], 'Only the dependency temporary directory fix may change')
            original = git('cat-file', 'blob', next(blob for name, _, blob in old_tree if name == 'Dockerfile'))
            anchor = b'RUN npm ci --ignore-scripts --workspaces --include-workspace-root'
            addition = b'RUN install -d -m 0700 "$TMPDIR" && ' + bytes((92, 10)) + b'    npm ci --ignore-scripts --workspaces --include-workspace-root'
            need(original.count(anchor) == 1 and (o.APP / 'Dockerfile').read_bytes() == original.replace(anchor, addition),
                 'Dockerfile delta differs from the observed dependency temporary-directory fix')
        lock_name = 'tools/veyra-release/linux-build.lock.json'
        if lock_name in changed:
            old_blob = next(blob for name, _, blob in old_tree if name == lock_name)
            old_lock, new_lock = json.loads(git('cat-file', 'blob', old_blob)), json.loads((o.APP / lock_name).read_text())
            need(old_lock['browser']['artifacts'] == new_lock['browser']['artifacts'] and
                 all(old_lock[key] == new_lock[key] for key in ('base', 'apt', 'npm', 'rust', 'swarm', 'voice')),
                 'Original pinned browser/base/package/ABI inputs changed')
            need(new_lock['browser'].get('runtimeArtifacts') == ['chromium', 'ffmpeg'],
                 'Only the reviewed full-Chromium runtime selection is qualified')
        context = o.WORK / 'docker-context'
        need(context.resolve() == context and projection['path'] == str(context), 'Original context identity differs')
        included = set(projection['includedPaths'])
        omitted = set(projection['omittedPaths'])
        need(included.isdisjoint(omitted) and included | omitted == set(current) and
             set(changed) <= included, 'Original canonical path projection differs')
        old_rows = []
        for name, mode, blob in old_tree:
            p = context / name
            if name in included:
                need(p.parent.resolve().is_relative_to(context) and not p.is_symlink() and p.is_file(),
                     'Existing filtered source alias or missing input')
                body = p.read_bytes()
                need(stat.S_IMODE(p.stat().st_mode) == int(mode, 8) & 0o777,
                     'Existing filtered executable mode differs')
            else:
                body = git('cat-file', 'blob', blob)
            need(hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest() == blob,
                 'Original filtered bytes no longer match the actual old Git object')
            old_rows.append({'path': name, 'mode': mode, 'gitBlob': blob,
                             'bytes': len(body), 'sha256': digest(body)})
        need(digest(encoded(old_rows)) == previous['sourceSha256'], 'Original canonical source authority differs')
        old_by_path = {row['path']: row for row in old_rows}
        for name in ('.dockerignore', 'Dockerfile.dockerignore'):
            need((name in current) == (name in old_by_path) and
                 (name not in current or current[name]['gitBlob'] == old_by_path[name]['gitBlob']),
                 'Dockerignore selection contract changed')
        need(o.sha(context / '.dockerignore') == projection['rawDockerignoreSha256'] and
             not any(line.lstrip().lower().startswith('# syntax=') for line in
                     (o.APP / 'Dockerfile').read_text().splitlines()), 'Original frontend/ignore contract changed')
        actual_paths = []
        for directory, names, files in os.walk(context, followlinks=False):
            need(not any((Path(directory) / name).is_symlink() for name in names), 'Filtered directory alias')
            actual_paths.extend((Path(directory) / name).relative_to(context).as_posix() for name in files)
        need(set(actual_paths) == included, 'Additional or missing filtered source path')
        coordination = o.PHASE / 'coordination/integration'
        key = 'source-context-delta-' + args.revision[:12]
        intent_path, result_path = coordination / (key + '-intent.json'), coordination / (key + '-result.json')
        uid, gid = coordination.stat().st_uid, coordination.stat().st_gid
        def publish(p, value):
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                os.fchown(stream.fileno(), uid, gid)
                json.dump(value, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        event = {'at': o.now(), 'originalOwner': owner, 'previousSource': previous,
                 'currentSource': report['source'], 'changedPaths': changed,
                 'changes': [{'old': old_by_path[name], 'new': current[name]} for name in changed],
                 'includedPathsSha256': digest(encoded(projection['includedPaths'])),
                 'originalProjectionSha256': digest(encoded(projection)),
                 'originalFrontendReplayed': False, 'compilerStarted': False}
        publish(intent_path, event)
        for name in changed:
            target, canonical = context / name, o.APP / name
            need(o.sha(target) == old_by_path[name]['sha256'], 'Source changed after original qualification')
            body, before = canonical.read_bytes(), target.stat()
            need(digest(body) == current[name]['sha256'], 'New canonical bytes changed')
            temporary = target.with_name('.veyra-delta-' + target.name)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                os.fchmod(stream.fileno(), int(current[name]['mode'], 8) & 0o777)
                os.fchown(stream.fileno(), before.st_uid, before.st_gid)
                os.fsync(stream.fileno())
            times = canonical.stat()
            os.utime(temporary, ns=(times.st_atime_ns, times.st_mtime_ns))
            os.replace(temporary, target)
        for name in included:
            p = context / name
            need(p.is_file() and not p.is_symlink() and o.sha(p) == current[name]['sha256'] and
                 stat.S_IMODE(p.stat().st_mode) == int(current[name]['mode'], 8) & 0o777,
                 'Complete current filtered projection differs')
        final, _, _ = o.inspect(args.revision, args.extension)
        need(final['sourceSha256'] == source['sourceSha256'], 'Current canonical source changed during delta')
        updated = copy.deepcopy(projection)
        updated.update(sourceSha256=source['sourceSha256'],
                       originalFrontendSourceSha256=projection.get('originalFrontendSourceSha256', previous['sourceSha256']),
                       currentProjectionMethod='canonical-byte-delta-with-unchanged-original-selection',
                       derivedContextDelta=str(result_path))
        receipt.setdefault('sourceTransitions', []).append(event)
        receipt.update(revision=args.revision, sourceSha256=source['sourceSha256'], sourceContextProjection=updated)
        owner = {**owner, 'revision': args.revision, 'sourceSha256': source['sourceSha256'],
                 'derivedSourceReceipt': str(result_path)}
        if staged:
            receipt['preflight'] = report
            suffix = 'installation-config' if args.staged_installation_config else 'tempdir'
            for filename, value in (('owner-' + suffix + '.json', owner),
                                    ('result-' + suffix + '-prepared.json', receipt)):
                with (o.WORK / filename).open('x') as stream:
                    json.dump(value, stream, indent=2)
                    stream.write('\n')
                (o.WORK / filename).chmod(0o600)
        else:
            o.write_json(o.WORK / 'owner.json', owner)
            o.write_json(o.WORK / 'result.json', receipt)
        summary = {**event, 'completedAt': o.now(), 'fullCurrentProjectionVerified': True,
                   'projection': updated, 'ociQualification': receipt['ociIsolationQualification'],
                   'fullCompilerOrImageAccepted': False}
        publish(result_path, summary)
        print(json.dumps({'result': str(result_path), 'source': report['source'],
                          'included': len(included), 'omitted': sorted(omitted),
                          'changed': changed, 'fullCurrentProjectionVerified': True,
                          'frontendOrProbeReplayed': False, 'compilerStarted': False}))
    finally:
        lock.close()


if __name__ == '__main__':
    main()
