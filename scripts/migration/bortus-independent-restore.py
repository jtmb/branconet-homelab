"""Callable bounded restore composition; no CLI or self-granted live acceptance."""
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import stat
import sys
import time
from typing import NamedTuple


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reader = load('independent_restore_reader', 'bortus-restore-reader.py')
source = load('independent_restore_source', 'bortus-restore-source.py')
admitted = load('independent_restore_admitted', 'bortus-restore-admitted.py')
mutations, data, watch, health = reader.mutations, reader.data, reader.data.watch, reader.data.health
FAILURES = ('configuration', 'deadline', 'source', 'qualification', 'ownership', 'watch',
            'create', 'binding', 'completion', 'health', 'data', 'delete', 'cleanup', 'receipt')
SOURCE_FILES = ('bortus-independent-restore.py', 'bortus-restore-reader.py',
    'bortus-restore-source.py', 'bortus-restore-admitted.py', 'bortus-restore-mutations.py',
    'bortus-restore-data.py', 'bortus-restore-watch.py', 'bortus-restore-journal.py',
    'bortus-restored-consumer-fence.py', 'bortus-restore-completion.py',
    'bortus-restore-metadata.py', 'bortus-operator-mtls.py', 'inspect-bortus-checkpoint.py',
    'inspect-bortus-independent-restore.py', 'bortus-sqlite-archive.py',
    'normalize-bortus-sqlite-archive.py', 'compare-bortus-databases.py')


class RestoreRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in FAILURES else 'configuration'
        super().__init__('Independent restore coordinator refused: ' + self.code)


class RestoreResult(NamedTuple):
    run_id: str
    receipt_basename: str = 'restore-receipt.json'
    coordinator_completed: bool = True
    whole_row_preservation_checked: bool = True
    owned_holder_absence_checked: bool = True
    overall_live_restore_acceptance: bool = False
    image_runtime_admission_acceptance: bool = False


def need(value, code):
    if not value:
        raise RestoreRefused(code)


def deadline_check(deadline):
    now = time.monotonic()
    need(type(deadline) in (int, float) and math.isfinite(deadline) and
         now < deadline <= now + 300, 'deadline')


def source_bindings():
    bindings = {}
    for name in SOURCE_FILES:
        raw = pathlib.Path(__file__).with_name(name).read_bytes()
        need(0 < len(raw) <= 1024 * 1024, 'configuration')
        bindings[name] = hashlib.sha256(raw).hexdigest()
    return bindings


def selected(identity):
    return {key: value for key, value in identity.items() if key in ('name', 'namespace', 'uid')}


def qualified(value, image, target, source_node, alternate_node):
    health.bounded(value)
    need(type(value) is dict and set(value) == {'holder_image', 'source_commit', 'config_image_id',
        'node_names', 'protected_claim_names', 'qualification_receipt_sha256',
        'admission_receipt_sha256', 'current_validation'}, 'qualification')
    need(value['holder_image'] == image and value['current_validation'] is True and
         type(value['source_commit']) is str and re.fullmatch('[0-9a-f]{40}', value['source_commit']) and
         type(value['config_image_id']) is str and re.fullmatch('sha256:[0-9a-f]{64}', value['config_image_id']) and
         all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}', value[k]) for k in
             ('qualification_receipt_sha256', 'admission_receipt_sha256')) and
         health.strict_equal(value['protected_claim_names'], ['bortus-data', target]), 'qualification')
    nodes = value['node_names']
    need(type(nodes) is list and len(nodes) == 3 and all(reader.metadata.valid_name(n) for n in nodes) and
         nodes == sorted(set(nodes)) and source_node in nodes and alternate_node in nodes, 'qualification')
    return copy.deepcopy(value)


def write_once(directory_fd, basename, value):
    raw = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    need(len(raw) <= 65536, 'receipt')
    fd = os.open(basename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as out:
            out.write(raw)
            out.flush()
            os.fsync(fd)
        os.fsync(directory_fd)
    finally:
        os.close(fd)


def _restore(run_directory, checkpoint_journal, checkpoint_sha256, original_archive,
             holder_image, alternate_node, kubeconfig_path, options, qualify_image,
             age, recipient_file, identity_file, deadline):
    fence = journal = collector = None
    receipt_fd = None
    failure, stage, result = None, 'configuration', None
    state = None
    try:
        deadline_check(deadline)
        need(os.name == 'posix' and type(options) is reader.credentials.OperatorMTLSOptions and
             callable(qualify_image) and source.preflight.cold.valid_digest(holder_image) and
             reader.metadata.valid_name(alternate_node) and type(kubeconfig_path) is str and
             pathlib.Path(kubeconfig_path) == options.path, 'configuration')
        stage = 'source'
        fence = source.SourceFence(checkpoint_journal, checkpoint_sha256, holder_image,
            alternate_node, source.metadata.MetadataAPI(options, origin=source.metadata.APPROVED_ORIGIN))
        prepared = fence.prepare(deadline=deadline)
        proposals = prepared['proposals']
        target, run = prepared['restore_target_name'], prepared['checkpoint_run_id']
        original = prepared['source_identities']
        backup = prepared['backup_identity']
        stage = 'qualification'
        image_binding = qualified(qualify_image(holder_image, target, deadline), holder_image,
            target, prepared['source_node_name'], alternate_node)
        bindings = source_bindings()
        stage = 'ownership'
        journal = watch.WatchJournal(pathlib.Path(run_directory)).open(watch.ownership.seed(
            run, checkpoint_sha256, hashlib.sha256(mutations.canonical(proposals)).hexdigest()))
        receipt_fd = os.dup(journal.fd)
        directory_inode = journal.directory_inode
        state = {'abi': 1, 'state': 'pending', 'failure': None, 'run_id': run,
            'checkpoint_journal_sha256': checkpoint_sha256, 'source_bindings': bindings,
            'qualification': image_binding, 'created': [], 'completion_observed': False,
            'whole_rows_equal': False, 'holder_absent': False, 'resources_closed': False,
            'overall_live_restore_acceptance': False, 'image_runtime_admission_acceptance': False}
        write_once(receipt_fd, 'restore-intent.json', state)
        src = watch.Source(proposals[0]['parameters']['fromBackup'], watch.completion.BackupIdentity(
            backup['name'], backup['namespace'], backup['uid'], backup['resourceVersion']),
            original['longhorn_volume']['uid'], original['longhorn_volume']['name'],
            original['pv']['uid'], original['claim']['uid'])
        stage = 'watch'
        collector = watch.Collector(journal, watch.TLSAPI(reader.metadata.APPROVED_ORIGIN, options), src)
        collector.deadline = min(collector.deadline, deadline)
        collector.start()
        api = mutations.MutationAPI(collector, options, proposals)

        def live():
            deadline_check(deadline)
            collector.prerequisite()

        def fresh_source():
            live()
            current = fence.check(deadline=deadline)
            need(current['checkpoint_journal_sha256'] == checkpoint_sha256 and
                 current['original_ciphertext_sha256'] == prepared['original_ciphertext_sha256'], 'source')
            for key, original_key in (('claim', 'claim'), ('pv', 'pv'), ('volume', 'longhorn_volume')):
                need(health.strict_equal(selected(current[key]), selected(original[original_key])), 'source')
            need(health.strict_equal(selected(current['backup']), selected(backup)), 'source')
            live()
            return current

        def authorize():
            fresh_source()
            value = qualified(qualify_image(holder_image, target, deadline), holder_image,
                target, prepared['source_node_name'], alternate_node)
            need(health.strict_equal(value, image_binding) and source_bindings() == bindings, 'qualification')
            live()

        def create(action, resource, proposal):
            authorize()
            def validate(reply):
                live()
                current = api.readonly.get(resource, target, deadline=deadline)
                admitted.validate(resource, proposal, reply, current)
                fresh_source()
                live()
            return collector.perform_create(action,
                lambda intent: api.create(action, intent, deadline=deadline), validate)

        stage = 'create'
        sc = create('storageclass_create', 'storageclass', proposals[0]); state['created'].append('storageclass')
        claim_created = create('claim_create', 'claim', proposals[1]); state['created'].append('claim')

        def pause():
            live()
            time.sleep(min(.05, max(0, deadline - time.monotonic())))
            live()

        stage = 'binding'
        while True:
            live()
            claim = api.readonly.get('claim', target, deadline=deadline)
            # Recheck full admitted policy throughout asynchronous controller binding.
            reply = {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
                'metadata': dict(claim_created['identity'], labels={'bortus-restore': run})}
            admitted.validate('claim', proposals[1], reply, claim)
            if claim.get('status', {}).get('phase') == 'Bound':
                pv_name = claim['spec'].get('volumeName')
                need(reader.metadata.valid_name(pv_name), 'binding')
                pv = api.readonly.get('pv', pv_name, deadline=deadline)
                volume_name = pv.get('spec', {}).get('csi', {}).get('volumeHandle')
                need(reader.metadata.valid_name(volume_name), 'binding')
                volume = api.readonly.get('volume', volume_name, deadline=deadline)
                # bind_target is irreversible: wait for an actual durable UID trace first.
                with collector.lock:
                    live()
                    observations = [p for p in collector.state['observations'] if
                        p['identity']['name'] == volume_name or p['identity']['uid'] == volume['metadata']['uid']]
                if observations:
                    fresh_source()
                    collector.bind_target(claim, pv, volume)
                    break
            pause()

        stage = 'completion'
        while True:
            live()
            volume = api.readonly.get('volume', volume_name, deadline=deadline)
            with collector.lock:
                live()
                events = collector._target_events()
                try:
                    watch.completion.evaluate_restore_transition(collector.expected, events,
                        watch_started_before_create=True,
                        longhorn_version=watch.completion.LONGHORN_VERSION,
                        api_version=watch.completion.API_VERSION)
                except watch.completion.RestoreTransitionRefused as error:
                    need(error.code == 'completion_unobserved', 'completion')
                    complete = False
                else:
                    projected = collector._project({'type': 'MODIFIED', 'object': volume})
                    complete = projected['identity'] == events[-1]['object']['metadata'] and \
                        projected['flags'] == events[-1]['object']['status']
                if complete:
                    collector.seal(volume)
                    break
            pause()
        state['completion_observed'] = True
        stage = 'create'
        holder_created = create('holder_create', 'pod', proposals[2]); state['created'].append('holder')
        expected = {'original_claim': selected(original['claim']), 'original_pv': selected(original['pv']),
            'original_volume': selected(original['longhorn_volume']), 'claim': selected(claim_created['identity']),
            'pv': selected(health.identity(pv, None)._asdict()), 'volume': selected(volume['metadata']),
            'backup': selected(backup), 'holder': selected(holder_created['identity']),
            'holder_image': holder_image, 'original_node': prepared['source_node_name'],
            'node': selected(prepared['alternate_node_identity']), 'longhorn_version': '1.12.1',
            'backup_url': src.backup_url}

        def read_metadata(_deadline):
            need(_deadline == deadline, 'deadline')
            live()
            objects = {k: api.readonly.get(resource, name, deadline=deadline) for k, resource, name in (
                ('claim', 'claim', target), ('pv', 'pv', pv_name), ('volume', 'volume', volume_name),
                ('backup', 'backup', backup['name']), ('node', 'node', alternate_node))}
            for key, resource in (('pvs', 'pv'), ('pods', 'pod'), ('engines', 'engine'), ('replicas', 'replica')):
                objects[key] = api.readonly.list(resource, deadline=deadline)
            live()
            return objects

        stage = 'health'
        while True:
            live()
            pod = api.readonly.get('pod', target, deadline=deadline)
            admitted.validate('pod', proposals[2], {'apiVersion': 'v1', 'kind': 'Pod',
                'metadata': dict(holder_created['identity'], labels={'bortus-restore': run})}, pod)
            if pod.get('status', {}).get('phase') == 'Running' and health.ready(pod.get('status', {})):
                eligible = health.evaluate(expected, read_metadata(deadline))
                first_health = data.health_record(eligible)
                break
            need(pod.get('status', {}).get('phase') not in ('Succeeded', 'Failed'), 'health')
            pause()

        def snapshot(_deadline):
            need(_deadline == deadline, 'deadline')
            current = fresh_source()
            return data.SourceSnapshot(checkpoint_sha256, current['original_ciphertext_sha256'],
                *(health.identity({'metadata': current[k]}, ns) for k, ns in
                  (('claim', 'bortus'), ('pv', None), ('volume', 'longhorn-system'), ('backup', 'longhorn-system'))))

        stage = 'data'
        authorize()
        launcher = reader.ReaderLauncher(api, kubeconfig_path, options)
        completed_data = data.execute(collector, expected, original_archive, prepared['original_ciphertext_sha256'],
            age=age, recipient_file=recipient_file, identity_file=identity_file,
            source_fence=snapshot, read_metadata=read_metadata, launch_reader=launcher.launch_reader,
            deadline=deadline)
        need(type(completed_data) is data.DataResult and completed_data.recovery_rows_equal is True and
             completed_data.exact_tmpfs_copies_cleaned is True and
             completed_data.overall_live_restore_acceptance is False and
             completed_data.image_runtime_admission_acceptance is False, 'data')
        state['whole_rows_equal'] = True
        authorize()
        data.same_identities(first_health, data.health_record(health.evaluate(expected, read_metadata(deadline))))
        stage = 'delete'
        current = api.readonly.get('pod', target, deadline=deadline)
        owned = admitted.validate('pod', proposals[2], {'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': dict(holder_created['identity'], labels={'bortus-restore': run})}, current, require_ready=True)
        delete_identity = dict(name=owned.name, namespace=owned.namespace, uid=owned.uid,
                               resourceVersion=owned.resource_version)

        def absence(reply):
            need(reply.get('submitted') is True and reply.get('deletion_observed') is False, 'delete')
            while True:
                live()
                pods = api.readonly.list('pod', deadline=deadline)
                # Refuse same-name replacement rather than waiting/adopting it.
                need(not any(p['metadata']['name'] == target and p['metadata']['uid'] != owned.uid
                             for p in pods['items']), 'delete')
                try:
                    admitted.holder_absent(pods, delete_identity)
                except admitted.AdmittedRefused as error:
                    need(error.code == 'present', 'delete')
                else:
                    fresh_source()
                    live()
                    return
                pause()
        journal.perform('holder_delete', lambda intent: api.delete(intent, deadline=deadline),
                        absence, delete_identity=delete_identity)
        state['holder_absent'] = True
        fresh_source()
        live()
    except RestoreRefused as error:
        failure = error.code
    except Exception:
        failure = stage
    finally:
        closed = True
        for owned_resource in (collector, fence, journal):
            if owned_resource is not None:
                try: owned_resource.close()
                except Exception: closed = False
        if not closed:
            failure = 'cleanup'
        if failure is None:
            try: deadline_check(deadline)
            except Exception: failure = 'deadline'
        if state is not None and receipt_fd is not None:
            state.update(state='refused' if failure else 'completed', failure=failure, resources_closed=closed)
            try:
                pinned, path = os.fstat(receipt_fd), pathlib.Path(run_directory).lstat()
                need((pinned.st_dev, pinned.st_ino) == directory_inode == (path.st_dev, path.st_ino) and
                     stat.S_ISDIR(path.st_mode) and path.st_uid == os.getuid() and
                     stat.S_IMODE(path.st_mode) == 0o700, 'ownership')
                write_once(receipt_fd, 'restore-receipt.json', state)
                if not failure: result = RestoreResult(state['run_id'])
            except Exception:
                failure = 'receipt'
        if receipt_fd is not None:
            try: os.close(receipt_fd)
            except Exception: failure, result = 'cleanup', None
    return (None if failure else result), failure


def restore(run_directory, checkpoint_journal, checkpoint_sha256, original_archive,
            holder_image, alternate_node, kubeconfig_path, options, qualify_image, *,
            age, recipient_file, identity_file, deadline):
    """Trusted root qualification callback metadata is prerequisite, never live proof."""
    result, failure = _restore(run_directory, checkpoint_journal, checkpoint_sha256, original_archive,
        holder_image, alternate_node, kubeconfig_path, options, qualify_image,
        age, recipient_file, identity_file, deadline)
    if failure:
        run_directory = checkpoint_journal = checkpoint_sha256 = original_archive = None
        holder_image = alternate_node = kubeconfig_path = options = qualify_image = None
        age = recipient_file = identity_file = deadline = None
        raise RestoreRefused(failure)
    return result
