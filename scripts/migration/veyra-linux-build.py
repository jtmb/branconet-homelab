#!/usr/bin/env python3
"""Build the current Veyra Dockerfile in the existing isolated WSL task root.

inspect is read-only. run requires the coordinator's fresh serial-platform lease
and measured storage admission; it neither publishes nor changes an application.
"""
import argparse
import collections
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tarfile
import time
import tomllib
import urllib.request

ROOT = Path('/home/brajam/.local/state/ingenium-release/skill-zen-fix-1792810845')
PHASE = ROOT / 'real-gmail-ui/veyra-phase-1'
APP = PHASE.parent / 'prd-ui-fixes'
WORK = ROOT / 'b/current'
RESULT_FILENAME = 'result.json'
OWNER_FILENAME = 'owner.json'
PRODUCER_ROOT_NAME = 'rootfs'
TOOLS = PHASE / 'linux-image/tools'
OWNER = '01a188fc-d3ed-7dc2-ab95-e0eed8a793ec'
EXECUTOR = '01a18518-24e7-7ce3-b620-f9ca775bfd1c'
NODE = Path('/home/brajam/.nvm/versions/node/v22.23.1/bin/node')
WINPY = '/mnt/c/Users/james/AppData/Local/Programs/Python/Python312/python.exe'
GIB = 1024 ** 3
# Human-authorized temporary ceiling for this existing paired Veyra workflow,
# November 6, 2026. Other tasks retain their own original limits.
CEILING, FLOOR = 23 * GIB, 15 * GIB
ASSET = 'buildkit-v0.34.1.linux-amd64.tar.gz'
ASSET_BYTES = 92218962
ASSET_SHA = 'a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b'
BINARIES = {
    'buildctl': (34819330, '8e64362dceba989827b23af567915feda10426ebd40611772318662e33bf2bfd'),
    'buildkit-runc': (13517072, '2f5ed1fb8b0d57bf8442767d572229cb0ff29bdcfe279c6a51535a6a84f85eff'),
    'buildkitd': (80918593, 'ca3c5d4fe1defc5df56631e179824f17ddd555f1fcf5057d14dfb87496baa8c3'),
}


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def command(args, **kwargs):
    if args[0] == NODE:
        # Root owns the isolated executor, not the source checkout. Inventory as
        # its actual owner; never add safe.directory to evade an ownership error.
        kwargs.setdefault('env', {**os.environ, 'NODE_DISABLE_COMPILE_CACHE': '1', 'GIT_OPTIONAL_LOCKS': '0'})
        if os.getuid() == 0:
            kwargs.setdefault('user', APP.stat().st_uid)
            kwargs.setdefault('group', APP.stat().st_gid)
            kwargs.setdefault('extra_groups', ())
    return subprocess.run([str(v) for v in args], check=True, capture_output=True,
                          timeout=kwargs.pop('timeout', 120), **kwargs).stdout


def json_command(args, **kwargs):
    return json.loads(command(args, **kwargs))


def write_json(path, data):
    # Only this invocation's exclusively-created private output files are updated.
    if path == WORK / 'result.json':
        path = WORK / RESULT_FILENAME
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def allocated(root, excluded=()):
    seen, total = set(), 0
    def fail(error):
        raise error
    for directory, names, files in os.walk(root, followlinks=False, onerror=fail):
        for path in [Path(directory), *(Path(directory) / n for n in names + files)]:
            info = path.lstat()
            key = (info.st_dev, info.st_ino)
            if key not in seen and key not in excluded:
                seen.add(key)
                total += info.st_blocks * 512
    return total


def task_allocated():
    # The existing approved native guard uses this SAME aggregate authority.
    # It counts private recovery/old-builder directories without opening their
    # contents or changing them. Per-file inspection is limited to our new work.
    argv = ['/usr/bin/du', '-x', '-s', '-B1', '--', str(ROOT)]
    if os.getuid() != 0:
        argv = ['/mnt/c/Windows/System32/wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--exec', *argv]
    return int(command(argv).split(None, 1)[0])


def inspect(revision, extension):
    need(ROOT.resolve() == ROOT and APP.resolve() == APP, 'Canonical existing roots required')
    owner = json.loads((PHASE / 'output-ownership.json').read_text())
    need(owner['activeOwner']['threadId'] == OWNER, 'Coordinator ownership changed')
    source = json_command([NODE, APP / 'tools/veyra-release/source-manifest.mjs', APP, revision])
    extension = extension.absolute()
    need(extension.resolve() == extension and extension.is_relative_to(ROOT), 'Existing confined extension source required')
    ext = json_command([NODE, APP / 'services/ingenium-api/scripts/browser-extension-bundle.mjs', '--source', extension])
    npm = json.loads((APP / 'package-lock.json').read_text())
    cargo = {}
    for name in ['services/veyra-api/Cargo.lock', 'services/veyra-swarm/Cargo.lock']:
        lock = tomllib.loads((APP / name).read_text())
        cargo[name] = {'sha256': sha(APP / name), 'packages': len(lock['package']),
                       'registryPackages': sum('checksum' in item for item in lock['package'])}
    lock = json.loads((APP / 'tools/veyra-release/linux-build.lock.json').read_text())
    return source, ext, {'at': now(), 'source': {k: source[k] for k in
            ['revision', 'tree', 'sourceDateEpoch', 'sourceSha256', 'fileCount', 'sourceBytes']},
        'extension': ext, 'extensionDirectory': str(extension), 'cargo': cargo,
        'npmLockSha256': sha(APP / 'package-lock.json'), 'npmPackages': len(npm['packages']),
        'linuxBuildLockSha256': sha(APP / 'tools/veyra-release/linux-build.lock.json'),
        'nodeBase': lock['base']['reference'], 'rustBase': lock['rust']['reference'],
        'serialExportTargetsInstalled': all((' AS ' + name) in (APP / 'Dockerfile').read_text() for name in ['veyra-budget-artifact', 'veyra-swarm-artifact', 'veyra-rust-artifact', 'veyra-node-artifact']),
        'buildkitDownloadBytes': ASSET_BYTES,
        'buildkitExtractedBytes': sum(v[0] for v in BINARIES.values()),
        'rootIdentity': {'device': ROOT.stat().st_dev, 'inode': ROOT.stat().st_ino, 'uid': ROOT.stat().st_uid},
        'linuxAllocatedBytes': task_allocated(), 'destinationFreeBytes': shutil.disk_usage(ROOT).free,
        'windowsFreeBytes': int(command([WINPY, '-I', '-B', '-c', "import shutil;print(shutil.disk_usage('C:/').free)"])),
        'noBuildDownloadOrInstallStarted': True}


def admit(lease_path, report, *, retire_before_image=0):
    need(lease_path.resolve() == lease_path and lease_path.is_relative_to(ROOT), 'Confined coordinator lease required')
    lease = json.loads(lease_path.read_text())
    need(lease['owner'] == OWNER and lease['platform'] == 'linux' and lease['exclusive'] is True,
         'Coordinator must release the exclusive Linux platform lease')
    age = time.time() - dt.datetime.fromisoformat(lease['at'].replace('Z', '+00:00')).timestamp()
    need(0 <= age < 180, 'Fresh serial-platform/storage admission required')
    need(lease['nativeStageActive'] is False, 'Windows and Linux builds must run serially')
    need(type(lease.get('combinedTaskCeilingBytes')) is int and
         lease['combinedTaskCeilingBytes'] == CEILING and
         type(lease.get('minimumFreeBytes')) is int and lease['minimumFreeBytes'] == FLOOR,
         'Fresh lease must bind the authorized temporary 23 GiB task ceiling and unchanged 15 GiB reserves')
    need(lease['sourceRevision'] == report['source']['revision'] and
         lease['sourceSha256'] == report['source']['sourceSha256'], 'Lease source identity differs')
    need(lease['extensionSha256'] == report['extension']['sourceSha256'], 'Lease extension identity differs')
    need(type(lease['nativeBudgetBytes']) is int and lease['nativeBudgetBytes'] > 0 and
         type(lease['growthBytes']) is int and lease['growthBytes'] > 0,
         'Measured native budget and full Linux peak required')
    # Admit MAX simultaneous phase, never the sum of compiler stores that will
    # be verified inactive and removed between stages. Exports remain counted.
    required = {'tools', 'context', 'preservedExports', 'contentAndSnapshots',
                'compilerWorkingSets', 'outputCoexistence', 'margin'}
    phases = lease['growthPhases']
    need(set(phases) == {'tools', 'budget', 'swarm', 'rust', 'node', 'image'}, 'Every serial phase needs complete peak accounting')
    for name, parts in phases.items():
        need(set(parts) == required and all(type(v) is int and v >= 0 for v in parts.values()), 'Incomplete phase peak: ' + name)
        need(parts['margin'] > 0 and parts['tools'] > 0, 'Tool/margin allowance omitted: ' + name)
        if name != 'tools':
            need(parts['context'] >= report['source']['sourceBytes'] + sum(f['bytes'] for f in report['extension']['files']), 'Contexts omitted: ' + name)
    need(max(sum(parts.values()) for parts in phases.values()) == lease['growthBytes'], 'Growth must equal the maximum complete simultaneous phase')
    need(phases['tools']['tools'] >= ASSET_BYTES + sum(v[0] for v in BINARIES.values()), 'Tool acquisition/extraction peak omitted')
    need(type(retire_before_image) is int and 0 <= retire_before_image <= report['linuxAllocatedBytes'],
         'Invalid measured continuation allocation')
    # Before image assembly the verified retained seed, executable, budget
    # export and already-counted prepared contexts are all retired. Budget earlier phases with their full original
    # growth plus everything currently on disk. C: receives no credit.
    paired_growth = max(sum(parts.values()) - (retire_before_image if name == 'image' else 0)
                        for name, parts in phases.items())
    need(lease['nativeBudgetBytes'] + report['linuxAllocatedBytes'] + paired_growth <= CEILING,
         'Complete paired task peak exceeds authorized temporary 23 GiB; retain current outputs and report exact shortfall')
    need(report['windowsFreeBytes'] - lease['growthBytes'] >= FLOOR, 'C: cannot retain 15 GiB through complete peak')
    need(report['destinationFreeBytes'] - lease['growthBytes'] >= FLOOR, 'Destination cannot retain 15 GiB through complete peak')
    if retire_before_image:
        lease['continuationAllocation'] = {'allocatedBytesRetiredBeforeImage': retire_before_image,
                                          'measuredLinuxAllocatedBytes': report['linuxAllocatedBytes'],
                                          'maximumAdditionalPairedBytes': paired_growth}
    return lease


def tool_inputs(receipt, retain_runtime=False):
    bin_dir = TOOLS / 'bin'
    runtime = bin_dir / 'buildkit-runc'
    if retain_runtime:
        need(TOOLS.resolve() == TOOLS and bin_dir.resolve() == bin_dir and
             TOOLS.stat().st_uid == 0 and bin_dir.stat().st_uid == 0 and
             set(TOOLS.iterdir()) == {bin_dir} and set(bin_dir.iterdir()) == {runtime},
             'Only the original isolated OCI runtime may precede tool restoration')
        info = runtime.lstat()
        size, digest = BINARIES['buildkit-runc']
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
             info.st_size == size and sha(runtime) == digest,
             'Retained OCI runtime no longer matches the original pinned tool')
    else:
        need(not TOOLS.exists() and not TOOLS.is_symlink(),
             'Existing tools require reconciliation; never replace them')
        TOOLS.mkdir(mode=0o700)
    archive = TOOLS / ASSET
    url = 'https://github.com/moby/buildkit/releases/download/v0.34.1/' + ASSET
    received, h = 0, hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as stream, archive.open('xb') as output:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            received += len(chunk)
            need(received <= ASSET_BYTES, 'Pinned tool archive exceeds size')
            output.write(chunk)
            h.update(chunk)
    need(received == ASSET_BYTES and h.hexdigest() == ASSET_SHA, 'Pinned BuildKit archive integrity failed')
    receipt['toolArchiveVerified'] = {'path': str(archive), 'bytes': received, 'sha256': h.hexdigest()}
    write_json(WORK / 'result.json', receipt)
    if not retain_runtime:
        bin_dir.mkdir(mode=0o700)
    selected = set()
    with tarfile.open(archive, 'r:gz') as bundle:
        for item in bundle:
            if item.name not in {'bin/' + name for name in BINARIES}:
                continue
            name = item.name.split('/')[1]
            need(name not in selected and item.isfile() and item.size == BINARIES[name][0], 'Unexpected selected tool member')
            target = TOOLS / item.name
            if retain_runtime and target == runtime:
                selected.add(name)
                continue
            with bundle.extractfile(item) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            need(sha(target) == BINARIES[name][1], 'Pinned tool hash differs')
            target.chmod(0o755)
            selected.add(name)
    need(selected == set(BINARIES), 'Missing pinned tools')
    # The extraction/archive streams are closed; verify all reference and
    # preservation checks before retiring even this short-lived derivative.
    retire_targets(receipt, [archive], 'verified-tool-archive')
    receipt['toolArchiveRemoved'] = {'path': str(archive), 'removed': not archive.exists()}


def contexts(source, extension, ext):
    context, named = WORK / 'context', WORK / 'browser-extension'
    context.mkdir(mode=0o700)
    named.mkdir(mode=0o700)
    for item in source['files']:
        original = APP / item['path']
        need(sha(original) == item['sha256'], 'Committed source changed: ' + item['path'])
        target = context / item['path']
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with original.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
        target.chmod(0o755 if item['mode'] == '100755' else 0o644)
        need(sha(target) == item['sha256'], 'Source context differs: ' + item['path'])
    for item in ext['files']:
        original, target = extension / item['name'], named / item['name']
        need(sha(original) == item['sha256'], 'Extension source changed')
        with original.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        target.chmod(0o444)
        need(sha(target) == item['sha256'], 'Extension context differs')
    return context, named


def process_status(pid):
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(') ', 1)[1].split()
    return fields[0], fields[19]


def birth(pid):
    return process_status(pid)[1]


def artifact_identity(root):
    need(root.resolve() == root and root.is_relative_to(WORK / 'handoffs'), 'Artifact root escaped')
    rows, logical, physical, seen, named = [], 0, root.stat().st_blocks * 512, set(), set()
    def fail(error):
        raise error
    for directory, names, files in os.walk(root, followlinks=False, onerror=fail):
        for path in [Path(directory), *(Path(directory) / n for n in names + files)]:
            relative = str(path.relative_to(root))
            if relative == '.' or relative in named:
                continue
            named.add(relative)
            info = path.lstat()
            key = (info.st_dev, info.st_ino)
            if key not in seen:
                physical += info.st_blocks * 512
                seen.add(key)
            row = {'path': relative, 'mode': info.st_mode & 0o7777, 'uid': info.st_uid, 'gid': info.st_gid}
            if stat.S_ISREG(info.st_mode):
                row.update(type='file', bytes=info.st_size, sha256=sha(path))
                logical += info.st_size
            elif stat.S_ISDIR(info.st_mode):
                row['type'] = 'directory'
            else:
                need(stat.S_ISLNK(info.st_mode), 'Unexpected special artifact entry')
                row.update(type='symlink', target=os.readlink(path))
            rows.append(row)
    rows.sort(key=lambda row: row['path'])
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'path': str(root), 'treeSha256': digest, 'entries': len(rows), 'logicalBytes': logical, 'linuxAllocatedBytes': physical}


def verify_artifacts(receipt):
    for name, original in receipt['artifacts'].items():
        if original.get('retired'):
            continue
        current = artifact_identity(Path(original['path']))
        need(current['treeSha256'] == original['treeSha256'], 'Actual producer artifact changed: ' + name)


def validate_export(name, path, source, report, artifacts):
    if name in ['budget', 'swarm']:
        out = path / 'tmp/veyra-build/swarm'
        marker = json.loads((out / '.swarm-stage-owner.json').read_text())
        need(marker['revision'] == source['revision'] and marker['sourceSha256'] == source['sourceSha256'] and
             marker['dependencyLockSha256'] == report['npmLockSha256'], 'Actual Swarm producer identity differs')
        if name == 'swarm':
            release = json.loads((out / 'swarm-release.json').read_text())
            need(release['revision'] == source['revision'] and release['sourceSha256'] == source['sourceSha256'], 'Actual Swarm release identity differs')
            for key, relative in [('workerSha256', 'bin/veyra-swarm-worker'), ('contractFileSha256', 'contracts/swarm-contract.json'),
                                  ('typescriptSha256', 'contracts/index.ts'), ('budgetPluginSha256', 'budget/index.mjs'),
                                  ('licenseManifestSha256', 'licenses/manifest.json')]:
                need(sha(out / relative) == release[key], 'Actual compiled Swarm output differs: ' + key)
    elif name == 'rust':
        proof = json.loads((path / 'out/rust-api-build-inputs.json').read_text())
        need(proof['cargoLockSha256'] == report['cargo']['services/veyra-api/Cargo.lock']['sha256'], 'Actual Rust lock differs')
        need(sha(path / 'out/veyra-read-api') == proof['binarySha256'] and
             sha(path / 'out/rust-api-licenses/manifest.json') == proof['noticeManifestSha256'], 'Actual Rust API/notices differ')
    elif name == 'node':
        proof = json.loads((path / 'usr/local/share/veyra/source-inputs.json').read_text())
        need(proof['revision'] == source['revision'] and proof['sourceSha256'] == source['sourceSha256'], 'Actual Node producer source differs')
        generated = Path(artifacts['swarm']['path']) / 'tmp/veyra-build/swarm/contracts/index.ts'
        need(sha(path / 'app/packages/veyra-contracts/src/index.ts') == sha(generated), 'Node did not consume the actual generated canonical contract')


def diagnostic_reason(path, info):
    """Preserve potential unique diagnostics, not just the parent's build log."""
    name = path.name.lower()
    suffixes = ('.core', '.dmp', '.dump', '.mdmp', '.hprof', '.heapsnapshot',
                '.heapprofile', '.cpuprofile', '.profraw', '.etl', '.trace', '.perfetto-trace')
    if (name == 'core' or name.startswith('core.') or name.endswith(suffixes)
            or name.startswith(('rustc-ice-', 'hs_err_pid', 'replay_pid'))
            or name in ['npm-debug.log', 'yarn-error.log']
            or name.endswith('.log') and any(part in ['_logs', 'npm-logs'] for part in path.parts)
            or name in ['output', 'stderr'] and 'build' in path.parts and 'target' in path.parts
            or name.startswith('report.') and name.endswith('.json')):
        return 'Potential unique crash/trace/compiler diagnostic by exact path/name'
    if stat.S_ISREG(info.st_mode):
        with path.open('rb') as stream:
            header = stream.read(20)
        if header.startswith(b'MDMP'):
            return 'Potential minidump signature'
        if (len(header) >= 18 and header[:4] == b'\x7fELF' and header[5] in [1, 2]
                and int.from_bytes(header[16:18], 'little' if header[5] == 1 else 'big') == 4):
            return 'ELF ET_CORE diagnostic'
    return None


def preserve_diagnostics(receipt, found):
    """Move closed unique files on the same filesystem without another bulk copy."""
    preserved = set()
    for path, original, reason in found:
        key = (original.st_dev, original.st_ino)
        if key in preserved:
            continue
        need(stat.S_ISREG(original.st_mode), 'Diagnostic link/special entry needs separate preservation: ' + str(path))
        destination_root = WORK / 'diagnostics'
        if not destination_root.exists():
            destination_root.mkdir(mode=0o700)
            receipt['diagnosticsRootIdentity'] = [destination_root.stat().st_dev, destination_root.stat().st_ino]
        need(destination_root.resolve() == destination_root and
             [destination_root.stat().st_dev, destination_root.stat().st_ino] == receipt.get('diagnosticsRootIdentity') and
             destination_root.stat().st_dev == original.st_dev, 'Diagnostic preservation filesystem/owner changed')
        current = path.lstat()
        need((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) ==
             (original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns), 'Diagnostic changed before preservation')
        digest = sha(path)
        token = hashlib.sha256(os.fsencode(path) + b'\0' + str(original.st_ino).encode() + bytes.fromhex(digest)).hexdigest()[:24]
        destination = destination_root / (token + '-' + path.name[:160])
        need(not destination.exists() and not destination.is_symlink(), 'Never replace an existing unique diagnostic')
        current = path.lstat()
        need((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) ==
             (original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns), 'Diagnostic changed while hashing')
        row = {'originalPath': str(path), 'path': str(destination), 'bytes': original.st_size,
               'linuxAllocatedBytes': original.st_blocks * 512, 'sha256': digest, 'reason': reason,
               'originalIdentity': {'device': original.st_dev, 'inode': original.st_ino,
                    'mode': original.st_mode & 0o7777, 'uid': original.st_uid, 'gid': original.st_gid,
                    'mtimeNs': original.st_mtime_ns, 'ctimeNs': original.st_ctime_ns},
               'consumer': 'Root diagnosis of this exact producer failure; unique diagnostic remains protected', 'moved': False}
        receipt.setdefault('diagnostics', []).append(row)
        write_json(WORK / 'result.json', receipt)
        path.rename(destination)
        row['moved'] = True
        need((destination.stat().st_dev, destination.stat().st_ino) == key and sha(destination) == digest,
             'Unique diagnostic preservation failed; retain original target')
        preserved.add(key)
        write_json(WORK / 'result.json', receipt)
    return preserved


def retire_targets(receipt, targets, pass_name):
    """Same qualified deletion checks, scoped to newly generated current outputs."""
    need(not any(row['pass'] == pass_name for row in receipt['cleanupPasses']), 'Never retry an earlier cleanup pass/refusal')
    verify_artifacts(receipt)
    cleanup = {'pass': pass_name, 'removed': [], 'retained': [], 'windowsRecoveryClaimed': False}
    previous_refusals = [(Path(row['path']), previous['pass'], row['failedSafetyCheck'])
        for previous in receipt['cleanupPasses'] for row in previous['retained']]
    receipt['cleanupPasses'].append(cleanup)
    for target in targets:
        if not target.exists() and not target.is_symlink() and not target.is_socket():
            continue
        try:
            prior = next((row for row in previous_refusals
                          if target.is_relative_to(row[0]) or row[0].is_relative_to(target)), None)
            need(prior is None, 'Protected by earlier cleanup refusal; no retry: ' + str(prior))
            need(target.resolve() == target and target.is_relative_to(ROOT) and
                 (target.is_relative_to(WORK) or target.is_relative_to(TOOLS)), 'Cleanup target escaped exact owned subtree')
            need(target != WORK and not (WORK / 'diagnostics').is_relative_to(target), 'Unique records/diagnostics are protected')
            needle = str(target).encode()
            for process in Path('/proc').iterdir():
                if not process.name.isdigit() or int(process.name) == os.getpid():
                    continue
                try:
                    state, original_birth = process_status(process.name)
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if state in ('Z', 'X', 'x'):
                    continue
                try:
                    for kind in ['cmdline', 'environ', 'maps', 'mountinfo']:
                        need(needle not in (process / kind).read_bytes(), 'Active ' + kind + ' reference PID ' + process.name)
                    for item in [process / 'cwd', process / 'root', process / 'exe', *list((process / 'fd').iterdir())]:
                        try:
                            value = os.readlink(item).encode()
                        except FileNotFoundError:
                            continue
                        need(needle not in value, 'Active process handle PID ' + process.name)
                except OSError as error:
                    if error.errno not in (errno.ENOENT, errno.ESRCH, errno.EINVAL):
                        raise
                    try:
                        current_state, current_birth = process_status(process.name)
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    if current_birth == original_birth and current_state not in ('Z', 'X', 'x'):
                        raise
            need(needle not in Path('/proc/self/mountinfo').read_bytes(), 'Active mount reference')
            initial = target.lstat()
            entries, identities, links, diagnostics = [target], {}, collections.Counter(), []
            while entries:
                path = entries.pop()
                info = path.lstat()
                need(info.st_dev == initial.st_dev and path.name != '.git', 'Nested filesystem or source repository')
                identity = (info.st_dev, info.st_ino)
                identities[identity] = info
                if stat.S_ISDIR(info.st_mode):
                    entries.extend(path.iterdir())
                    continue
                links[identity] += 1
                if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                    reason = diagnostic_reason(path, info)
                    if reason:
                        diagnostics.append((path, info, reason))
                    continue
                whiteout = (target == WORK / 'store' and stat.S_ISCHR(info.st_mode)
                    and os.major(info.st_rdev) == 0 and os.minor(info.st_rdev) == 0 and info.st_size == 0
                    and str(path.relative_to(target)).startswith('runc-overlayfs/snapshots/snapshots/'))
                need(whiteout or (target == WORK / 'socket' and stat.S_ISSOCK(info.st_mode)), 'Unexpected special cache entry')
            need(all(identities[key].st_nlink == count for key, count in links.items()), 'Hard link outside exact cleanup target')
            need((target.lstat().st_dev, target.lstat().st_ino) == (initial.st_dev, initial.st_ino), 'Cleanup identity changed')
            preserved = preserve_diagnostics(receipt, diagnostics)
            # A moved diagnostic can retain an inode also named by aliases in
            # this store. Its data blocks are retained, never claimed recovered.
            size = (allocated(target, preserved) if stat.S_ISDIR(initial.st_mode)
                    else 0 if (initial.st_dev, initial.st_ino) in preserved else target.lstat().st_blocks * 512)
            if stat.S_ISDIR(initial.st_mode):
                need(shutil.rmtree.avoids_symlink_attacks, 'Descriptor-safe cleanup unavailable')
                shutil.rmtree(target)
            else:
                if (initial.st_dev, initial.st_ino) not in preserved:
                    target.unlink()
            cleanup['removed'].append({'path': str(target), 'linuxAllocatedBytes': size})
            cleanup['linuxAllocatedBytesRemoved'] = sum(row['linuxAllocatedBytes'] for row in cleanup['removed'])
            for artifact in receipt['artifacts'].values():
                if Path(artifact['path']).is_relative_to(target):
                    artifact['retired'] = True
        except Exception as error:
            row = {'path': str(target), 'failedSafetyCheck': str(error)}
            try:
                row['linuxAllocatedBytes'] = allocated(target) if target.is_dir() and not target.is_symlink() else target.lstat().st_blocks * 512
            except OSError as measurement_error:
                row.update(linuxAllocatedBytes=None, allocationError=str(measurement_error))
            cleanup['retained'].append(row)
        write_json(WORK / 'result.json', receipt)
    verify_artifacts(receipt)
    cleanup['linuxAllocatedBytesRemoved'] = sum(row['linuxAllocatedBytes'] for row in cleanup['removed'])
    need(not cleanup['retained'], 'A cleanup safety check failed; preserve exact targets and do not advance')


def retained_output(path, reason):
    row = {'path': str(path), 'reason': reason}
    try:
        row['linuxAllocatedBytes'] = allocated(path) if path.is_dir() and not path.is_symlink() else path.lstat().st_blocks * 512
        if path.is_file() and not path.is_symlink():
            row['bytes'] = path.stat().st_size
    except OSError as error:
        row.update(linuxAllocatedBytes=None, allocationError=str(error))
    return row


def owned_processes_terminal(receipt):
    observed = []
    for stage in receipt['stages']:
        for kind in ['client', 'daemon']:
            original = stage.get(kind)
            if original is None:
                need(not stage.get(kind + 'LaunchAttempted'), 'No PID/start identity captured for attempted ' + stage['name'] + ' ' + kind)
                continue
            need(original.get('startTicks') is not None, 'Unknown original start identity: ' + str(original))
            identity = {'stage': stage['name'], 'kind': kind, **original}
            try:
                fields = (Path('/proc') / str(original['pid']) / 'stat').read_text().split(') ', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                identity['terminalObservation'] = 'original PID absent'
            else:
                if fields[19] == original['startTicks']:
                    need(fields[0] == 'Z', 'Original owned process remains active: ' + str(identity))
                    identity['terminalObservation'] = 'original process terminal/zombie; reference checks still required'
                else:
                    identity['terminalObservation'] = 'PID reused; unrelated replacement is untouched'
            observed.append(identity)
    return observed


def failure_cleanup(receipt, protected, scratch):
    """Clean this stopped invocation; keep original failure evidence and exports."""
    result = receipt['failureCleanup'] = {'at': now(), 'retained': [], 'preservedRecords': [],
        'linuxAllocatedBytesRemoved': 0, 'windowsRecoveryClaimed': False}
    candidates = [path for path in scratch if path.exists() or path.is_symlink() or path.is_socket()]
    archive = TOOLS / ASSET
    try:
        need(ROOT.resolve() == ROOT and WORK.resolve() == WORK and
             WORK.stat().st_dev == receipt['preflight']['rootIdentity']['device'], 'Failure cleanup root/filesystem changed')
        owner = json.loads((WORK / OWNER_FILENAME).read_text())
        need(all(owner.get(key) == receipt[key] for key in ['owner', 'executor', 'revision', 'sourceSha256']),
             'Failure cleanup invocation ownership differs')
        result['terminalProcesses'] = owned_processes_terminal(receipt)
        changed = [str(path) for path, expected in protected.items() if sha(path) != expected]
        need(not changed, 'Original source/lock preservation failed: ' + ', '.join(changed))
        verify_artifacts(receipt)
        # Logs/metadata are outside every cleanup target and remain byte-identical.
        for path in WORK.iterdir():
            if path.name.endswith(('.log', '-metadata.json')) or path.name == 'owner.json':
                need(path.is_file() and not path.is_symlink(), 'Original log/metadata identity is unqualified: ' + str(path))
                result['preservedRecords'].append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)})
            elif path.name != 'result.json' and not path.is_dir():
                reason = diagnostic_reason(path, path.lstat())
                if reason:
                    row = retained_output(path, reason + '; unique top-level diagnostic remains protected for Root diagnosis')
                    if path.is_file() and not path.is_symlink():
                        row['sha256'] = sha(path)
                    result['retained'].append(row)
        if archive.exists() or archive.is_symlink():
            if (archive.is_file() and not archive.is_symlink() and archive.stat().st_size == ASSET_BYTES
                    and sha(archive) == ASSET_SHA):
                candidates.append(archive)
            else:
                row = retained_output(archive, 'Unqualified partial/changed tool archive: exact original-byte regeneration or diagnostic preservation is unproven')
                if archive.is_file() and not archive.is_symlink():
                    row['sha256'] = sha(archive)
                result['retained'].append(row)
        # A failure handler must not re-enter a refused normal cleanup target.
        fresh = []
        for path in candidates:
            prior = next(((previous['pass'], row) for previous in receipt['cleanupPasses'] for row in previous['retained']
                if path.is_relative_to(Path(row['path'])) or Path(row['path']).is_relative_to(path)), None)
            if prior:
                result['retained'].append({**prior[1], 'reason': 'Earlier cleanup refusal remains protected; not retried', 'priorPass': prior[0]})
            else:
                fresh.append(path)
        candidates = fresh
        write_json(WORK / 'result.json', receipt)
        if candidates:
            try:
                attempt = receipt.get('attempt', 'initial')
                pass_name = 'failed-invocation-stopped-scratch'
                if attempt != 'initial':
                    pass_name += '-' + attempt
                retire_targets(receipt, candidates, pass_name)
            except Exception as error:
                result['cleanupSafetyFailure'] = str(error)
            cleanup = next((row for row in receipt['cleanupPasses'] if row['pass'] == 'failed-invocation-stopped-scratch'), None)
            if cleanup:
                result['linuxAllocatedBytesRemoved'] = cleanup.get('linuxAllocatedBytesRemoved', 0)
                result['retained'].extend(cleanup['retained'])
        need(all(sha(path) == expected for path, expected in protected.items()), 'Original source/locks changed across failure cleanup')
        need(all(sha(Path(row['path'])) == row['sha256'] for row in result['preservedRecords']), 'Original failure log/metadata changed')
        verify_artifacts(receipt)
    except Exception as error:
        result['preservationOrTerminalFailure'] = str(error)
        accounted = {row['path'] for row in result['retained']}
        for path in candidates:
            if str(path) not in accounted and (path.exists() or path.is_symlink() or path.is_socket()):
                result['retained'].append(retained_output(path, 'Cleanup not entered: ' + str(error)))
    if (archive.exists() or archive.is_symlink()) and not any(row['path'] == str(archive) for row in result['retained']):
        result['retained'].append(retained_output(archive,
            'Original tool input retained: terminal/preservation gate did not establish safe authenticated retirement'))
    consumers = {'budget': 'Remaining same-source canonical Swarm producer',
                 'swarm': 'Remaining same-source Node contract/final-image or image-projection review',
                 'rust': 'Remaining same-source final-image or image-projection review',
                 'node': 'Remaining same-source final-image or image-projection review'}
    for name, row in receipt['artifacts'].items():
        if not row.get('retired'):
            result['retained'].append({**row, 'reason': consumers[name]})
    for stage in receipt['stages']:
        path = WORK / 'veyra-linux.oci.tar' if stage['name'] == 'image' else WORK / 'handoffs' / stage['name']
        if (path.exists() or path.is_symlink()) and (stage['name'] == 'image' or stage['name'] not in receipt['artifacts']):
            result['retained'].append(retained_output(path, 'Unqualified partial OCI/export: exact regeneration and diagnostic preservation are not yet proven; retain original failure output'))
    for path, reason in [(WORK / 'context', 'Exact-source repair context; original committed source remains authoritative'),
                         (WORK / 'browser-extension', 'Same-source final-image repair context'),
                         (TOOLS, 'Pinned acquisition/build tools for the concrete same-source repair; partial extraction remains unqualified')]:
        if path.exists() or path.is_symlink():
            result['retained'].append(retained_output(path, reason))
    result['finishedAt'] = now()
    write_json(WORK / 'result.json', receipt)


def stage_env():
    env = {k: v for k, v in os.environ.items() if k in ['PATH', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR']}
    paths = {'HOME': 'home', 'TMPDIR': 'tmp', 'TEMP': 'tmp', 'TMP': 'tmp', 'XDG_CACHE_HOME': 'cache',
             'XDG_CONFIG_HOME': 'config', 'XDG_STATE_HOME': 'state', 'XDG_RUNTIME_DIR': 'run',
             'DOCKER_CONFIG': 'home/.docker', 'NPM_CONFIG_CACHE': 'cache/npm', 'NPM_CONFIG_LOGS_DIR': 'cache/npm-logs',
             'APPDATA': 'appdata', 'LOCALAPPDATA': 'localappdata'}
    for key, suffix in paths.items():
        directory = WORK / suffix
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[key] = str(directory)
    env.update({'GOMEMLIMIT': '256MiB', 'GOMAXPROCS': '2', 'NODE_DISABLE_COMPILE_CACHE': '1'})
    return env


def execute_stage(name, target, overrides, source, ext, report, lease, receipt):
    verify_artifacts(receipt)
    planned = lease['growthPhases'][name]
    preserved = sum(row['linuxAllocatedBytes'] for row in receipt['artifacts'].values() if not row.get('retired'))
    need(preserved <= planned['preservedExports'], 'Measured retained exports exceed phase allowance; do not start ' + name)
    pending = sum(planned[key] for key in ['contentAndSnapshots', 'compilerWorkingSets', 'outputCoexistence', 'margin'])
    need(task_allocated() + lease['nativeBudgetBytes'] + pending <= CEILING,
         'Fresh measured complete phase peak exceeds paired ceiling: ' + name)
    need(shutil.disk_usage(ROOT).free - pending >= FLOOR, 'Destination cannot retain floor during ' + name)
    windows_free = int(command([WINPY, '-I', '-B', '-c', "import shutil;print(shutil.disk_usage('C:/').free)"]))
    need(windows_free - pending >= FLOOR, 'C: cannot retain floor during ' + name)
    env = stage_env()
    (WORK / 'runc').mkdir(mode=0o700)
    runtime, config = WORK / 'runtime', WORK / 'buildkitd.toml'
    runtime.write_text('#!/bin/sh\nset -eu\nexec ' + str(TOOLS / 'bin/buildkit-runc') + ' --root ' + str(WORK / 'runc') + ' "$@"\n')
    runtime.chmod(0o700)
    config.write_text('debug = false\n[worker.oci]\n  gc = true\n  reservedSpace = 0\n'
        '  maxUsedSpace = 3221225472\n[[worker.oci.gcpolicy]]\n  all = true\n'
        '  reservedSpace = 0\n  maxUsedSpace = 3221225472\n')
    address = 'unix://' + str(WORK / 'socket')
    output = WORK / 'veyra-linux.oci.tar' if name == 'image' else WORK / 'handoffs' / name
    need(not output.exists(), 'Never replace an existing exported artifact')
    row = {'name': name, 'target': target, 'startedAt': now(), 'producerExitCode': None}
    row['admission'] = {'preservedExportBytes': preserved, 'pendingGrowthBytes': pending, 'windowsFreeBytes': windows_free}
    receipt['stages'].append(row)
    daemon = client = None
    try:
        with (WORK / (name + '-daemon.log')).open('xb') as daemon_log, (WORK / (name + '-build.log')).open('xb') as build_log:
            row['daemonLaunchAttempted'] = True
            daemon = subprocess.Popen([str(TOOLS / 'bin/buildkitd'), '--root', str(WORK / 'store'), '--addr', address,
                '--config', str(config), '--oci-worker=true', '--containerd-worker=false', '--oci-worker-snapshotter', 'overlayfs',
                '--oci-worker-net', 'host', '--oci-worker-binary', str(runtime), '--oci-max-parallelism', '1', '--cdi-disabled'],
                env=env, cwd=WORK, stdout=daemon_log, stderr=daemon_log, start_new_session=True)
            row['daemon'] = {'pid': daemon.pid, 'startTicks': None}
            row['daemon']['startTicks'] = birth(daemon.pid)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                need(daemon.poll() is None, 'Owned daemon exited; preserve stage daemon log')
                ready = subprocess.run([str(TOOLS / 'bin/buildctl'), '--addr', address, 'debug', 'workers'], env=env, cwd=WORK, capture_output=True, timeout=5)
                if ready.returncode == 0:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('Owned daemon readiness timed out')
            argv = [str(TOOLS / 'bin/buildctl'), '--addr', address, 'build', '--frontend', 'dockerfile.v0',
                '--local', 'context=' + str(WORK / 'context'), '--local', 'dockerfile=' + str(WORK / 'context'),
                '--local', 'veyra-browser-extension=' + str(WORK / 'browser-extension'),
                '--opt', 'context:veyra-browser-extension=local:veyra-browser-extension',
                '--opt', 'platform=linux/amd64', '--opt', 'target=' + target,
                '--opt', 'memory=4294967296', '--opt', 'memswap=4294967296', '--opt', 'cpuperiod=100000', '--opt', 'cpuquota=150000',
                '--opt', 'build-arg:IMAGE_REVISION=' + source['revision'], '--opt', 'build-arg:IMAGE_SOURCE=https://github.com/jtmb/ingenium',
                '--opt', 'build-arg:IMAGE_SOURCE_SHA256=' + source['sourceSha256'],
                '--opt', 'build-arg:SOURCE_DATE_EPOCH=' + str(source['sourceDateEpoch']),
                '--opt', 'build-arg:VEYRA_BROWSER_EXTENSION_SHA256=' + ext['sourceSha256']]
            for stage, value in overrides.items():
                if isinstance(value, Path):
                    key = 'handoff-' + stage
                    argv.extend(['--local', key + '=' + str(value), '--opt', 'context:' + stage + '=local:' + key])
                else:
                    argv.extend(['--opt', 'context:' + stage + '=docker-image:' + value])
            if name == 'image':
                argv.extend(['--opt', 'label:org.veyra.image.role=' + target])
            argv.extend(['--output', ('type=oci,dest=' if name == 'image' else 'type=local,dest=') + str(output),
                         '--metadata-file', str(WORK / (name + '-metadata.json')), '--progress', 'plain'])
            row['arguments'] = argv
            write_json(WORK / 'result.json', receipt)
            print(json.dumps({'stage': name, 'state': 'actual-producer-starting'}), flush=True)
            row['clientLaunchAttempted'] = True
            client = subprocess.Popen(argv, env=env, cwd=WORK, stdout=build_log, stderr=build_log, start_new_session=True)
            row['client'] = {'pid': client.pid, 'startTicks': None}
            row['client']['startTicks'] = birth(client.pid)
            while client.poll() is None:
                try:
                    client.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    live = task_allocated()
                    row['peakObservedTaskBytes'] = max(row.get('peakObservedTaskBytes', 0), live + lease['nativeBudgetBytes'])
                    need(live + lease['nativeBudgetBytes'] <= CEILING, 'Observed paired ceiling reached; cancel only owned build')
                    need(shutil.disk_usage(ROOT).free >= FLOOR, 'Destination floor reached; cancel only owned build')
                    free = int(command([WINPY, '-I', '-B', '-c', "import shutil;print(shutil.disk_usage('C:/').free)"]))
                    need(free >= FLOOR, 'C: floor reached; cancel only owned build')
                    write_json(WORK / 'result.json', receipt)
            row['producerExitCode'] = client.returncode
            need(client.returncode == 0, 'Actual ' + name + ' producer failed; preserve its original log')
    except BaseException as error:
        row['originalFailure'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        for kind, process in [('client', client), ('daemon', daemon)]:
            if process is not None:
                row.setdefault(kind, {'pid': process.pid, 'startTicks': None})
        try:
            if client is not None and client.poll() is None:
                need(birth(client.pid) == row['client']['startTicks'], 'Client identity changed; do not signal')
                os.killpg(client.pid, signal.SIGINT)
                try:
                    client.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    row['clientStopFailed'] = True
            if (client is None or client.poll() is not None) and daemon is not None and daemon.poll() is None:
                need(birth(daemon.pid) == row['daemon']['startTicks'], 'Daemon identity changed; do not signal')
                daemon.terminate()
                try:
                    daemon.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    row['daemonStopFailed'] = True
        except BaseException as error:
            row['stopFailure'] = {'type': type(error).__name__, 'message': str(error)}
        row['daemonStopped'] = daemon is None or daemon.poll() is not None
        row['clientStopped'] = client is None or client.poll() is not None
        row['daemonExitCode'] = None if daemon is None else daemon.returncode
        row['clientExitCode'] = None if client is None else client.returncode
        row['finishedAt'] = now()
        write_json(WORK / 'result.json', receipt)
    need(row['daemonStopped'] and row['clientStopped'], 'A producer remains active; do not advance')
    if name != 'image':
        validate_export(name, output, source, report, receipt['artifacts'])
        receipt['artifacts'][name] = {**artifact_identity(output), 'producerStage': name,
            'revision': source['revision'], 'sourceSha256': source['sourceSha256'], 'producerExitCode': row['producerExitCode']}
        write_json(WORK / 'result.json', receipt)
    else:
        need(output.is_file() and not output.is_symlink() and output.stat().st_size > 0, 'Complete OCI export absent')
    return output


def run(args, source, ext, report):
    need(os.getuid() == 0, 'Use the established isolated root-owned WSL builder')
    os.umask(0o077)
    lease = admit(args.lease.absolute(), report)
    need(report['serialExportTargetsInstalled'], 'Root must integrate the reviewed artifact-export-only Dockerfile patch first')
    need(not WORK.exists() and not TOOLS.exists(), 'Prior current outputs/tools require reconciliation; never replace them')
    identity = report['rootIdentity']
    need((ROOT.stat().st_dev, ROOT.stat().st_ino, ROOT.stat().st_uid) ==
         (identity['device'], identity['inode'], identity['uid']), 'Task root identity changed')
    for parent in [WORK.parent, TOOLS.parent]:
        need(parent.resolve() == parent and parent.stat().st_dev == identity['device'], 'Output filesystem changed')
    WORK.mkdir(mode=0o700)
    lock = (WORK / 'executor.lock').open('xb')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    owner = {'owner': OWNER, 'executor': EXECUTOR, 'root': str(ROOT), 'revision': source['revision'],
             'sourceSha256': source['sourceSha256'], 'regeneration': 'This serial command, exact source/locks/extension and pinned tools'}
    write_json(WORK / 'owner.json', owner)
    receipt = {'at': now(), **owner, 'state': 'serial-candidate-preparing', 'globalDockerStoreUsed': False,
               'admission': lease, 'preflight': report, 'stages': [], 'artifacts': {}, 'cleanupPasses': []}
    record = WORK / 'result.json'
    write_json(record, receipt)
    protected = {APP / item['path']: item['sha256'] for item in source['files']}
    protected.update({args.extension.absolute() / item['name']: item['sha256'] for item in ext['files']})
    scratch = [WORK / n for n in ['store', 'runc', 'tmp', 'cache', 'home', 'config', 'state', 'run', 'appdata', 'localappdata', 'socket']]
    try:
        tool_inputs(receipt)
        contexts(source, args.extension.absolute(), ext)
        (WORK / 'handoffs').mkdir(mode=0o700)
        base = report['nodeBase']
        hand = WORK / 'handoffs'
        stages = [
            ('budget', 'veyra-budget-artifact', {}),
            ('swarm', 'veyra-swarm-artifact', {'swarm-budget-builder': hand / 'budget', 'node-dependencies': base}),
            ('rust', 'veyra-rust-artifact', {'builder': base}),
            ('node', 'veyra-node-artifact', {'swarm-rust-builder': hand / 'swarm'}),
            ('image', args.target, {'builder': hand / 'node', 'vendor-security': hand / 'node',
                'computer-use': hand / 'node', 'rust-api-builder': hand / 'rust', 'swarm-rust-builder': hand / 'swarm'}),
        ]
        for name, target, overrides in stages:
            receipt['state'] = 'building-' + name
            execute_stage(name, target, overrides, source, ext, report, lease, receipt)
            need(all(sha(file) == expected for file, expected in protected.items()), 'Original source/locks changed')
            targets = scratch + ([hand / 'budget'] if name == 'swarm' else [])
            retire_targets(receipt, targets, name + '-last-consumer')
            write_json(record, receipt)
        import sys
        sys.path.insert(0, str(APP / 'ops'))
        from oci_image import Archive
        archive = WORK / 'veyra-linux.oci.tar'
        candidate = Archive(archive)
        try:
            labels = candidate.labels
            need(labels.get('org.opencontainers.image.revision') == source['revision'] and
                 labels.get('org.opencontainers.image.source') == 'https://github.com/jtmb/ingenium' and
                 labels.get('org.ingenium.source.sha256') == source['sourceSha256'] and
                 labels.get('dev.veyra.browser-extension.source-sha256') == ext['sourceSha256'] and
                 labels.get('org.veyra.image.role') == args.target, 'Built image provenance differs')
            receipt['oci'] = {'path': str(archive), 'bytes': archive.stat().st_size,
                             'archiveSha256': sha(archive), 'digest': candidate.digest, 'labels': labels}
        finally:
            candidate.close()
        retire_targets(receipt, [WORK / 'context', WORK / 'browser-extension', WORK / 'handoffs', TOOLS,
                                WORK / 'runtime', WORK / 'buildkitd.toml'], 'final-archive-consumer')
        need(all(sha(file) == expected for file, expected in protected.items()), 'Original sources/locks changed across cleanup')
        need(sha(archive) == receipt['oci']['archiveSha256'], 'Required archive changed across cleanup')
        receipt['state'] = 'exact-source-serial-image-built-archive-validated-not-published'
    except BaseException as error:
        receipt.update(state='failed-preserve-original-observation', errorType=type(error).__name__, error=str(error))
        try:
            failure_cleanup(receipt, protected, scratch)
        except BaseException as cleanup_error:
            receipt['failureCleanupUnexpectedFailure'] = {'type': type(cleanup_error).__name__, 'message': str(cleanup_error)}
        raise
    finally:
        receipt['finishedAt'] = now()
        receipt['retainedConsumer'] = 'Root exact-image qualification and existing publisher; failed original observation remains preserved'
        write_json(record, receipt)
        lock.close()
    print(json.dumps({k: receipt.get(k) for k in ['state', 'stages', 'cleanupPasses', 'oci']}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'run'])
    parser.add_argument('--revision', required=True)
    parser.add_argument('--extension', type=Path, default=PHASE / 'windows-source/integrations/browser-extension')
    parser.add_argument('--lease', type=Path)
    parser.add_argument('--target', choices=['compatibility', 'control-plane', 'user-runtime', 'runtime-manager', 'runtime-gateway'], default='compatibility')
    args = parser.parse_args()
    source, extension, report = inspect(args.revision, args.extension)
    if args.mode == 'inspect':
        print(json.dumps(report, indent=2))
    else:
        need(args.lease is not None, 'Explicit existing-root coordinator lease file required')
        run(args, source, extension, report)


if __name__ == '__main__':
    main()
