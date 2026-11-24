#!/usr/bin/env python3
"""One read-only Linux reference census for three exact superseded binaries."""
import datetime
import errno
import json
import os
from pathlib import Path
import subprocess
import time

CANONICAL = Path('/mnt/c/Users/james/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Veyra-MVP-native')
ALIAS = Path('/mnt/c/Users/james/AppData/Local/Veyra-MVP-native')
SUFFIXES = ['runtime/integrated-mvp/pre-service-update/' + name for name in
            ('veyra-service.exe', 'veyra-service-before-acl.exe', 'Veyra-before-privacy.exe')]
OUTPUT = Path('/home/brajam/.local/state/ingenium-release/skill-zen-fix-1792810845/real-gmail-ui/veyra-phase-1/coordination/integration/native-rollback-linux-references-20261106.json')


def normalized(value):
    return value.replace('\\\\', '/').replace('\\', '/').casefold()


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    assert os.getuid() == 0 and not OUTPUT.exists()
    started = time.monotonic()
    result = {'startedAt': stamp(), 'readOnly': True, 'targets': [], 'processCount': 0,
              'containerCount': 0, 'failures': [], 'workloadsStopped': False, 'filesChanged': False}
    # The first metadata-only attempt stopped at this exact WSL alias ENOENT.
    # Do not retry it or infer an alias inode; Root must reconcile Windows alias
    # metadata. Continue independent canonical-inode and both literal-path checks.
    result['aliasMetadataException'] = {
        'path': str(ALIAS / SUFFIXES[0]), 'observedError': 'FileNotFoundError/ENOENT',
        'retried': False, 'otherAliasInodesChecked': False}
    needles, identities = {}, {}
    for suffix in SUFFIXES:
        paths = [CANONICAL / suffix, ALIAS / suffix]
        rows = []
        info = paths[0].stat()
        rows.append({'path': str(paths[0]), 'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size})
        rows.append({'path': str(paths[1]), 'literalReferencesChecked': True,
                     'inodeNotAssumed': True})
        item = {'canonical': str(paths[0]), 'aliases': rows, 'references': []}
        result['targets'].append(item)
        identities[(rows[0]['device'], rows[0]['inode'])] = item
        variants = []
        for path in paths:
            text = str(path)
            variants.extend([normalized(text), normalized('C:' + text[len('/mnt/c'):])])
        needles[item['canonical']] = variants

    def inspect_text(body, pid, kind):
        value = normalized(body.decode(errors='replace'))
        for item in result['targets']:
            if any(needle in value for needle in needles[item['canonical']]):
                item['references'].append({'pid': pid, 'kind': kind})

    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        if time.monotonic() - started > 45:
            result['failures'].append({'kind': 'bounded-census-deadline'})
            break
        pid = int(process.name)
        result['processCount'] += 1
        try:
            for name in ('cmdline', 'environ', 'maps', 'mountinfo'):
                with (process / name).open('rb') as stream:
                    body = stream.read(8 * 1024**2 + 1)
                if len(body) > 8 * 1024**2:
                    result['failures'].append({'pid': pid, 'kind': name, 'reason': 'bounded-read-exceeded'})
                else:
                    inspect_text(body, pid, name)
            for item in [process / 'cwd', process / 'root', process / 'exe', *list((process / 'fd').iterdir())]:
                try:
                    inspect_text(os.fsencode(os.readlink(item)), pid, item.parent.name + '/' + item.name)
                    info = item.stat()
                    target = identities.get((info.st_dev, info.st_ino))
                    if target is not None:
                        target['references'].append({'pid': pid, 'kind': 'open-inode'})
                except FileNotFoundError:
                    pass
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                result['failures'].append({'pid': pid, 'kind': 'proc-read',
                                           'errno': error.errno, 'type': type(error).__name__})

    try:
        ids = subprocess.check_output(['docker', 'ps', '-aq', '--no-trunc'], timeout=10).decode().split()
        assert len(ids) <= 1000
        if ids:
            rows = subprocess.check_output(['docker', 'inspect', '--format', '{{json .Mounts}}', *ids], timeout=15)
            mounts = [json.loads(line) for line in rows.decode().splitlines()]
            assert len(mounts) == len(ids)
            result['containerCount'] = len(ids)
            for identifier, entries in zip(ids, mounts):
                for mount in entries:
                    source = normalized(mount.get('Source', '')).rstrip('/')
                    if not source:
                        continue
                    for target in result['targets']:
                        if any(needle == source or needle.startswith(source + '/') or source.startswith(needle + '/')
                               for needle in needles[target['canonical']]):
                            target['references'].append({'container': identifier, 'kind': 'configured-mount'})
    except (OSError, subprocess.SubprocessError, ValueError, AssertionError) as error:
        result['failures'].append({'kind': 'docker-reference-read', 'type': type(error).__name__})
    result['finishedAt'] = stamp()
    result['elapsedSeconds'] = round(time.monotonic() - started, 3)
    result['canonicalAndLiteralReferenceChecksPassed'] = not result['failures'] and all(not item['references'] for item in result['targets'])
    result['linuxReferenceCheckPassed'] = False
    result['retirementAuthorized'] = False
    result['remainingAuthority'] = 'Root owns current Windows checks, lossless-delta verification, source preservation and any exact-target retirement.'
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        parent = OUTPUT.parent.stat()
        os.fchown(stream.fileno(), parent.st_uid, parent.st_gid)
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'receipt': str(OUTPUT), **result}))


if __name__ == '__main__':
    main()
