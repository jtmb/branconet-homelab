#!/usr/bin/env python3
"""Pinned Bookworm producer primitives for the existing serial operator.

No host compiler substitution, global image store or snapshot copy is used.
The caller still owns complete graph orchestration, original full admission,
all original export/runtime validation, last-consumer cleanup and publication.
There is deliberately no standalone run CLI that skips those authorities.
"""
import contextlib
import copy
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time

sys.dont_write_bytecode = True


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture_full_authority(operator, report, lease_path, receipt, *, retire_before_image=0):
    """Fresh original full admission ONCE; later same-process stages retain it."""
    value = operator.admit(lease_path.absolute(), report, retire_before_image=retire_before_image)
    value['_admittedProcess'] = [os.getpid(), operator.birth(os.getpid())]
    value['_admittedRoot'] = [operator.ROOT.stat().st_dev, operator.ROOT.stat().st_ino]
    receipt['admission'] = value
    return value


def retain_full_authority(operator, report, authority, receipt):
    need(authority is receipt.get('admission') and
         authority.get('_admittedProcess') == [os.getpid(), operator.birth(os.getpid())] and
         authority.get('_admittedRoot') == [operator.ROOT.stat().st_dev, operator.ROOT.stat().st_ino] and
         authority.get('sourceSha256') == report['source']['sourceSha256'] and
         set(authority.get('growthPhases', {})) == {'tools', 'budget', 'swarm', 'rust', 'node', 'image'},
         'Only this same live originally admitted full serial authority may continue')
    return authority


class LocalBlob:
    """Adapter for the original immutable registry inventory, without reread IO."""
    def __init__(self, path, descriptor):
        self.stream = path.open('rb')
        self.descriptor, self.hash, self.bytes_read = descriptor, hashlib.sha256(), 0
    def read(self, size=-1):
        body = self.stream.read(size)
        self.hash.update(body)
        self.bytes_read += len(body)
        return body
    def verify(self):
        need(self.bytes_read == self.descriptor['size'] and
             'sha256:' + self.hash.hexdigest() == self.descriptor['digest'],
             'Original closed layer input changed')
    def close(self):
        self.stream.close()


class LocalReader:
    def __init__(self, path):
        self.path = path
    @contextlib.contextmanager
    def blob(self, descriptor):
        stream = LocalBlob(self.path, descriptor)
        try:
            yield stream
        finally:
            stream.close()


class Producer:
    def __init__(self, operator, report, lease_path, receipt, stage, probe=False, authority=None, seed=None, attempt='initial'):
        need(os.getuid() == 0, 'Original isolated root-owned executor required')
        need(stage in {'budget', 'swarm', 'rust', 'node', 'image'}, 'Original serial producer stage required')
        self.stage = stage
        need(re.fullmatch('[a-z][a-z0-9-]{0,30}', attempt), 'Exact owned producer attempt required')
        self.attempt = attempt
        self.closed_probe = probe
        self.operator, self.report, self.receipt = operator, report, receipt
        # Keep the ORIGINAL complete admission. A small metadata-probe lease
        # cannot become compiler authority through this API.
        if probe:
            path = Path(__file__).with_name('veyra-linux-probe-admission.py')
            spec = importlib.util.spec_from_file_location('veyra_closed_probe_admission', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.lease = (module.retained(operator, report, authority, receipt) if authority is not None else
                          module.admit(operator, report, lease_path.absolute()))
        else:
            if authority is None:
                self.lease = capture_full_authority(operator, report, lease_path, receipt)
            else:
                self.lease = retain_full_authority(operator, report, authority, receipt)
        path = Path(__file__).with_name('veyra-linux-cgroup-limits.py')
        spec = importlib.util.spec_from_file_location('veyra_effective_cgroups', path)
        limits = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(limits)
        limits.current()
        need(operator.WORK.resolve() == operator.WORK and operator.WORK.is_dir(),
             'Original exclusively owned current work must already exist')
        owner = json.loads((operator.WORK / operator.OWNER_FILENAME).read_text())
        need(owner['owner'] == operator.OWNER and owner['executor'] == operator.EXECUTOR and
             owner['revision'] == report['source']['revision'] and
             owner['sourceSha256'] == report['source']['sourceSha256'], 'Original current owner/source changed')
        self.root = operator.WORK / ('qualification-rootfs' if probe else operator.PRODUCER_ROOT_NAME)
        need(not self.root.exists(), 'Never replace a prior producer or failed filesystem')
        if seed is None:
            self.root.mkdir(mode=0o755)
        else:
            binding = seed.get('compatibleSource', seed['proof'])
            fields = {'archive', 'proof', 'config'}
            need(not probe and set(seed) in (fields, fields | {'compatibleSource'}) and
                 binding.get('revision') == report['source']['revision'] and
                 binding.get('sourceSha256') == report['source']['sourceSha256'] and
                 ('compatibleSource' not in seed or
                  binding is receipt.get('dependencySeedSourceTransition') and
                  binding['originalArchiveSha256'] == seed['proof']['sha256']),
                 'Only this originally admitted same-source successful producer seed may be restored')
            frozen = seed['config']
            need(set(frozen) == {'oci', 'environment', 'workingDirectory', 'arguments'} and
                 frozen['workingDirectory'].startswith('/'), 'Exact frozen producer config/ENV/ARG/WORKDIR required')
            path = Path(__file__).with_name('veyra-linux-streamed-handoff.py')
            spec = importlib.util.spec_from_file_location('veyra_original_handoff_restore', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            restored = module.restore(self.root, Path(seed['archive']), seed['proof'], operator=operator)
            need(restored['actualRestoredProjectionVerified'] is True, 'Actual seed projection was not restored')
        self.identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        self.environment, self.arguments, self.cwd = {}, {}, '/'
        self.sequence = 0
        self.config = {}
        if seed is not None:
            self.config = copy.deepcopy(seed['config']['oci'])
            self.environment = dict(seed['config']['environment'])
            self.arguments = dict(seed['config']['arguments'])
            self.cwd = seed['config']['workingDirectory']
        self.proof = {'source': report['source'], 'root': str(self.root),
                      'rootIdentity': self.identity, 'bases': [], 'instructions': [],
                      'hostCompilerUsed': False, 'acceptedFinalImage': False,
                      'hostExtractionTools': {str(path): sha(path) for path in [
                          Path('/usr/bin/bwrap'), Path('/usr/bin/tar'),
                          Path('/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2')]}}
        if seed is not None:
            self.proof['restoredSeed'] = {**restored, 'archiveSha256': seed['proof']['sha256'],
                'sourceSha256': seed['proof']['sourceSha256'],
                'frozenConfigSha256': hashlib.sha256(json.dumps(seed['config'], sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest()}
        receipt.setdefault('streamedProducerStages', []).append(self.proof)
        self.record()

    def record(self):
        self.operator.write_json(self.operator.WORK / 'result.json', self.receipt)

    def guard(self):
        o = self.operator
        need(self.root.resolve() == self.root and
             (self.root.stat().st_dev, self.root.stat().st_ino) == self.identity and
             self.root.stat().st_dev == o.ROOT.stat().st_dev, 'Original producer filesystem changed')
        need(o.task_allocated() + self.lease['nativeBudgetBytes'] <= o.CEILING,
             'Original paired ceiling reached; do not advance producer')
        need(shutil.disk_usage(o.ROOT).free >= o.FLOOR and
             int(o.command([o.WINPY, '-I', '-B', '-c',
                 "import shutil;print(shutil.disk_usage('C:/').free)"])) >= o.FLOOR,
             'Original C/destination floor reached; do not advance producer')

    def path(self, name):
        name = posixpath.normpath(posixpath.join(self.cwd, name))
        need(name.startswith('/') and '..' not in Path(name).parts and
             not name.startswith(('/__veyra_host', '/__veyra_input')), 'Producer path escaped reserved namespace')
        path = self.root / name.lstrip('/')
        # Refuse a host-resolving absolute image symlink rather than following it.
        need(path.parent.resolve().is_relative_to(self.root) or path == self.root,
             'Image path needs explicit namespace symlink resolution: ' + name)
        return path

    def sandbox(self, argv, log, host_tools=False, input_file=None, env=None):
        if not host_tools:
            need(not self.closed_probe, 'Closed probe cannot execute arbitrary image/install RUN instructions')
            qualification = self.receipt.get('ociIsolationQualification', {})
            need(qualification.get('passed') is True and
                 qualification.get('runtimeSha256') == self.operator.BINARIES['buildkit-runc'][1] and
                 qualification.get('seccompSourceSha256') ==
                 '785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334',
                 'Actual pinned OCI confinement/ownership/capability qualification must precede image RUN')
            path = Path(__file__).with_name('veyra-linux-oci-sandbox.py')
            spec = importlib.util.spec_from_file_location('veyra_original_oci_sandbox', path)
            sandbox = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sandbox)
            environment = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                           'HOME': '/root', **self.arguments, **self.environment, **(env or {})}
            sandbox.run(self, argv, environment, log)
            return
        need(input_file is not None and env is None and self.cwd == '/' and argv == [
            '/__veyra_host/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2',
            '--library-path', '/__veyra_host/lib/x86_64-linux-gnu:/__veyra_host/lib',
            '/__veyra_host/bin/tar', '--extract', '--file=-',
            '--directory=/', '--numeric-owner', '--same-owner', '--same-permissions',
            '--xattrs', '--xattrs-include=*', '--acls', '--selinux', '--keep-directory-symlink',
            '--delay-directory-restore', '--exclude=.wh.*', '--exclude=*/.wh.*'],
            'Host tool namespace is exclusively the fixed verified base extraction; never image commands')
        self.guard()
        host_marker, input_marker = self.root / '__veyra_host', self.root / '__veyra_input'
        need(not host_marker.exists() and not host_marker.is_symlink() and
             not input_marker.exists() and not input_marker.is_symlink(),
             'Never reuse an unresolved temporary namespace mountpoint')
        args = ['/usr/bin/bwrap', '--die-with-parent', '--new-session', '--unshare-pid',
                '--unshare-ipc', '--unshare-uts', '--unshare-cgroup', '--bind', str(self.root), '/',
                '--dev', '/dev', '--proc', '/proc', '--cap-drop', 'ALL',
                '--cap-add', 'CAP_CHOWN', '--cap-add', 'CAP_DAC_OVERRIDE',
                '--cap-add', 'CAP_FOWNER', '--cap-add', 'CAP_FSETID',
                '--cap-add', 'CAP_SETFCAP', '--clearenv']
        if host_tools:
            args += ['--ro-bind', '/usr', '/__veyra_host']
        if input_file is not None:
            need(input_file.resolve() == input_file and input_file.is_relative_to(self.operator.WORK),
                 'Only original owned immutable input may be mounted')
        environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root'}
        for key, value in environment.items():
            args += ['--setenv', key, value]
        args += ['--chdir', self.cwd, '--', *argv]
        child = subprocess.Popen(args, cwd=self.operator.WORK, stdout=log, stderr=log,
                                 stdin=subprocess.PIPE, start_new_session=True)
        birth = self.operator.birth(child.pid)
        feeder_errors = []
        def feed_verified_tar():
            try:
                # Compressed+diffID integrity was checked before this call.
                # Decompression stays in the trusted parent: no gzip binary or
                # shell is needed inside the initially empty image filesystem.
                with gzip.open(input_file, 'rb') as incoming:
                    for block in iter(lambda: incoming.read(1024 * 1024), b''):
                        child.stdin.write(block)
                child.stdin.close()
            except BaseException as error:
                feeder_errors.append(error)
                if not child.stdin.closed:
                    child.stdin.close()
        feeder = threading.Thread(target=feed_verified_tar, daemon=True)
        feeder.start()
        try:
            while child.poll() is None:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.guard()
            feeder.join(timeout=10)
            need(child.returncode == 0 and not feeder.is_alive() and not feeder_errors,
                 'Original producer instruction/input failed; preserve log and rootfs')
        except BaseException as error:
            self.proof['originalFailure'] = {'type': type(error).__name__, 'message': str(error),
                                             'childPid': child.pid, 'childStartTicks': birth}
            self.record()
            raise
        finally:
            if child.poll() is None:
                need(self.operator.birth(child.pid) == birth, 'Owned child identity changed; do not signal')
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('Owned isolated producer did not stop; retain filesystem and do not advance')
            if host_tools and host_marker.exists():
                need(host_marker.is_dir() and not host_marker.is_symlink() and
                     not any(host_marker.iterdir()), 'Temporary tool mountpoint is not an empty owned directory')
                host_marker.rmdir()
            if input_file is not None and input_marker.exists():
                need(input_marker.is_file() and not input_marker.is_symlink() and
                     input_marker.stat().st_size == 0, 'Temporary input mountpoint has unexpected content')
                input_marker.unlink()
            if child.poll() is not None:
                if not child.stdin.closed:
                    child.stdin.close()
                feeder.join(timeout=2)
            self.guard()

    def load_base(self, repository, lock_key):
        self.guard()
        sys.path.insert(0, str(self.operator.APP / 'ops'))
        from registry_image_reader import RegistryImageReader
        from registry_layer_inventory import inventory_layer
        lock = json.loads((self.operator.APP / 'tools/veyra-release/linux-build.lock.json').read_text())[lock_key]
        reader = RegistryImageReader(repository)
        image = reader.image(lock['manifestDigest'])
        need(image['selectedDigest'] == lock['manifestDigest'] and
             image['manifest']['config']['digest'] == lock['configDigest'], 'Pinned base/config differs')
        base = {'repository': repository, 'manifestDigest': lock['manifestDigest'],
                'configDigest': lock['configDigest'], 'layers': []}
        for index, (descriptor, diff) in enumerate(zip(image['manifest']['layers'], image['config']['rootfs']['diff_ids'])):
            # Only ONE original compressed layer coexists with the mutable
            # filesystem; there is no content-store or snapshot duplicate.
            path = self.operator.WORK / ('base-layer-' + self.stage + '-' + lock_key + '-' + str(index) + '.tar.gz')
            retained = self.receipt.get('protectedBaseLayers', {}).get(str(path))
            if retained is not None:
                need(path.resolve() == path and path.is_file() and retained == descriptor['digest'],
                     'Protected prior layer cannot be replaced or retired')
            if path.exists():
                need(path.resolve() == path and path.is_file() and
                     path.stat().st_size == descriptor['size'] and
                     'sha256:' + sha(path) == descriptor['digest'],
                     'Prior immutable input changed/partial; retain it, never replace')
            else:
                last_guard = time.monotonic()
                with reader.blob(descriptor) as source, path.open('xb') as output:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        output.write(block)
                        if time.monotonic() - last_guard >= 10:
                            self.guard()
                            last_guard = time.monotonic()
                    source.verify()
            inventory = inventory_layer(LocalReader(path), descriptor, diff)
            rows = inventory['rows']
            need(len({row['path'] for row in rows}) == len(rows), 'Duplicate OCI base path')
            for row in rows:
                need(not row['path'].startswith(('/__veyra_host', '/__veyra_input')),
                     'Pinned image overlaps temporary tool namespace')
            # Actual complete authenticated input inventories established zero
            # whiteouts in BOTH current locked bases. Reject changed semantics
            # rather than installing unused generic destructive extraction code.
            need(not any(row['type'] == 'whiteout' for row in rows),
                 'Changed pinned base has removals requiring explicit OCI changeset qualification')
            logfile = self.operator.WORK / ('base-' + self.stage + '-' + lock_key + '-' + str(index) + '-' + self.attempt + '-extract.log')
            with logfile.open('xb') as log:
                # The host tar/loader are READ-ONLY extraction tools, never
                # compiler/runtime inputs. Kernel namespace confines absolute
                # archive links to this new original owned filesystem.
                self.sandbox(['/__veyra_host/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2',
                    '--library-path', '/__veyra_host/lib/x86_64-linux-gnu:/__veyra_host/lib',
                    '/__veyra_host/bin/tar', '--extract', '--file=-',
                    '--directory=/', '--numeric-owner', '--same-owner', '--same-permissions',
                    '--xattrs', '--xattrs-include=*', '--acls', '--selinux', '--keep-directory-symlink',
                    '--delay-directory-restore', '--exclude=.wh.*', '--exclude=*/.wh.*'],
                    log, host_tools=True, input_file=path)
            base['layers'].append({key: inventory[key] for key in [
                'compressedDigest', 'compressedBytes', 'diffId', 'entries', 'logicalFileBytes']})
            # Input retirement remains the ORIGINAL terminal/ref/preservation
            # implementation; no raw cleanup bypass is installed here.
            if retained is None:
                self.operator.retire_targets(self.receipt, [path], 'streamed-base-' + self.stage + '-' + lock_key + '-' + str(index) + '-' + self.attempt)
        self.environment = dict(item.split('=', 1) for item in image['config'].get('config', {}).get('Env', []))
        self.config = image['config'].get('config', {}).copy()
        self.proof['bases'].append(base)
        self.record()

    def expand(self, value):
        values = {**self.arguments, **self.environment}
        return re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)\}|\$([A-Za-z_][A-Za-z_0-9]*)',
                      lambda match: values.get(match[1] or match[2], ''), value)

    def copy(self, value, contexts):
        fields = shlex.split(value)
        flags = {}
        while fields and fields[0].startswith('--'):
            key, separator, val = fields.pop(0)[2:].partition('=')
            need(separator and key in {'from', 'chown', 'chmod'}, 'Unsupported original COPY flag')
            flags[key] = val
        need(len(fields) >= 2 and flags.get('chown', 'root:root') == 'root:root',
             'Original root-owned explicit COPY contract required')
        source_root = contexts[flags.get('from', 'source')]
        if 'from' not in flags:
            projection = self.receipt.get('sourceContextProjection', {})
            need(projection.get('completed') is True and projection.get('originalDockerignoreFrontend') is True and
                 projection.get('sourceSha256') == self.report['source']['sourceSha256'] and
                 projection.get('path') == str(source_root) and source_root == self.operator.WORK / 'docker-context',
                 'Source COPY requires original Dockerignore-filtered canonical context, never broader raw APP/context')
        need(source_root.resolve() == source_root and source_root.is_relative_to(self.operator.WORK),
             'Only current original confined source/handoff may be copied')
        destination = self.path(self.expand(fields[-1]))
        hardlinks = {}
        def ensure_directory(path):
            if path.exists():
                need(path.is_dir() and path.resolve().is_relative_to(self.root), 'COPY parent escaped or is not a directory')
                return
            need(path.parent.resolve().is_relative_to(self.root), 'COPY new parent escaped')
            ensure_directory(path.parent)
            mode = int(flags.get('chmod', '0755'), 8)
            path.mkdir(mode=mode)
            os.chown(path, 0, 0)
            os.chmod(path, mode)
        def copied_file(source_name, target_name):
            source_path, target_path = Path(source_name), Path(target_name)
            need(target_path.parent.resolve().is_relative_to(self.root), 'COPY parent resolved outside original filesystem')
            info = source_path.lstat()
            need(stat.S_ISREG(info.st_mode), 'Expected original regular COPY file')
            key = (info.st_dev, info.st_ino)
            temporary = target_path.with_name('.veyra-copy-' + target_path.name)
            need(not temporary.exists() and not temporary.is_symlink(), 'Unresolved COPY temporary must be retained')
            if key in hardlinks:
                os.link(hardlinks[key], temporary, follow_symlinks=False)
            else:
                with source_path.open('rb') as incoming, temporary.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                shutil.copystat(source_path, temporary, follow_symlinks=False)
            os.replace(temporary, target_path)
            hardlinks.setdefault(key, target_path)
            return str(target_path)
        for name in fields[:-1]:
            name = self.expand(name)
            need('..' not in Path(name).parts and not any(char in name for char in '*?['),
                 'Original COPY glob/path needs explicit semantic implementation')
            source = source_root / name.lstrip('/')
            need(source.is_relative_to(source_root) and (source.exists() or source.is_symlink()),
                 'Original COPY input absent')
            target = destination / source.name if (not source.is_dir() and
                (fields[-1].endswith('/') or len(fields) > 2 or destination.is_dir())) else destination
            ensure_directory(target.parent)
            if source.is_dir() and not source.is_symlink():
                # Preflight existing destination directory aliases before
                # copytree can apply metadata to them, including empty dirs.
                for directory, names, _ in os.walk(source, followlinks=False):
                    slot = target / Path(directory).relative_to(source)
                    need(slot.parent.resolve().is_relative_to(self.root), 'COPY directory parent escaped')
                    if slot.exists() and slot.is_dir():
                        need(slot.resolve().is_relative_to(self.root), 'COPY destination directory alias escaped')
                    for child in names:
                        candidate = slot / child
                        if candidate.exists() and candidate.is_dir():
                            need(candidate.resolve().is_relative_to(self.root), 'COPY nested directory alias escaped')
                # BuildKit v0.34.1 pins fsutil83cac42c1c52: CopyDirContents
                # prepares the top destination with0755/original flags and
                # calls copy(...overwriteTargetMetadata=false). Source root
                # ownership/mode/xattrs never replace that existing root.
                # Recursive contained directories do receive source metadata.
                ensure_directory(target)
                root_times = source.stat()
                for child in source.iterdir():
                    slot = target / child.name
                    if child.is_dir() and not child.is_symlink():
                        shutil.copytree(child, slot, symlinks=True, dirs_exist_ok=True,
                                        copy_function=copied_file)
                    elif child.is_symlink():
                        need(not slot.is_dir() or slot.is_symlink(), 'COPY link cannot replace a real directory')
                        if slot.exists() or slot.is_symlink():
                            slot.unlink()
                        slot.symlink_to(os.readlink(child))
                        shutil.copystat(child, slot, follow_symlinks=False)
                    else:
                        copied_file(child, slot)
                # Only copied source members receive --chown/--chmod; earlier
                # unrelated destination children are retained unchanged.
                pairs = [(p, target / p.relative_to(source)) for p in source.rglob('*')]
            else:
                need(target.parent.resolve().is_relative_to(self.root) and not target.is_dir(),
                     'Original COPY file destination is not a confined file slot')
                if source.is_symlink():
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    target.symlink_to(os.readlink(source))
                    shutil.copystat(source, target, follow_symlinks=False)
                else:
                    # Original COPY is allowed to replace the generated private
                    # view (e.g. the canonical Swarm TypeScript contract). Never
                    # follow an existing destination symlink into another tree.
                    copied_file(source, target)
                pairs = [(source, target)]
            for original, path in pairs:
                attrs = {key: os.getxattr(original, key, follow_symlinks=False)
                         for key in os.listxattr(original, follow_symlinks=False)}
                os.chown(path, 0, 0, follow_symlinks=False)
                if not path.is_symlink():
                    os.chmod(path, int(flags['chmod'], 8) if 'chmod' in flags else
                             stat.S_IMODE(original.lstat().st_mode))
                # chown/chmod can clear security.capability; source inode
                # xattrs are applied afterward, as in the pinned fsutil code.
                for key, body in attrs.items():
                    os.setxattr(path, key, body, follow_symlinks=False)
            if source.is_dir() and not source.is_symlink():
                # The pinned existing-root branch restores SOURCE fi times.
                os.utime(target, ns=(root_times.st_atime_ns, root_times.st_mtime_ns))
        self.guard()

    def instruction(self, row, contexts):
        need(not self.closed_probe, 'Closed fixture cannot become an application producer or execute Dockerfile directives')
        self.guard()
        kind, value = row['instruction'], row['value']
        if kind == 'ARG':
            key, has_default, default = value.partition('=')
            if key not in self.arguments and has_default:
                self.arguments[key] = shlex.split(default)[0] if default else ''
        elif kind == 'ENV':
            for item in shlex.split(value):
                key, separator, val = item.partition('=')
                need(separator, 'Unsupported original legacy ENV form')
                self.environment[key] = self.expand(val)
            self.config['Env'] = [key + '=' + value for key, value in self.environment.items()]
        elif kind == 'WORKDIR':
            self.cwd = posixpath.normpath(posixpath.join(self.cwd, self.expand(value)))
            self.path(self.cwd).mkdir(parents=True, exist_ok=True)
            self.config['WorkingDir'] = self.cwd
        elif kind == 'COPY':
            self.copy(value, contexts)
        elif kind == 'RUN':
            need(self.config.get('User', '') in ('', 'root', '0', '0:0'),
                 'Non-root RUN requires original UID/GID resolution before execution')
            attempt_suffix = '' if self.attempt == 'initial' else '-' + self.attempt
            logfile = self.operator.WORK / ('rootfs-' + self.stage + '-run-' + str(self.sequence) + attempt_suffix + '.log')
            with logfile.open('xb') as log:
                self.sandbox(['/bin/sh', '-c', value], log)
        elif kind == 'LABEL':
            for item in shlex.split(value):
                key, separator, val = item.partition('=')
                need(separator, 'Unsupported original legacy LABEL form')
                self.config.setdefault('Labels', {})[key] = self.expand(val)
        elif kind == 'USER':
            self.config['User'] = self.expand(value)
        elif kind in ('CMD', 'ENTRYPOINT'):
            command = json.loads(value)
            need(isinstance(command, list) and all(isinstance(item, str) for item in command),
                 'Original explicit JSON execution metadata required')
            self.config['Entrypoint' if kind == 'ENTRYPOINT' else 'Cmd'] = command
        elif kind == 'EXPOSE':
            for item in shlex.split(value):
                port = self.expand(item)
                self.config.setdefault('ExposedPorts', {})[port if '/' in port else port + '/tcp'] = {}
        elif kind == 'HEALTHCHECK':
            if value == 'NONE':
                self.config['Healthcheck'] = {'Test': ['NONE']}
            else:
                flags, separator, command = value.partition(' CMD ')
                need(separator and command.startswith('['), 'Original explicit JSON healthcheck required')
                health = {'Test': ['CMD', *json.loads(command)]}
                names = {'interval': 'Interval', 'timeout': 'Timeout', 'retries': 'Retries',
                         'start-period': 'StartPeriod', 'start-interval': 'StartInterval'}
                for flag in shlex.split(flags):
                    key, separator, val = flag.removeprefix('--').partition('=')
                    need(flag.startswith('--') and separator and key in names, 'Unknown original healthcheck flag')
                    if key == 'retries':
                        health[names[key]] = int(val)
                    else:
                        duration = re.fullmatch(r'([0-9]+)(ns|us|ms|s|m|h)', val)
                        need(duration is not None, 'Unimplemented original healthcheck duration')
                        health[names[key]] = int(duration[1]) * {
                            'ns': 1, 'us': 1000, 'ms': 1_000_000, 's': 1_000_000_000,
                            'm': 60_000_000_000, 'h': 3_600_000_000_000}[duration[2]]
                self.config['Healthcheck'] = health
        else:
            # Final metadata needs an exact complete config projection by the
            # full orchestrator. Never silently discard an unknown directive.
            raise RuntimeError('Original Dockerfile directive still needs exact implementation: ' + kind)
        self.proof['instructions'].append({'sequence': self.sequence, 'instruction': kind,
            'programSha256': hashlib.sha256(value.encode()).hexdigest(), 'completed': True})
        self.sequence += 1
        self.record()
