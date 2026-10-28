"""Remove only source-bound tool exports from fixed successful publisher stage profiles."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
C = F / 'operator-control'
P = F / 'local-charts-publisher'
ORIGINAL = Path('/mnt/c/Users/james/.codex/local-ci/branconet-charts-local-ci/.tools')
STAGES = {'38436e85d0c34674b0f68f7a3f585e17': '26763df5254b2725f8839fa4400c15c18dc2fe4d',
          '115d2c88828b4e2ab219f08e3d811b7e': '9cf350960cf9af37052a144ac0afb4f950d49766',
          '4eeabacbddb847b39bebabb47e28ef92': '42a60c183af0178d55e1275b07a59b8f08623494',
          '2ca2d94ab9cb4eff9e18c10bc4dfd5b6': '4801e6cf4464b76dbcee5b0b498c5d6124495aad'}
EXPECTED = {'helm': '57ce7fc4ea77b28ee6fa91ae071abcade74d3f524e80c9decff5877a5ac8eda4',
            'kubectl': '65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8',
            'gitleaks': '88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509'}
PREFIX = 'publisher-headroom-'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def ident(path):
    s = path.lstat()
    return {key: getattr(s, 'st_' + key) for key in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def write(name, value):
    path = C / name
    with path.open('x') as out:
        json.dump(value, out, indent=2)
    os.chown(path, 1000, 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--profile', choices=('initial', 'ingenium'), default='initial')
    selection.add_argument('--stage', action='append', help='Exact terminal stage UUID:source SHA; at most eight')
    args = parser.parse_args()
    global STAGES
    prefix = PREFIX
    if args.profile == 'ingenium':
        prefix = 'publisher-headroom-ingenium-'
        STAGES = {'06e055eeb82b4e899bca4ac1d80a183b': 'fa48bcf8032edbe6535fcc55300606243f0a141c',
                  'd59e47ea0028486da396489f8fdd9b5b': '1ec4ba4935ab46a40266269a995ba667a0c3bd93'}
    if args.stage:
        assert 1 <= len(args.stage) <= 8
        assert all(re.fullmatch(r'[a-f0-9]{32}:[a-f0-9]{40}', value) for value in args.stage)
        STAGES = dict(value.split(':', 1) for value in args.stage)
        assert len(STAGES) == len(args.stage)
        token = hashlib.sha256(json.dumps(STAGES, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]
        prefix = 'publisher-headroom-' + token + '-'
        args.profile = 'explicit'
    assert os.geteuid() == 0 and F.is_mount() and P.resolve() == P
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(F), '-o', 'UUID,FSTYPE']))['filesystems'][0]
    assert fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b'
    os.umask(0o077)
    os.environ.update(SYSTEMD_COLORS='0', SYSTEMD_URLIFY='0', COLUMNS='4096')
    locks, targets, protected, stages = [], [], {}, []
    git = '/mnt/c/Program Files/Git/cmd/git.exe'
    repo = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci'
    assert all(sha(ORIGINAL / name) == digest for name, digest in EXPECTED.items())
    try:
        for stage_id, revision in STAGES.items():
            stage = P / ('local-charts-publish-' + stage_id)
            assert stage.resolve() == stage and stage.stat().st_dev == F.stat().st_dev
            lock = (stage / 'operation.lock').open('r+b')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locks.append(lock)
            docs = {phase: json.loads((stage / (phase + '.json')).read_text()) for phase in ('prepare', 'check', 'publish')}
            assert all(d['passed'] is True and d['sourceSHA'] == revision for d in docs.values())
            assert docs['prepare']['binariesSHA256'] == EXPECTED
            assert docs['publish']['publicationPerformed'] is True and docs['publish']['actionsUsed'] is False
            assert docs['publish']['checkReceiptSHA256'] == sha(stage / 'check.json')
            assert docs['check']['prepareReceiptSHA256'] == sha(stage / 'prepare.json')
            assert docs['check']['validationReportSHA256'] == sha(stage / 'source/.validation/validation.json')
            assert subprocess.run([git, '-C', repo, 'merge-base', '--is-ancestor', revision, 'HEAD']).returncode == 0
            raw = subprocess.check_output([git, '-C', repo, 'ls-tree', '-r', '-z', revision])
            manifest = {}
            for line in raw.split(b'\0'):
                if not line:
                    continue
                header, name = line.split(b'\t', 1)
                mode, kind, oid = header.decode().split()
                assert kind == 'blob'
                manifest[name.decode()] = {'mode': mode, 'oid': oid}
            assert manifest == docs['prepare']['manifest']
            source = stage / 'source'
            assert not (source / '.git').exists()
            for name, row in manifest.items():
                path = source / name
                assert path.resolve() == path and path.is_relative_to(source) and path.is_file()
                data = path.read_bytes()
                assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['oid']
            tools = source / '.tools'
            assert tools.resolve() == tools and not tools.is_mount() and set(p.name for p in tools.iterdir()) == set(EXPECTED)
            for name, digest in EXPECTED.items():
                path = tools / name
                before = ident(path)
                assert path.resolve() == path and path.is_relative_to(F) and stat.S_ISREG(before['mode'])
                assert before['uid'] == 1000 and before['nlink'] == 1 and before['dev'] == F.stat().st_dev
                assert sha(path) == digest and path.read_bytes()[:4] == b'\x7fELF'
                targets.append({'relative': str(path.relative_to(F)), 'kind': 'file', 'identity': before, 'sha256': digest})
            targets.append({'relative': str(tools.relative_to(F)), 'kind': 'directory', 'identity': ident(tools)})
            stages.append({'stage': str(stage), 'sourceSHA': revision, 'sourceManifestFiles': len(manifest)})
            for path in stage.rglob('*'):
                if path.is_file() and not path.is_relative_to(tools):
                    assert path.resolve() == path
                    protected[str(path)] = {'identity': ident(path), 'sha256': sha(path)}
        failed = P / 'local-charts-publish-f2085e8a5d0f4098896b6be87e5e3797'
        for path in failed.rglob('*'):
            if path.is_file():
                assert path.resolve() == path
                protected[str(path)] = {'identity': ident(path), 'sha256': sha(path)}
        reference = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation/reference-frozen.py'
        raw = reference.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == '65491a7f5a67b313a527129bc4d7489369ab3f434787f3f366fc28f35e8f6576'
        common = {'__name__': 'publisher_tool_references'}
        exec(compile(raw, '<reviewed-reference-checks>', 'exec'), common)
        common.update(BASE=P, ATTEMPTS=tuple('local-charts-publish-' + n + '/source/.tools' for n in STAGES))
        references = common['idle']()
        plan = {'stageProfile': args.profile, 'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F), 'filesystem': fs,
                'targets': targets, 'stages': stages, 'protected': protected,
                'originalToolsSHA256': EXPECTED, 'references': references,
                'regeneration': 'Recreate exact temporary source/.tools copies from retained publisher .tools originals after pinned SHA checks in a future exclusive stage; never replay publication',
                'protectedFailedAttempt': str(failed), 'sourceExportsAndAllReceiptsRetained': True}
        plan_path = C / (prefix + 'plan-20261027.json')
        if not args.apply:
            assert not plan_path.exists()
            write(plan_path.name, plan)
            print(json.dumps({'status': 'qualified_for_native_handle_check', 'toolFiles': len(STAGES) * 3, 'receiptKey': prefix.removeprefix('publisher-headroom-').removesuffix('-'),
                              'allocatedTargetBytes': sum(r['identity']['blocks'] * 512 for r in targets)}))
            return
        original = json.loads(plan_path.read_text())
        assert all(plan[k] == original[k] for k in ('targets', 'protected', 'stages', 'originalToolsSHA256'))
        proof = json.loads((C / (prefix + 'windows-proof-20261027.json')).read_text())
        assert proof['status'] == 'completed' and proof['handlesClosed'] and len(proof['files']) == len(STAGES) * 3
        assert proof['planSHA256'] == sha(plan_path)
        assert {(r['relative'], r['sha256']) for r in proof['files']} == {(r['relative'], r['sha256']) for r in targets if r['kind'] == 'file'}
        common['idle']()
        for path, value in protected.items():
            assert ident(Path(path)) == value['identity'] and sha(Path(path)) == value['sha256']
        before_space = os.statvfs(F)
        result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'started',
                  'removed': [], 'availableBeforeBytes': before_space.f_bavail * before_space.f_frsize,
                  'sourcesReceiptsAndFailedAttemptPreserved': False, 'publisherChangedOrRetried': False,
                  'windowsRecoveryClaimed': False}
        try:
            for row in targets:
                path = F / row['relative']
                current = ident(path)
                keys = ('dev', 'ino', 'mode', 'uid', 'gid') if row['kind'] == 'directory' else tuple(current)
                assert all(current[k] == row['identity'][k] for k in keys) and path.resolve() == path
                if row['kind'] == 'file':
                    assert sha(path) == row['sha256']
                else:
                    assert not any(path.iterdir())
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    opened = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                    assert (opened.st_dev, opened.st_ino) == (current['dev'], current['ino'])
                    (os.unlink if row['kind'] == 'file' else os.rmdir)(path.name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['removed'].append({'path': str(path), 'allocatedBytes': current['blocks'] * 512})
            assert all(ident(Path(p)) == v['identity'] and sha(Path(p)) == v['sha256'] for p, v in protected.items())
            assert all(sha(ORIGINAL / n) == h for n, h in EXPECTED.items())
            result.update(status='completed', sourcesReceiptsAndFailedAttemptPreserved=True)
        finally:
            space = os.statvfs(F)
            result.update(removedAllocatedBytes=sum(r['allocatedBytes'] for r in result['removed']),
                          availableAfterBytes=space.f_bavail * space.f_frsize,
                          unchangedPublisherFloorBytes=15 * 1024**3 + 256 * 1024**2)
            write(prefix + 'reconciliation-20261027.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'removed'}))
    finally:
        for lock in locks:
            lock.close()


if __name__ == '__main__':
    main()
