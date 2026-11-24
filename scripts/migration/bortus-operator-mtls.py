"""Fresh embedded-only operator mTLS options; no CLI, live reads or credential cache."""
import base64
import fcntl
import os
import pathlib
import re
import ssl
import stat

import yaml


APPROVED_ORIGIN = 'https://192.168.0.4:6443'
MAX_CONFIG_BYTES = 65536
MAX_PEM_BYTES = 16384
MAX_YAML_EVENTS = 4096
MAX_YAML_DEPTH = 12


class AdapterRefused(RuntimeError):
    """Fixed public code only; never retain YAML, TLS, key or filesystem errors."""
    def __init__(self, code):
        self.code = code
        super().__init__('Operator mTLS adapter refused: ' + code)


def require(ok, code):
    if not ok: raise AdapterRefused(code)


def name(value):
    # These are kubeconfig identifiers, including kubeadm's user@cluster context,
    # not DNS names or filesystem paths.
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9_.@-]{1,253}', value) is not None


class ClosedLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        require(isinstance(node, yaml.MappingNode), 'yaml_shape')
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            require(type(key) is str and key not in result, 'yaml_duplicate')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse(raw):
    """Bound events/depth and refuse aliases/anchors/tags before construction."""
    try:
        text = raw.decode('utf-8', errors='strict')
        depth = documents = 0
        for count, event in enumerate(yaml.parse(text), 1):
            require(count <= MAX_YAML_EVENTS, 'yaml_bound')
            require(not isinstance(event, yaml.AliasEvent) and
                    getattr(event, 'anchor', None) is None and getattr(event, 'tag', None) is None,
                    'yaml_reference')
            if isinstance(event, yaml.DocumentStartEvent): documents += 1
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1; require(depth <= MAX_YAML_DEPTH, 'yaml_bound')
            if isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)): depth -= 1
        require(documents == 1 and depth == 0, 'yaml_shape')
        obj = yaml.load(text, Loader=ClosedLoader)
        require(type(obj) is dict, 'yaml_shape')
        return obj
    except AdapterRefused:
        raise
    except Exception:
        raise AdapterRefused('yaml_shape') from None


def embedded(value, key=False):
    try:
        require(type(value) is str and 0 < len(value) <= 4 * ((MAX_PEM_BYTES + 2) // 3), 'pem_bound')
        raw = base64.b64decode(value, validate=True)
        require(0 < len(raw) <= MAX_PEM_BYTES and base64.b64encode(raw).decode('ascii') == value, 'pem_bound')
        text = raw.decode('ascii')
        if key:
            # No encrypted PKCS8, legacy PEM encryption or interactive password path.
            require(re.fullmatch(r'\s*-----BEGIN (PRIVATE KEY|RSA PRIVATE KEY|EC PRIVATE KEY)-----\s+'
                r'[A-Za-z0-9+/=\s]+-----END \1-----\s*', text) is not None, 'key_format')
        else:
            require(re.fullmatch(r'(?:\s*-----BEGIN CERTIFICATE-----\s+'
                r'[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----\s*)+', text) is not None, 'certificate_format')
        return raw
    except AdapterRefused:
        raise
    except Exception:
        raise AdapterRefused('pem_format') from None


def shape(obj):
    require(set(obj) == {'apiVersion', 'kind', 'clusters', 'contexts', 'current-context', 'users'} and
            obj['apiVersion'] == 'v1' and obj['kind'] == 'Config', 'config_shape')
    entries = {}
    for plural, singular in [('clusters', 'cluster'), ('contexts', 'context'), ('users', 'user')]:
        values = obj[plural]
        require(type(values) is list and len(values) == 1 and type(values[0]) is dict and
                set(values[0]) == {'name', singular} and name(values[0]['name']) and
                type(values[0][singular]) is dict, 'config_shape')
        entries[singular] = values[0]
    cluster, context, user = [entries[k][k] for k in ('cluster', 'context', 'user')]
    require(name(obj['current-context']) and obj['current-context'] == entries['context']['name'] and
            set(context) == {'cluster', 'user'} and context['cluster'] == entries['cluster']['name'] and
            context['user'] == entries['user']['name'], 'context_shape')
    require(set(cluster) == {'server', 'certificate-authority-data'} and
            cluster['server'] == APPROVED_ORIGIN, 'cluster_shape')
    require(set(user) == {'client-certificate-data', 'client-key-data'}, 'user_shape')
    return (embedded(cluster['certificate-authority-data']),
            embedded(user['client-certificate-data']), embedded(user['client-key-data'], key=True))


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def close_owned(descriptors):
    failed = False
    for fd in reversed(descriptors):
        try: os.close(fd)
        except Exception: failed = True
    if failed: raise AdapterRefused('descriptor_cleanup') from None


def read_fresh(path):
    """Pin every parent without following links; verify path/inode after bounded read."""
    descriptors = []
    try:
        require(os.name == 'posix' and hasattr(os, 'memfd_create') and
                type(path) is pathlib.PosixPath and path.is_absolute() and
                1 < len(path.parts) <= 32 and len(str(path)) <= 1024 and
                all(part not in ('.', '..') for part in path.parts[1:]), 'source_path')
        root = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        descriptors.append(root)
        chain = []
        for part in path.parts[1:-1]:
            parent = descriptors[-1]
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            descriptors.append(fd); info = os.fstat(fd)
            require(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and
                    stat.S_IMODE(info.st_mode) & 0o022 == 0, 'source_parent')
            chain.append((parent, part, fingerprint(info), fd))
        parent = descriptors[-1]
        require(os.fstat(parent).st_uid == os.getuid() and
                stat.S_IMODE(os.fstat(parent).st_mode) & 0o022 == 0, 'source_parent')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        descriptors.append(fd); initial = os.fstat(fd)
        require(stat.S_ISREG(initial.st_mode) and initial.st_uid == os.getuid() and
                stat.S_IMODE(initial.st_mode) == 0o600 and initial.st_nlink == 1 and
                0 < initial.st_size <= MAX_CONFIG_BYTES, 'source_file')
        parts, count = [], 0
        while True:
            data = os.read(fd, min(16384, MAX_CONFIG_BYTES - count + 1))
            count += len(data); require(count <= MAX_CONFIG_BYTES, 'source_bound')
            if not data: break
            parts.append(data)
        require(count == initial.st_size and fingerprint(os.fstat(fd)) == fingerprint(initial) and
                fingerprint(os.stat(path.name, dir_fd=parent, follow_symlinks=False)) == fingerprint(initial),
                'source_changed')
        for parent_fd, part, before, opened in chain:
            require(fingerprint(os.fstat(opened)) == before and
                    fingerprint(os.stat(part, dir_fd=parent_fd, follow_symlinks=False)) == before,
                    'source_changed')
        return b''.join(parts)
    except AdapterRefused:
        raise
    except Exception:
        raise AdapterRefused('source_read') from None
    finally:
        close_owned(descriptors)


def no_password():
    raise AdapterRefused('key_encrypted')


def memory_file(raw):
    fd = os.memfd_create('bortus-owned-mtls', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        os.fchmod(fd, 0o600)
        remaining = memoryview(raw)
        while remaining:
            written = os.write(fd, remaining)
            require(written > 0, 'memfd_write')
            remaining = remaining[written:]
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                    fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        return fd
    except Exception:
        close_owned([fd])
        raise


class OperatorMTLSOptions:
    """Callable stores only caller-reviewed absolute source path, never credential bytes."""
    def __init__(self, approved_path):
        require(type(approved_path) is str and len(approved_path) <= 1024, 'source_path')
        self.path = pathlib.Path(approved_path)

    def __call__(self):
        descriptors = []
        failure = None
        result = None
        ca = certificate = key = raw = context = None
        try:
            ca, certificate, key = shape(parse(read_fresh(self.path)))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_verify_locations(cadata=ca.decode('ascii'))
            for raw in (certificate, key): descriptors.append(memory_file(raw))
            context.load_cert_chain('/proc/self/fd/' + str(descriptors[0]),
                                    '/proc/self/fd/' + str(descriptors[1]), password=no_password)
            result = (context, {})
        except AdapterRefused as error:
            failure = error.code
        except Exception:
            failure = 'tls_material'
        finally:
            try: close_owned(descriptors)
            except AdapterRefused as error: failure = error.code
            # Reference release is not a claim of Python heap zeroization. No
            # private material is attached to the public exception traceback.
            ca = certificate = key = raw = context = None
        # Outside handlers: from None alone suppresses display but retains the
        # original exception in __context__, including YAML input mark buffers.
        if failure is not None:
            result = None
            raise AdapterRefused(failure) from None
        return result
