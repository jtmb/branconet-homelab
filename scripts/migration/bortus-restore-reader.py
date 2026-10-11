"""One owned inert-holder exec child; program bytes belong exclusively to data.execute."""
import copy
import math
import os
import pathlib
import re
import ssl
import stat
import subprocess
import time

import importlib.util
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mutations = load('bortus_reader_mutations', 'bortus-restore-mutations.py')
credentials = load('bortus_reader_credentials', 'bortus-operator-mtls.py')
data = mutations.data
metadata = mutations.metadata
RUNTIME = pathlib.Path.home() / '.local/share/branconet-migration'
POPEN_TYPE = subprocess.Popen
spawn = subprocess.Popen
FAILURES = ('configuration', 'prerequisite', 'ownership', 'credential', 'deadline',
            'holder', 'no_replay', 'launch', 'child_exit', 'cleanup')


class ReaderRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in FAILURES else 'launch'
        super().__init__('Independent restore reader refused: ' + self.code)


def need(condition, code):
    if not condition:
        raise ReaderRefused(code)


def check_deadline(deadline):
    now = time.monotonic()
    need(type(deadline) in (int, float) and math.isfinite(deadline) and
         now < deadline <= now + 300, 'deadline')


def close_descriptors(descriptors):
    failed = False
    for fd in reversed(descriptors):
        try: os.close(fd)
        except Exception: failed = True
    if failed:
        raise ReaderRefused('cleanup')


def check_pinned(path, fd, identity, anchors):
    need(credentials.fingerprint(os.fstat(fd)) == identity ==
         credentials.fingerprint(path.lstat()), 'credential')
    for location, opened, before in anchors:
        actual, pinned = location.lstat(), os.fstat(opened)
        need(stat.S_ISDIR(actual.st_mode) and (actual.st_dev, actual.st_ino, actual.st_uid,
             stat.S_IMODE(actual.st_mode)) == before ==
             (pinned.st_dev, pinned.st_ino, pinned.st_uid, stat.S_IMODE(pinned.st_mode)), 'credential')


def pin_config(path):
    """Validate the exact inherited source inode, never a newly exported credential file."""
    descriptors, anchors, material = [], [], []
    raw = ca = certificate = key = context = None
    success = False
    try:
        need(type(path) is pathlib.PosixPath and path.is_absolute() and '..' not in path.parts and
             1 < len(path.parts) <= 32 and len(str(path)) <= 1024, 'credential')
        parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        descriptors.append(parent)
        location = pathlib.Path('/')
        for part in path.parts[1:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=parent)
            descriptors.append(parent)
            location /= part
            info = os.fstat(parent)
            mode = stat.S_IMODE(info.st_mode)
            need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and mode & 0o022 == 0,
                 'credential')
            anchors.append((location, parent, (info.st_dev, info.st_ino, info.st_uid, mode)))
        need(os.fstat(parent).st_uid == os.getuid(), 'credential')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent)
        descriptors.append(fd)
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
             stat.S_IMODE(info.st_mode) == 0o600 and 0 < info.st_size <= credentials.MAX_CONFIG_BYTES,
             'credential')
        identity = credentials.fingerprint(info)
        raw = bytearray()
        while len(raw) <= credentials.MAX_CONFIG_BYTES:
            block = os.read(fd, min(16384, credentials.MAX_CONFIG_BYTES - len(raw) + 1))
            if not block: break
            raw.extend(block)
        need(len(raw) == info.st_size, 'credential')
        check_pinned(path, fd, identity, anchors)
        ca, certificate, key = credentials.shape(credentials.parse(bytes(raw)))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cadata=ca.decode('ascii'))
        for pem in (certificate, key): material.append(credentials.memory_file(pem))
        context.load_cert_chain('/proc/self/fd/' + str(material[0]),
                                '/proc/self/fd/' + str(material[1]), password=credentials.no_password)
        check_pinned(path, fd, identity, anchors)
        os.lseek(fd, 0, os.SEEK_SET)
        success = True
        return fd, descriptors, anchors, identity
    finally:
        raw = ca = certificate = key = context = None
        cleanup_failed = False
        try: close_descriptors(material)
        except Exception: cleanup_failed = True
        if not success or cleanup_failed:
            try: close_descriptors(descriptors)
            except Exception: cleanup_failed = True
        if cleanup_failed: raise ReaderRefused('cleanup')


def inert_holder(pod, proposal):
    """Same narrow benign API defaults as the complete restored-consumer fence."""
    data.health.bounded(pod)
    spec = copy.deepcopy(pod.get('spec'))
    need(type(spec) is dict, 'holder')
    for key, value in {'dnsPolicy': 'ClusterFirst', 'schedulerName': 'default-scheduler',
        'terminationGracePeriodSeconds': 30, 'enableServiceLinks': True,
        'serviceAccountName': 'default', 'serviceAccount': 'default',
        'preemptionPolicy': 'PreemptLowerPriority', 'priority': 0}.items():
        if key in spec:
            need(type(spec[key]) is type(value) and spec.pop(key) == value, 'holder')
    if 'tolerations' in spec:
        need(data.health.strict_equal(spec.pop('tolerations'), [
            {'key': 'node.kubernetes.io/not-ready', 'operator': 'Exists',
             'effect': 'NoExecute', 'tolerationSeconds': 300},
            {'key': 'node.kubernetes.io/unreachable', 'operator': 'Exists',
             'effect': 'NoExecute', 'tolerationSeconds': 300}]), 'holder')
    for container in spec.get('containers', []):
        for key, value in {'terminationMessagePath': '/dev/termination-log',
                           'terminationMessagePolicy': 'File'}.items():
            if key in container:
                need(type(container[key]) is str and container.pop(key) == value, 'holder')
    need(data.health.strict_equal(spec, proposal['spec']), 'holder')
    status = pod.get('status', {})
    need(type(status) is dict and not pod['metadata'].get('ownerReferences') and
         status.get('phase') == 'Running' and data.health.ready(status), 'holder')
    states = status.get('containerStatuses')
    need(type(states) is list and len(states) == 1 and type(states[0]) is dict and
         states[0].get('name') == 'holder' and states[0].get('ready') is True and
         type(states[0].get('state', {}).get('running')) is dict and
         states[0].get('image') == proposal['spec']['containers'][0]['image'] and
         type(states[0].get('restartCount')) is int and states[0]['restartCount'] == 0, 'holder')


class ReaderLauncher:
    """Caller supplies the exact mutation interface and reviewed credential source.

    No program is written here. The data step owns stdin delivery, whole-operation
    deadline and closure after a returned child. This helper cleans pre-return failures.
    """
    def __init__(self, mutation_api, kubeconfig_path, options):
        failure = None
        try:
            need(os.name == 'posix' and type(mutation_api) is mutations.MutationAPI and
                 type(options) is credentials.OperatorMTLSOptions and type(kubeconfig_path) is str,
                 'configuration')
            path = pathlib.Path(kubeconfig_path)
            need(path.is_absolute() and '..' not in path.parts and path == options.path, 'configuration')
            self.api, self.collector, self.options, self.kubeconfig = (
                mutation_api, mutation_api.collector, options, path)
            self.readonly = metadata.MetadataAPI(options, origin=metadata.APPROVED_ORIGIN)
            self.proposal = metadata.bounded_json(mutation_api.proposal_bytes['holder_create'])
            self.attempted = False
        except ReaderRefused as error:
            failure = error.code
        except Exception:
            failure = 'configuration'
        if failure:
            raise ReaderRefused(failure)

    def _live_holder(self, holder):
        with self.collector.lock:
            self.collector.prerequisite()
            need(type(holder) is data.health.Identity and holder.namespace == 'bortus' and
                 re.fullmatch(r'bortus-restore-[0-9a-f]{12}', holder.name) and
                 holder.name == self.collector.journal.record['target_name'] and
                 self.collector.state['metadata_eligible'] is True and self.collector.expected is not None,
                 'prerequisite')
            self.collector.journal._owned()
            created = self.collector.journal.record['operations'].get('holder_create', {})
            need(created.get('state') == 'confirmed' and 'holder_delete' not in
                 self.collector.journal.record['operations'] and all(
                     created['identity'][key] == getattr(holder, attr) for key, attr in
                     [('name', 'name'), ('namespace', 'namespace'), ('uid', 'uid')]), 'ownership')

    def _binary(self):
        binary = RUNTIME / 'bin/kubectl'
        need(binary.is_absolute(), 'ownership')
        # No binary or credential contents are logged or copied; fixed executable only.
        location = pathlib.Path('/')
        for part in binary.parts[1:-1]:
            location /= part
            path = location
            info = path.lstat()
            need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and
                 stat.S_IMODE(info.st_mode) & 0o022 == 0, 'ownership')
        info = binary.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
             info.st_nlink == 1 and stat.S_IMODE(info.st_mode) & 0o022 == 0 and
             stat.S_IMODE(info.st_mode) & 0o100, 'ownership')
        return binary

    def _launch(self, holder, deadline):
        child = None
        descriptors = []
        failure = None
        context = pod = None
        try:
            check_deadline(deadline)
            self._live_holder(holder)
            with self.collector.lock:
                need(not self.attempted, 'no_replay')
                self.attempted = True
            binary = self._binary()
            need(self.options.path == self.kubeconfig, 'credential')
            # Parse/load TLS material from precisely the inode inherited by kubectl.
            config_fd, descriptors, anchors, identity = pin_config(self.kubeconfig)
            check_deadline(deadline)
            pod = self.readonly.get('pod', holder.name, deadline=deadline)
            actual = data.health.identity(pod, 'bortus')
            need(actual == holder and pod['metadata'].get('labels', {}).get('bortus-restore') ==
                 self.collector.journal.record['run_id'], 'holder')
            inert_holder(pod, self.proposal)
            pod = None
            self._live_holder(holder)
            check_deadline(deadline)
            check_pinned(self.kubeconfig, config_fd, identity, anchors)
            need(self.options.path == self.kubeconfig, 'credential')
            # No program, database values or credential contents appear in argv/env.
            args = [str(binary), '--kubeconfig', '/proc/self/fd/' + str(config_fd),
                    '--request-timeout=' + format(deadline - time.monotonic(), '.6f') + 's',
                    '-n', 'bortus', 'exec', holder.name, '-c', 'holder', '-i', '--', 'node', '-']
            child = spawn(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
                pass_fds=(config_fd,),
                env={'HOME': str(pathlib.Path.home()), 'PATH': str(RUNTIME / 'bin') + ':/usr/bin:/bin',
                     'LANG': 'C.UTF-8'})
            need(type(child) is POPEN_TYPE and child.stdin is not None and child.stdout is not None
                 and child.stderr is None, 'launch')
            need(child.poll() is None, 'child_exit')
            self._live_holder(holder)
            check_deadline(deadline)
        except ReaderRefused as error:
            failure = error.code
        except credentials.AdapterRefused:
            failure = 'credential'
        except (metadata.MetadataRefused, data.health.Refused):
            failure = 'holder'
        except data.watch.WatchRefused:
            failure = 'prerequisite'
        except Exception:
            failure = 'launch'
        finally:
            context = pod = None
            try: close_descriptors(descriptors)
            except Exception: failure = 'cleanup'
        if failure is not None and child is not None:
            # Every closure is attempted even if stopping or another stream refuses.
            try:
                data.archive.stop_owned(child)
            except Exception:
                failure = 'cleanup'
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    try: stream.close()
                    except Exception: failure = 'cleanup'
            child = None
        return child, failure

    def launch_reader(self, holder, deadline):
        child, failure = self._launch(holder, deadline)
        if failure:
            raise ReaderRefused(failure)
        return child
