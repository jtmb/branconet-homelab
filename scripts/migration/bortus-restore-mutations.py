"""Dispatch-once scoped restore mutations; no CLI, retries or live acceptance."""
import copy
import hashlib
import http.client
import json
import math
import ssl
import time

import importlib.util
import pathlib
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The coordinator must construct its Collector through this exact exported interface.
data = load('bortus_mutation_data', 'bortus-restore-data.py')
metadata = load('bortus_mutation_metadata', 'bortus-restore-metadata.py')
preflight = load('bortus_mutation_preflight', 'inspect-bortus-independent-restore.py')
CREATE = {'storageclass_create': 'storageclass', 'claim_create': 'claim', 'holder_create': 'pod'}
MAX_REQUEST = 65536
FAILURES = ('configuration', 'proposal', 'ownership', 'prerequisite', 'no_replay',
            'request_scope', 'deadline', 'tls_configuration', 'tls_verification',
            'mutation_transport', 'mutation_response', 'mutation_identity', 'mutation_bound')


class MutationRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in FAILURES else 'mutation_transport'
        super().__init__('Restore mutation refused: ' + self.code)


def need(condition, code):
    if not condition:
        raise MutationRefused(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def proposal_bytes(value):
    stack, nodes, characters = [(value, 0)], 0, 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        need(nodes <= 512 and depth <= 16, 'proposal')
        if type(item) is dict:
            need(len(item) <= 64 and all(type(k) is str for k in item), 'proposal')
            stack.extend((v, depth + 1) for pair in item.items() for v in pair)
        elif type(item) is list:
            need(len(item) <= 64, 'proposal')
            stack.extend((v, depth + 1) for v in item)
        elif type(item) is str:
            characters += len(item)
            need(len(item) <= 4096 and characters <= MAX_REQUEST, 'proposal')
        else:
            need(type(item) in (bool, int, type(None)) and
                 (type(item) is not int or -2147483648 <= item <= 2147483647), 'proposal')
    raw = canonical(value)
    need(len(raw) <= MAX_REQUEST, 'proposal')
    return raw


class MutationAPI:
    """One initially empty journal, reviewed proposals and actual live Collector only.

    Returned create identity is NOT admitted-spec proof. DELETE is only a submitted
    acknowledgment; the coordinator must subsequently observe the owned UID absent.
    """
    def __init__(self, collector, options, proposals):
        failure = self._initialize(collector, options, proposals)
        if failure:
            raise MutationRefused(failure)

    def _initialize(self, collector, options, proposals):
        try:
            need(type(collector) is data.watch.Collector and
                 type(collector.journal) is data.watch.WatchJournal and callable(options), 'configuration')
            with collector.lock:
                collector.prerequisite()
                journal = collector.journal
                need(journal.record['operations'] == {}, 'no_replay')
                raw = proposal_bytes(proposals)
                need(len(raw) <= MAX_REQUEST and type(proposals) is list and len(proposals) == 3 and
                     hashlib.sha256(raw).hexdigest() == journal.record['reviewed_proposal_sha256'], 'proposal')
                proposals = metadata.bounded_json(raw)
                name, run = journal.record['target_name'], journal.record['run_id']
                labels = {'bortus-restore': run}
                source = collector.source
                preflight.url_matches(source.backup_url, source.backup.name, source.original_volume_handle)
                holder = proposals[2]
                image = holder['spec']['containers'][0]['image']
                node = holder['spec']['nodeName']
                need(preflight.cold.valid_digest(image) and metadata.valid_name(node), 'proposal')
                expected = [
                    {'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
                     'metadata': {'name': name, 'labels': labels}, 'provisioner': 'driver.longhorn.io',
                     'reclaimPolicy': 'Retain', 'volumeBindingMode': 'Immediate',
                     'allowVolumeExpansion': True,
                     'parameters': dict(preflight.PARAMETERS, fromBackup=source.backup_url)},
                    {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
                     'metadata': {'name': name, 'namespace': 'bortus', 'labels': labels,
                                  'annotations': {'helm.sh/resource-policy': 'keep'}},
                     'spec': {'storageClassName': name, 'accessModes': ['ReadWriteOnce'],
                              'resources': {'requests': {'storage': '1Gi'}}}},
                    {'apiVersion': 'v1', 'kind': 'Pod',
                     'metadata': {'name': name, 'namespace': 'bortus', 'labels': labels},
                     'spec': data.health.holder_spec(image, name, node)}]
                # Canonical JSON distinguishes booleans from integer lookalikes.
                need(raw == canonical(expected), 'proposal')
                self.collector, self.options = collector, options
                self.proposals = dict(zip(CREATE, copy.deepcopy(proposals)))
                self.proposal_bytes = {action: canonical(p) for action, p in self.proposals.items()}
                self.proposal_sha = journal.record['reviewed_proposal_sha256']
                self.lease = collector.state['lease_id']
                self.dispatched = set()
                self.readonly = metadata.MetadataAPI(options, origin=metadata.APPROVED_ORIGIN)
            return None
        except MutationRefused as error:
            return error.code
        except Exception:
            return 'proposal'

    def _pending(self, action, intent, *, dispatch, already_dispatched=False):
        with self.collector.lock:
            try:
                self.collector.prerequisite()
            except Exception:
                raise MutationRefused('prerequisite') from None
            journal = self.collector.journal
            need(self.collector.state['lease_id'] == self.lease and
                 journal.record['reviewed_proposal_sha256'] == self.proposal_sha, 'ownership')
            journal._owned()
            raw, inode = journal._file('journal.json')
            record = json.loads(raw, object_pairs_hook=data.watch.ownership.unique_object)
            data.watch.ownership.validate_record(record)
            need(inode == journal.journal_inode and canonical(record) == canonical(journal.record), 'ownership')
            pending = record['operations'].get(action)
            need(type(intent) is dict and pending is not None and pending['state'] == 'pending' and
                 canonical(pending) == proposal_bytes(intent), 'ownership')
            if action in CREATE:
                need(sum(x['action'] == action for x in self.collector.state['authorizations']) == 1,
                     'prerequisite')
            need((action in self.dispatched) == already_dispatched, 'no_replay')
            if dispatch:
                # Record once BEFORE options/connect/request; a failed attempt never retries.
                self.dispatched.add(action)

    def _live(self):
        try:
            self.collector.prerequisite()
        except Exception:
            raise MutationRefused('prerequisite') from None

    def _project(self, obj, resource, name):
        metadata.object_identity(obj, resource, name)
        ns = metadata.RESOURCES[resource][3] or None
        ident = data.health.identity(obj, ns)
        meta = obj['metadata']
        need(type(meta.get('labels')) is dict and
             meta['labels'].get('bortus-restore') == self.collector.journal.record['run_id'], 'mutation_identity')
        return {'apiVersion': obj['apiVersion'], 'kind': obj['kind'], 'metadata': {
            'name': ident.name, **({'namespace': ns} if ns else {}), 'uid': ident.uid,
            'resourceVersion': ident.resource_version,
            'labels': {'bortus-restore': self.collector.journal.record['run_id']}}}

    def _acknowledge(self, obj, intent):
        owned = intent['preconditions']
        if type(obj) is dict and obj.get('apiVersion') == 'v1' and obj.get('kind') == 'Pod':
            metadata.object_identity(obj, 'pod', owned['name'])
            need(obj['metadata']['uid'] == owned['uid'], 'mutation_identity')
        else:
            need(type(obj) is dict and obj.get('apiVersion') == 'v1' and obj.get('kind') == 'Status' and
                 obj.get('status') == 'Success' and type(obj.get('details')) is dict, 'mutation_response')
            details = obj['details']
            need(details.get('name') == owned['name'] and details.get('uid') == owned['uid'] and
                 details.get('kind') == 'pods' and details.get('group', '') == '', 'mutation_identity')
        return {'submitted': True, 'name': owned['name'], 'namespace': 'bortus', 'uid': owned['uid'],
                'deletion_observed': False}

    def _transport(self, method, path, body, deadline, project):
        connection = response = headers = raw = transport_socket = None
        value, failure = None, None
        try:
            now = time.monotonic()
            need(type(deadline) in (int, float) and math.isfinite(deadline) and
                 now < deadline <= now + 300, 'deadline')
            wire = canonical(body)
            need(len(wire) <= MAX_REQUEST, 'mutation_bound')
            context, headers = self.options()
            need(type(context) is ssl.SSLContext and context.check_hostname and
                 context.verify_mode == ssl.CERT_REQUIRED and
                 context.minimum_version >= ssl.TLSVersion.TLSv1_2 and type(headers) is dict and
                 set(headers) <= {'Authorization'} and all(metadata.text(v, 16384) and
                 all(32 <= ord(c) < 127 for c in v) for v in headers.values()), 'tls_configuration')
            self._live()
            need(time.monotonic() < deadline, 'deadline')
            connection = http.client.HTTPSConnection(self.readonly.host, self.readonly.port,
                context=context, timeout=min(30, deadline - time.monotonic()))
            connection.connect()
            transport_socket = connection.sock
            need(isinstance(transport_socket, ssl.SSLSocket) and transport_socket.getpeercert() and
                 transport_socket.version() in ('TLSv1.2', 'TLSv1.3'), 'tls_verification')
            self._live()
            need(time.monotonic() < deadline, 'deadline')
            transport_socket.settimeout(min(30, deadline - time.monotonic()))
            connection.request(method, path, body=wire, headers={'Content-Type': 'application/json',
                'Accept': 'application/json', 'Accept-Encoding': 'identity', **headers})
            headers = None
            need(time.monotonic() < deadline, 'deadline')
            transport_socket.settimeout(min(30, deadline - time.monotonic()))
            response = connection.getresponse()
            need(response.status in ((201,) if method == 'POST' else (200, 202)) and
                 response.getheader('Content-Type', '').split(';', 1)[0].strip() == 'application/json' and
                 response.getheader('Content-Encoding', 'identity') == 'identity', 'mutation_response')
            declared = response.getheader('Content-Length')
            need(declared is None or (declared.isascii() and declared.isdecimal() and
                 int(declared) <= metadata.MAX_BYTES), 'mutation_bound')
            parts, count = [], 0
            while True:
                need(time.monotonic() < deadline, 'deadline')
                transport_socket.settimeout(min(30, deadline - time.monotonic()))
                block = response.read1(min(65536, metadata.MAX_BYTES - count + 1))
                count += len(block)
                need(time.monotonic() < deadline, 'deadline')
                need(count <= metadata.MAX_BYTES, 'mutation_bound')
                if not block:
                    break
                parts.append(block)
                if response.isclosed():
                    break
            need(declared is None or count == int(declared), 'mutation_response')
            raw = b''.join(parts)
            value = project(metadata.bounded_json(raw))
            self._live()
            need(time.monotonic() < deadline, 'deadline')
        except MutationRefused as error:
            failure = error.code
        except (metadata.MetadataRefused, data.health.Refused):
            failure = 'mutation_identity'
        except (ValueError, UnicodeError, RecursionError):
            failure = 'mutation_response'
        except Exception:
            failure = 'mutation_transport'
        finally:
            for owned in (response, connection):
                if owned is not None:
                    try:
                        owned.close()
                    except Exception:
                        failure = 'mutation_transport'
            headers = raw = None
        if failure is None:
            try:
                self._live()
            except Exception:
                failure = 'prerequisite'
        # Never return a value alongside closure failure or preserve private error frames.
        return (None if failure else value), failure

    def _execute(self, action, intent, deadline):
        try:
            need(type(action) is str and action in set(CREATE) | {'holder_delete'}, 'request_scope')
            if action in CREATE:
                self._pending(action, intent, dispatch=True)
                resource = CREATE[action]
                body = metadata.bounded_json(self.proposal_bytes[action])
                return self._transport('POST', metadata.RESOURCES[resource][0], body,
                    deadline, lambda obj: self._project(obj, resource, intent['name']))
            self._pending(action, intent, dispatch=True)
            current = self.readonly.get('pod', intent['name'], deadline=deadline)
            self._live()
            actual = self._project(current, 'pod', intent['name'])['metadata']
            expected = intent['preconditions']
            need(all(actual[k] == expected[k] for k in ('name', 'namespace', 'uid', 'resourceVersion')),
                 'mutation_identity')
            # Recheck durable pending after the fresh GET, without rearming dispatch.
            self._pending(action, intent, dispatch=False, already_dispatched=True)
            return self._transport('DELETE', metadata.RESOURCES['pod'][0] + '/' + intent['name'],
                {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                 'preconditions': {'uid': expected['uid'], 'resourceVersion': expected['resourceVersion']}},
                deadline, lambda obj: self._acknowledge(obj, intent))
        except MutationRefused as error:
            return None, error.code
        except Exception:
            return None, 'ownership'

    def create(self, action, intent, *, deadline):
        if type(action) is not str or action not in CREATE:
            raise MutationRefused('request_scope')
        value, failure = self._execute(action, intent, deadline)
        if failure:
            raise MutationRefused(failure)
        return value

    def delete(self, intent, *, deadline):
        value, failure = self._execute('holder_delete', intent, deadline)
        if failure:
            raise MutationRefused(failure)
        return value
