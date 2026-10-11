"""Fresh TLS, scoped read-only metadata for the independent restore executor."""
import http.client
import json
import math
import re
import ssl
import time
from urllib.parse import urlsplit

APPROVED_ORIGIN = 'https://192.168.0.4:6443'
MAX_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 10000
LONGHORN = '/apis/longhorn.io/v1beta2/namespaces/longhorn-system/'
RESOURCES = {
    'storageclass': ('/apis/storage.k8s.io/v1/storageclasses', 'storage.k8s.io/v1', 'StorageClass', ''),
    'deployment': ('/apis/apps/v1/namespaces/bortus/deployments', 'apps/v1', 'Deployment', 'bortus'),
    'replicaset': ('/apis/apps/v1/namespaces/bortus/replicasets', 'apps/v1', 'ReplicaSet', 'bortus'),
    'helmrelease': ('/apis/helm.toolkit.fluxcd.io/v2/namespaces/flux-system/helmreleases', 'helm.toolkit.fluxcd.io/v2', 'HelmRelease', 'flux-system'),
    'kustomization': ('/apis/kustomize.toolkit.fluxcd.io/v1/namespaces/flux-system/kustomizations', 'kustomize.toolkit.fluxcd.io/v1', 'Kustomization', 'flux-system'),
    'claim': ('/api/v1/namespaces/bortus/persistentvolumeclaims', 'v1', 'PersistentVolumeClaim', 'bortus'),
    'pv': ('/api/v1/persistentvolumes', 'v1', 'PersistentVolume', ''),
    'node': ('/api/v1/nodes', 'v1', 'Node', ''),
    'pod': ('/api/v1/namespaces/bortus/pods', 'v1', 'Pod', 'bortus'),
    'volume': (LONGHORN + 'volumes', 'longhorn.io/v1beta2', 'Volume', 'longhorn-system'),
    'backup': (LONGHORN + 'backups', 'longhorn.io/v1beta2', 'Backup', 'longhorn-system'),
    'snapshot': (LONGHORN + 'snapshots', 'longhorn.io/v1beta2', 'Snapshot', 'longhorn-system'),
    'backuptarget': (LONGHORN + 'backuptargets', 'longhorn.io/v1beta2', 'BackupTarget', 'longhorn-system'),
    'engine': (LONGHORN + 'engines', 'longhorn.io/v1beta2', 'Engine', 'longhorn-system'),
    'replica': (LONGHORN + 'replicas', 'longhorn.io/v1beta2', 'Replica', 'longhorn-system'),
}
LISTABLE = frozenset(('pv', 'pod', 'engine', 'replica', 'storageclass', 'claim'))


class MetadataRefused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Restore metadata refused: ' + code)


def need(condition, code):
    if not condition:
        raise MetadataRefused(code)


def text(value, maximum=256):
    return type(value) is str and 0 < len(value) <= maximum and all(ord(c) >= 32 for c in value)


def valid_name(value):
    return type(value) is str and 0 < len(value) <= 253 and all(
        len(label) <= 63 and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label)
        for label in value.split('.'))


def bounded_json(raw):
    def unique(pairs):
        need(len(pairs) == len({key for key, _ in pairs}), 'metadata_json')
        return dict(pairs)
    def invalid(_):
        raise MetadataRefused('metadata_json')
    obj = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=unique, parse_constant=invalid)
    stack, nodes = [(obj, 0)], 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        need(nodes <= 400000 and depth <= 32, 'metadata_bound')
        if type(value) is dict:
            stack.extend((v, depth + 1) for pair in value.items() for v in pair)
        elif type(value) is list:
            stack.extend((v, depth + 1) for v in value)
        elif type(value) is str:
            need(len(value) <= 65536, 'metadata_bound')
    return obj


def object_identity(obj, resource, expected_name=None):
    _, version, kind, namespace = RESOURCES[resource]
    need(type(obj) is dict and obj.get('apiVersion') == version and obj.get('kind') == kind,
         'metadata_shape')
    meta = obj.get('metadata')
    need(type(meta) is dict and valid_name(meta.get('name')) and text(meta.get('uid')) and
         text(meta.get('resourceVersion')) and meta.get('namespace', '') == namespace and
         (expected_name is None or meta['name'] == expected_name), 'metadata_identity')
    return meta['name'], meta['uid']


class MetadataAPI:
    """Only fixed metadata GETs. No secrets, mutations, proxies, retries or credential pool."""
    def __init__(self, options, *, origin=APPROVED_ORIGIN):
        need(type(origin) is str and origin == APPROVED_ORIGIN and callable(options), 'configuration')
        parsed = urlsplit(origin)
        need(parsed.scheme == 'https', 'configuration')
        self.host, self.port, self.options = parsed.hostname, parsed.port or 443, options

    def _request(self, path, resource, name, deadline):
        connection = response = headers = raw = transport_socket = None
        failure, value = None, None
        try:
            now = time.monotonic()
            need(type(deadline) in (int, float) and math.isfinite(deadline) and
                 now < deadline <= now + 300, 'deadline')
            context, headers = self.options()  # Fresh externally supplied credentials for this request only.
            need(type(context) is ssl.SSLContext and context.check_hostname and
                 context.verify_mode == ssl.CERT_REQUIRED and
                 context.minimum_version >= ssl.TLSVersion.TLSv1_2 and type(headers) is dict and
                 set(headers) <= {'Authorization'} and all(text(v, 16384) and
                 all(32 <= ord(c) < 127 for c in v) for v in headers.values()), 'tls_configuration')
            connection = http.client.HTTPSConnection(self.host, self.port, context=context,
                timeout=min(30, deadline - time.monotonic()))
            connection.connect()
            transport_socket = connection.sock
            need(isinstance(connection.sock, ssl.SSLSocket) and connection.sock.getpeercert() and
                 connection.sock.version() in ('TLSv1.2', 'TLSv1.3'), 'tls_verification')
            need(time.monotonic() < deadline, 'deadline')
            transport_socket.settimeout(min(30, deadline - time.monotonic()))
            connection.request('GET', path, headers={'Accept': 'application/json',
                'Accept-Encoding': 'identity', **headers})
            headers = None
            need(time.monotonic() < deadline, 'deadline')
            connection.sock.settimeout(min(30, deadline - time.monotonic()))
            response = connection.getresponse()
            need(response.status == 200 and response.getheader('Content-Type', '').split(';', 1)[0].strip()
                 == 'application/json' and response.getheader('Content-Encoding', 'identity') == 'identity',
                 'metadata_response')
            declared = response.getheader('Content-Length')
            need(declared is None or (declared.isascii() and declared.isdecimal() and
                                     int(declared) <= MAX_BYTES), 'metadata_bound')
            parts, count = [], 0
            while True:
                need(time.monotonic() < deadline, 'deadline')
                # read1 performs at most one underlying read; slow trickles cannot
                # restart a full timeout repeatedly within an unbounded read().
                transport_socket.settimeout(min(30, deadline - time.monotonic()))
                block = response.read1(min(65536, MAX_BYTES - count + 1))
                count += len(block)
                need(time.monotonic() < deadline, 'deadline')
                need(count <= MAX_BYTES, 'metadata_bound')
                if not block:
                    break
                parts.append(block)
                if response.isclosed():
                    break
            need(declared is None or count == int(declared), 'metadata_response')
            raw = b''.join(parts)
            obj = bounded_json(raw)
            if name is not None:
                object_identity(obj, resource, name)
            else:
                _, version, kind, _ = RESOURCES[resource]
                meta = obj.get('metadata') if type(obj) is dict else None
                items = obj.get('items') if type(obj) is dict else None
                need(type(obj) is dict and obj.get('apiVersion') == version and
                     obj.get('kind') == kind + 'List' and type(meta) is dict and
                     text(meta.get('resourceVersion')) and meta.get('continue', '') == '' and
                     ('remainingItemCount' not in meta or type(meta['remainingItemCount']) is int and
                      meta['remainingItemCount'] == 0) and type(items) is list and len(items) <= MAX_ITEMS,
                     'metadata_incomplete')
                # A validated typed collection supplies only omitted item TypeMeta.
                # Named GETs and explicitly supplied conflicting headers stay strict.
                normalized = []
                for item in items:
                    need(type(item) is dict, 'metadata_shape')
                    item = dict(item)
                    item.setdefault('apiVersion', version)
                    item.setdefault('kind', kind)
                    normalized.append(item)
                identities = [object_identity(item, resource) for item in normalized]
                need(len({e[0] for e in identities}) == len(items) and
                     len({e[1] for e in identities}) == len(items), 'metadata_identity')
                obj['items'] = normalized
            need(time.monotonic() < deadline, 'deadline')
            value = obj
        except MetadataRefused as error:
            failure = error.code
        except (ValueError, UnicodeError, RecursionError):
            failure = 'metadata_json'
        except Exception:
            failure = 'metadata_transport'
        finally:
            for owned in (response, connection):
                if owned is not None:
                    try:
                        owned.close()
                    except Exception:
                        failure = 'metadata_transport'
            headers = raw = None
        # Returning a code drops parser/body/error frames before the public refusal is raised.
        return (None if failure else value), failure

    def get(self, resource, name, *, deadline):
        need(type(resource) is str and resource in RESOURCES and valid_name(name), 'request_scope')
        value, failure = self._request(RESOURCES[resource][0] + '/' + name, resource, name, deadline)
        if failure:
            raise MetadataRefused(failure)
        return value

    def list(self, resource, *, deadline):
        need(type(resource) is str and resource in LISTABLE, 'request_scope')
        value, failure = self._request(RESOURCES[resource][0], resource, None, deadline)
        if failure:
            raise MetadataRefused(failure)
        return value
