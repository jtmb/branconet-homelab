#!/usr/bin/env python3
"""Export or sequentially preload an immutable image; never run or deploy it."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import stat
import subprocess
import tarfile
import threading
import uuid

SPEC = importlib.util.spec_from_file_location('release_builder', pathlib.Path(__file__).with_name('build-bortus-release-image.py'))
b = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(b)
MAX_ARCHIVE = 4 * 1024 ** 3
MAX_MEMBERS = 4096
MAX_METADATA = 8 * 1024 ** 2
HOSTS = ('192.168.0.4', '192.168.0.5', '192.168.0.6')


def require(ok, code): b.require(ok, code)


class OperationRun(b.Run):
    def __init__(self, parent, commit, purpose, attempt_id=None):
        require(os.name == 'posix' and b.hexid(commit, 40) and purpose in ('export', 'preload'), 'operation')
        require(attempt_id is None or (purpose == 'preload' and b.hexid(attempt_id, 12)), 'attempt')
        self.parent = pathlib.Path(parent); self.name = 'bortus-' + purpose + '-' + commit + (('-attempt-' + attempt_id) if attempt_id is not None else '')
        self.directory = self.parent / self.name; self.parent_fd = self.fd = None; self.anchors = []
        try:
            require(self.parent.is_absolute() and len(self.parent.parts) <= 32 and '..' not in self.parent.parts, 'runtime_parent')
            fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.anchors.append((pathlib.Path('/'), fd, b.identity(os.fstat(fd))))
            path = pathlib.Path('/')
            for part in self.parent.parts[1:]:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                path /= part; info = os.fstat(fd); self.anchors.append((path, fd, b.identity(info)))
                require(info.st_uid in (0, os.getuid()) and stat.S_IMODE(info.st_mode) & 0o022 == 0, 'runtime_parent')
            require(os.fstat(fd).st_uid == os.getuid(), 'runtime_parent'); self.parent_fd = fd
            os.mkdir(self.name, 0o700, dir_fd=fd); os.fsync(fd)
            self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            self.run_identity = b.identity(os.fstat(self.fd)); self.record_identity = None; self.inputs = {}
            self.record = {'scope': 'Immutable image staging only; no runtime or deployment qualification',
                'owner': str(uuid.uuid4()), 'source_commit': commit, 'image_tag': 'bortus:release-' + commit,
                'purpose': purpose, 'phase': 'validating', 'started_at_utc': b.now(), 'runtime_qualified': False,
                'deployed': False, 'nodes': []}
            if attempt_id is not None: self.record['attempt_id'] = attempt_id
            self.save()
        except Exception:
            self.close(); raise


def receipt(run, path, expected_sha, commit, config_id):
    require(b.hexid(expected_sha, 64) and type(config_id) is str and config_id.startswith('sha256:') and
        b.hexid(config_id[7:], 64), 'receipt_input')
    run.copy_input(path, 'build-receipt.json', MAX_METADATA)
    with run.open_input('build-receipt.json', expected_sha) as source:
        record = json.loads(source.read(), object_pairs_hook=b.unique)
    require(type(record) is dict and record.get('scope') == 'Immutable BORTUS image build only; no runtime/deployment acceptance' and
        record.get('phase') == 'completed' and record.get('source_commit') == commit and
        record.get('image_tag') == run.record['image_tag'] and
        all(type(record.get(k)) is int and record[k] == 0 for k in ('build_exit_code', 'inspect_exit_code', 'tag-check_exit_code')) and
        type(record.get('image_bytes')) is int and 0 < record['image_bytes'] <= MAX_ARCHIVE and
        b.hexid(record.get('application_tree'), 40) and all(b.hexid(record.get(k), 64) for k in ('context_sha256', 'manifest_sha256')) and
        record.get('deployed') is False and record.get('runtime_accepted') is False and
        record.get('runtime_digest_qualified') is False and record.get('image_manifest_digest') is None, 'build_receipt')
    try: owner = str(uuid.UUID(record.get('owner')))
    except (ValueError, TypeError, AttributeError): owner = None
    require(owner is not None and owner == record['owner'], 'build_owner')
    labels = dict(zip(b.LABEL_KEYS, [commit, record['application_tree'], record['context_sha256'], record['manifest_sha256'], owner]))
    if record.get('build_recipe') == 'release-v2':
        require(record.get('builder_transport') == 'local' and record.get('dockerfile') == 'Dockerfile.release' and
                b.hexid(record.get('dockerfile_sha256'), 64) and type(record.get('runtime_image')) is str and
                re.fullmatch(r'[a-z0-9][a-z0-9._/:@-]{0,252}', record['runtime_image']) and
                type(record.get('runtime_image_id')) is str and
                re.fullmatch(r'sha256:[0-9a-f]{64}', record['runtime_image_id']) and
                all(type(record.get(k)) is int and record[k] == 0 for k in
                    ('runtime-before_exit_code', 'runtime-after_exit_code')) and
                type(record.get('local_image_id')) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', record['local_image_id']) and
                'config_image_id' not in record and
                (run.record['purpose'] != 'export' or record['local_image_id'] == config_id), 'release_build_receipt')
        labels[b.BASE_LABEL] = record['runtime_image']
        run.record.update(build_recipe='release-v2', builder_transport='local',
                          runtime_image=record['runtime_image'], runtime_image_id=record['runtime_image_id'],
                          dockerfile_sha256=record['dockerfile_sha256'], local_image_id=record['local_image_id'])
    else:
        require('build_recipe' not in record and 'builder_transport' not in record and
                record.get('config_image_id') == config_id, 'build_recipe')
    require(record.get('labels') == labels, 'source_labels')
    run.record.update(labels=labels, build_receipt_sha256=expected_sha)
    if record.get('build_recipe') != 'release-v2' or run.record['purpose'] == 'preload':
        run.record['config_image_id'] = config_id
    return record


def release_archive_identity(stream, tag, local_id, labels):
    """Resolve the saved Docker OCI index; retain the original archive verifier below."""
    stream.seek(0); members = {}; names = set(); total = 0
    with tarfile.open(fileobj=stream, mode='r|', tarinfo=ImageTarInfo) as archive:
        for member in archive:
            path_ok(member.name); canonical = member.name.rstrip('/')
            require(canonical not in names and len(names) < MAX_MEMBERS and not member.linkname and
                    set(member.pax_headers) <= {'path'}, 'release_archive_member')
            names.add(canonical)
            if member.isdir(): require(member.size == 0, 'image_directory'); continue
            require(member.isfile(), 'image_archive_regular'); total += member.size
            require(total <= MAX_ARCHIVE, 'image_archive_total')
            members[member.name] = (member.offset_data, member.size)
        while True:
            raw = archive.fileobj.read(65536)
            if not raw: break
            require(not any(raw), 'image_archive_trailing')
    def blob(name, digest=None, size=None):
        require(name in members, 'release_blob_missing')
        offset, count = members[name]
        require(count <= MAX_METADATA and (size is None or type(size) is int and size == count), 'release_blob_size')
        stream.seek(offset); raw = stream.read(count)
        require(len(raw) == count and (digest is None or b.digest(raw) == digest[7:]), 'release_blob_hash')
        return json.loads(raw, object_pairs_hook=b.unique)
    def descriptor(value, media):
        require(type(value) is dict and set(value) <= {'digest', 'size', 'mediaType', 'platform', 'annotations'} and
                type(value.get('digest')) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', value['digest']) and
                type(value.get('size')) is int and value['size'] >= 0 and type(value.get('mediaType')) is str and
                value['mediaType'] == media, 'release_descriptor')
        return blob('blobs/sha256/' + value['digest'][7:], value['digest'], value['size'])
    index_media = 'application/vnd.oci.image.index.v1+json'
    manifest_media = 'application/vnd.oci.image.manifest.v1+json'
    top = blob('index.json')
    require(type(top) is dict and set(top) == {'schemaVersion', 'mediaType', 'manifests'} and
            type(top['schemaVersion']) is int and top['schemaVersion'] == 2 and top['mediaType'] == index_media and
            type(top['manifests']) is list and len(top['manifests']) == 1 and
            top['manifests'][0].get('digest') == local_id, 'release_local_index')
    index = descriptor(top['manifests'][0], index_media)
    require(type(index) is dict and set(index) == {'schemaVersion', 'mediaType', 'manifests'} and
            type(index['schemaVersion']) is int and index['schemaVersion'] == 2 and index['mediaType'] == index_media and
            type(index['manifests']) is list and len(index['manifests']) == 2, 'release_index')
    runtime, attestation = index['manifests']
    require(runtime.get('platform') == {'architecture': 'amd64', 'os': 'linux'} and
            'annotations' not in runtime, 'release_platform')
    leaf = descriptor(runtime, manifest_media)
    require(type(leaf) is dict and set(leaf) == {'schemaVersion', 'mediaType', 'config', 'layers'} and
            type(leaf['schemaVersion']) is int and leaf['schemaVersion'] == 2 and leaf['mediaType'] == manifest_media,
            'release_manifest')
    require(attestation.get('platform') == {'architecture': 'unknown', 'os': 'unknown'} and
            attestation.get('annotations') == {'vnd.docker.reference.digest': runtime['digest'],
                                              'vnd.docker.reference.type': 'attestation-manifest'}, 'release_attestation_reference')
    attest = descriptor(attestation, manifest_media)
    require(type(attest) is dict and type(attest.get('schemaVersion')) is int and attest['schemaVersion'] == 2 and
            attest.get('mediaType') == manifest_media and type(attest.get('config')) is dict and
            type(attest.get('layers')) is list and 1 <= len(attest['layers']) <= 8, 'release_attestation')
    for item in [attest['config'], *attest['layers']]:
        descriptor(item, item.get('mediaType'))
    config = descriptor(leaf['config'], 'application/vnd.oci.image.config.v1+json')
    config_id = leaf['config']['digest']
    docker_manifest = blob('manifest.json')
    require(type(leaf['layers']) is list and 1 <= len(leaf['layers']) <= 1024 and
            type(docker_manifest) is list and len(docker_manifest) == 1, 'release_layers')
    layer_paths = []
    for item in leaf['layers']:
        require(type(item) is dict and set(item) == {'mediaType', 'digest', 'size'} and
                type(item['digest']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', item['digest']) and
                type(item['size']) is int and item['size'] >= 0 and item['mediaType'] in {
                    'application/vnd.oci.image.layer.v1.tar', 'application/vnd.oci.image.layer.v1.tar+gzip',
                    'application/vnd.docker.image.rootfs.diff.tar', 'application/vnd.docker.image.rootfs.diff.tar.gzip'}, 'release_layer')
        name = 'blobs/sha256/' + item['digest'][7:]
        require(name in members and members[name][1] == item['size'], 'release_layer_size')
        stream.seek(members[name][0]); prefix = stream.read(min(2, item['size']))
        require((item['mediaType'].endswith(('+gzip', '.gzip'))) == (prefix == b'\x1f\x8b'), 'release_layer_media')
        layer_paths.append(name)
    require(docker_manifest[0].get('Config') == 'blobs/sha256/' + config_id[7:] and
            docker_manifest[0].get('RepoTags') == [tag] and docker_manifest[0].get('Layers') == layer_paths, 'release_docker_manifest')
    verified = archive_identity(stream, tag, config_id, labels, allow_repeated_layers=True)
    require(verified['layer_blob_digests'] == [d['digest'] for d in leaf['layers']] and
            config.get('rootfs') == {'type': 'layers', 'diff_ids': verified['ordered_diff_ids']}, 'release_layer_identity')
    return dict(verified, local_image_id=local_id, selected_manifest_digest=runtime['digest'],
                attestation_reference_checked=True, attestation_semantics_qualified=False)


def path_ok(name):
    require(type(name) is str and len(name.encode()) <= 4096 and name and not name.startswith('/') and
        '\\' not in name and ':' not in name and all(p not in ('', '.', '..') for p in (name[:-1] if name.endswith('/') else name).split('/')) and
        not any(ord(c) < 32 or ord(c) == 127 for c in name), 'image_archive_path')


class ImageTarInfo(tarfile.TarInfo):
    def _proc_member(self, archive):
        require(self.type in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE, tarfile.XHDTYPE) and
            0 <= self.size <= (8192 if self.type == tarfile.XHDTYPE else MAX_ARCHIVE), 'image_archive_type_size')
        return super()._proc_member(archive)


class MemberSlice:
    def __init__(self, stream, offset, size):
        self.stream, self.remaining = stream, size; stream.seek(offset)
    def read(self, amount=-1):
        amount = min(65536, self.remaining, amount if amount >= 0 else 65536)
        raw = self.stream.read(amount); self.remaining -= len(raw); return raw


def archive_identity(stream, tag, config_id, labels, *, allow_repeated_layers=False):
    """Bounded complete inventory; decode only manifest/config, never layer values."""
    size = os.fstat(stream.fileno()).st_size; require(0 < size <= MAX_ARCHIVE, 'image_archive_bound')
    stream.seek(0); digest = b.stream_hash(stream); stream.seek(0)
    files = {}; metadata = {}; layers = {}; total = 0
    with tarfile.open(fileobj=stream, mode='r|', tarinfo=ImageTarInfo) as archive:
        names = set()
        for member in archive:
            path_ok(member.name); canonical = member.name.rstrip('/')
            require(canonical not in names and len(names) < MAX_MEMBERS and
                not member.linkname and set(member.pax_headers) <= {'path'}, 'image_archive_member')
            names.add(canonical)
            if member.isdir(): require(member.size == 0, 'image_directory'); continue
            require(member.isfile(), 'image_archive_regular'); total += member.size
            require(total <= MAX_ARCHIVE, 'image_archive_total')
            source = archive.extractfile(member); hashed = hashlib.sha256(); prefix = source.read(2)
            hashed.update(prefix)
            # Docker save emits uncompressed layer tar or content-addressed OCI blobs.
            # Keep their bytes opaque; the config's ordered diff IDs are verified below.
            raw = bytearray(prefix) if member.size <= MAX_METADATA else None
            for chunk in iter(lambda: source.read(65536), b''):
                hashed.update(chunk)
                if raw is not None: raw.extend(chunk)
            source.close(); files[member.name] = hashed.hexdigest()
            if member.name == 'manifest.json' or hashed.hexdigest() == config_id[7:]:
                require(raw is not None, 'image_metadata_bound'); metadata[member.name] = bytes(raw)
            if member.name.endswith('/layer.tar') or member.name.startswith('blobs/sha256/'):
                layers[member.name] = (member.offset_data, member.size, prefix)
        while True:
            raw = archive.fileobj.read(65536)
            if not raw: break
            require(not any(raw), 'image_archive_trailing')
    require('manifest.json' in metadata, 'image_manifest')
    manifest = json.loads(metadata['manifest.json'], object_pairs_hook=b.unique)
    require(type(manifest) is list and len(manifest) == 1 and type(manifest[0]) is dict and
        set(manifest[0]) <= {'Config', 'RepoTags', 'Layers', 'LayerSources'} and
        all(k in manifest[0] for k in ('Config', 'RepoTags', 'Layers')), 'image_manifest')
    item = manifest[0]; require(item['RepoTags'] == [tag] and type(item['Layers']) is list and
        len(item['Layers']) <= 1024 and
        (allow_repeated_layers or len(set(item['Layers'])) == len(item['Layers'])), 'image_inventory')
    path_ok(item['Config']); require(files.get(item['Config']) == config_id[7:] and item['Config'] in metadata, 'image_config_id')
    config = json.loads(metadata[item['Config']], object_pairs_hook=b.unique)
    require(type(config) is dict and config.get('os') == 'linux' and config.get('architecture') == 'amd64' and
        type(config.get('config')) is dict and all(config['config'].get('Labels', {}).get(k) == v for k, v in labels.items()) and
        type(config.get('rootfs')) is dict and config['rootfs'].get('type') == 'layers', 'image_config')
    ordered = []; blob_ids = []; expanded = 0
    for layer in item['Layers']:
        path_ok(layer); require(layer in layers, 'image_layer')
        blob_ids.append('sha256:' + files[layer])
        offset, count, prefix = layers[layer]
        if prefix == b'\x1f\x8b':
            hashed = hashlib.sha256()
            with gzip.GzipFile(fileobj=MemberSlice(stream, offset, count), mode='rb') as decompressed:
                for chunk in iter(lambda: decompressed.read(65536), b''):
                    expanded += len(chunk); require(expanded <= MAX_ARCHIVE, 'image_layer_expansion'); hashed.update(chunk)
            ordered.append('sha256:' + hashed.hexdigest())
        else:
            expanded += count; require(expanded <= MAX_ARCHIVE, 'image_layer_expansion'); ordered.append('sha256:' + files[layer])
    require(config['rootfs'].get('diff_ids') == ordered, 'image_diff_ids')
    return {'archive_sha256': digest, 'archive_bytes': size, 'config_image_id': config_id,
            'archive_members': len(names), 'linux_amd64': True, 'ordered_diff_ids_verified': True,
            'layer_blob_digests': blob_ids, 'ordered_diff_ids': ordered}


def inspect_command(tag, labels=None, local=False):
    template = '{' + json.dumps('local_image_id' if local else 'config_image_id') + ':{{json .Id}},"labels":{' + ','.join(
        json.dumps(k) + ':{{json (index .Config.Labels ' + json.dumps(k) + ')}}' for k in (labels or b.LABEL_KEYS)) + '}}'
    argv = ['docker', 'image', 'inspect', '--format', template, tag]
    return argv if local else b.remote(argv)


def inspect(run, stage, invoke):
    code = invoke(run, stage, inspect_command(run.record['image_tag'], run.record['labels'],
                  run.record.get('builder_transport') == 'local'), 30)
    path = run.directory / (stage + '.stdout'); require(code == 0 and path.stat().st_size <= MAX_METADATA, 'source_inspect')
    result = json.loads(path.read_bytes(), object_pairs_hook=b.unique)
    image_key = 'local_image_id' if run.record.get('builder_transport') == 'local' else 'config_image_id'
    require(type(result) is dict and set(result) == {image_key, 'labels'} and
        result[image_key] == run.record[image_key] and
        result['labels'] == run.record['labels'], 'source_identity')


def export_image(build_receipt, receipt_sha, commit, config_id, runtime_parent, invoke=None):
    if invoke is None: invoke = export_execute
    run = OperationRun(runtime_parent, commit, 'export'); dispatched = False; failure = None
    try:
        receipt(run, build_receipt, receipt_sha, commit, config_id); run.save()
        inspect(run, 'source-before', invoke)
        run.record.update(phase='pending', pending_at_utc=b.now()); run.save()
        fd = run.create('image.tar')
        with os.fdopen(fd, 'w+b') as archive:
            dispatched = True
            argv = ['docker', 'image', 'save', run.record['image_tag']]
            code = invoke(run, 'save', argv if run.record.get('builder_transport') == 'local' else b.remote(argv),
                          1200, archive=archive)
            run.record['save_exit_code'] = code
            archive.flush(); os.fsync(archive.fileno()); os.fsync(run.fd)
            require(code == 0, 'image_save')
            verified = (release_archive_identity(archive, run.record['image_tag'], run.record['local_image_id'], run.record['labels'])
                        if run.record.get('build_recipe') == 'release-v2' else
                        archive_identity(archive, run.record['image_tag'], config_id, run.record['labels']))
            run.record.update(verified)
            run.inputs['image.tar'] = b.input_identity(os.fstat(archive.fileno()))
            run.check_input('image.tar', archive.fileno())
        inspect(run, 'source-after', invoke)
        run.record.update(phase='completed', completed_at_utc=b.now(), archive_path=str(run.directory / 'image.tar')); run.save()
        result = dict(run.record)
    except Exception as error:
        failure = error.code if isinstance(error, b.BuildRefused) else 'export_failed'
        run.record.update(phase='uncertain' if dispatched else 'refused', failure=failure)
        try: run.save()
        except Exception: pass
    finally: run.close()
    if failure: raise b.BuildRefused(failure)
    return result


def export_execute(run, stage, command, timeout, archive=None):
    if archive is None: return b.execute(run, stage, command, timeout)
    fd = run.create(stage + '.stderr')
    with os.fdopen(fd, 'wb') as err:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err, start_new_session=True)
        failed = []
        def receive():
            try:
                total = 0
                for chunk in iter(lambda: process.stdout.read(65536), b''):
                    total += len(chunk); require(total <= MAX_ARCHIVE, 'save_archive_bound'); archive.write(chunk)
            except Exception:
                failed.append(True); process.kill()
            finally: process.stdout.close()
        reader = threading.Thread(target=receive, daemon=True); reader.start()
        try:
            code = process.wait(timeout=timeout); run.record[stage + '_exit_code'] = code
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10)
            run.record[stage + '_timed_out'] = True; raise b.BuildRefused('save_timeout') from None
        finally:
            reader.join(timeout=5); err.flush(); os.fsync(err.fileno())
        require(not reader.is_alive() and not failed, 'save_stream'); return code


def preload_execute(run, host, request, archive):
    """Password goes only to the owned SSH pipe; archive streaming is bounded."""
    script = pathlib.Path(__file__).with_name('bortus-release-preload-node.py').read_text(encoding='utf-8')
    command = b.SSH[:-1] + ['james@' + host, 'python3 -c ' + shlex.quote(script)]
    out_fd = run.create(host + '.stdout')
    try: err_fd = run.create(host + '.stderr')
    except Exception: os.close(out_fd); raise
    with os.fdopen(out_fd, 'wb') as out, os.fdopen(err_fd, 'wb') as err:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
        run.record['active_ssh_pid'] = process.pid
        writer_failed = []
        def write():
            try:
                process.stdin.write((json.dumps(request) + '\n').encode()); process.stdin.flush()
                for chunk in iter(lambda: archive.read(65536), b''): process.stdin.write(chunk)
                process.stdin.flush()
            except Exception: writer_failed.append(True)
            finally:
                try: process.stdin.close()
                except Exception: writer_failed.append(True)
        thread = threading.Thread(target=write, daemon=True); thread.start()
        try: code = process.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10); raise b.BuildRefused('preload_timeout') from None
        finally:
            thread.join(timeout=5)
            if process.poll() is None: process.kill(); process.wait(timeout=10)
            out.flush(); err.flush(); os.fsync(out.fileno()); os.fsync(err.fileno())
        require(not thread.is_alive() and not writer_failed, 'preload_stream')
        require(out.tell() <= 65536, 'node_metadata_bound')
    raw = (run.directory / (host + '.stdout')).read_bytes()
    require(code == 0, 'node_reply')
    return json.loads(raw, object_pairs_hook=b.unique)


def preload(build_receipt, receipt_sha, export_receipt, export_sha, commit, config_id, runtime_parent,
            password, invoke=preload_execute, *, attempt_id=None):
    require(type(password) is str and 0 < len(password.encode()) <= 4096 and not any(c in password for c in '\0\r\n'), 'stdin_authorization')
    run = OperationRun(runtime_parent, commit, 'preload', attempt_id=attempt_id); failure = None; dispatched = False; request = None
    try:
        receipt(run, build_receipt, receipt_sha, commit, config_id)
        run.copy_input(export_receipt, 'export-receipt.json', MAX_METADATA)
        with run.open_input('export-receipt.json', export_sha) as stream:
            exported = json.loads(stream.read(), object_pairs_hook=b.unique)
        require(type(exported) is dict and exported.get('scope') == 'Immutable image staging only; no runtime or deployment qualification' and
            exported.get('phase') == 'completed' and exported.get('purpose') == 'export' and
            exported.get('runtime_qualified') is False and exported.get('deployed') is False and
            exported.get('linux_amd64') is True and exported.get('ordered_diff_ids_verified') is True and
            exported.get('source_commit') == commit and exported.get('config_image_id') == config_id and
            exported.get('labels') == run.record['labels'] and exported.get('image_tag') == run.record['image_tag'] and
            exported.get('build_receipt_sha256') == receipt_sha and b.hexid(exported.get('archive_sha256'), 64) and
            type(exported.get('archive_bytes')) is int and 0 < exported['archive_bytes'] <= MAX_ARCHIVE, 'export_receipt')
        if run.record.get('build_recipe') == 'release-v2':
            require(exported.get('local_image_id') == run.record['local_image_id'] and
                    exported.get('build_recipe') == 'release-v2', 'export_local_identity')
        run.copy_input(exported['archive_path'], 'image.tar', MAX_ARCHIVE)
        with run.open_input('image.tar', exported['archive_sha256']) as stream:
            verified = (release_archive_identity(stream, run.record['image_tag'], run.record['local_image_id'], run.record['labels'])
                        if run.record.get('build_recipe') == 'release-v2' else
                        archive_identity(stream, run.record['image_tag'], config_id, run.record['labels']))
        require(verified['archive_bytes'] == exported['archive_bytes'] and verified['config_image_id'] == config_id,
                'export_archive'); run.record.update(verified)
        expected_manifest = None
        for host in HOSTS:
            node = {'host': host, 'phase': 'pending', 'pending_at_utc': b.now()}
            run.record['nodes'].append(node); run.record['phase'] = 'pending'; run.save()
            request = {'sudo_password': password, 'source_commit': commit, 'config_image_id': config_id,
                'labels': run.record['labels'], 'archive_sha256': verified['archive_sha256'], 'archive_bytes': verified['archive_bytes'],
                'layer_blob_digests': verified['layer_blob_digests'], 'ordered_diff_ids': verified['ordered_diff_ids']}
            if attempt_id is not None: request['attempt_id'] = attempt_id
            require(len((json.dumps(request) + '\n').encode()) <= 256 * 1024, 'node_request_bound')
            with run.open_input('image.tar', verified['archive_sha256']) as stream:
                dispatched = True; reply = invoke(run, host, request, stream); run.check_input('image.tar', stream.fileno())
            request.clear()
            require(type(reply) is dict and set(reply) == {'phase', 'source_commit', 'config_image_id', 'runtime_manifest_digest',
                'selected_manifest_digest', 'archive_sha256', 'archive_bytes', 'labels', 'import_exit_code', 'runtime_qualified'} | ({'attempt_id'} if attempt_id is not None else set()) and
                (attempt_id is None or reply['attempt_id'] == attempt_id) and
                reply['phase'] == 'completed' and reply['source_commit'] == commit and reply['config_image_id'] == config_id and
                reply['labels'] == run.record['labels'] and reply['archive_sha256'] == verified['archive_sha256'] and
                type(reply['archive_bytes']) is int and reply['archive_bytes'] == verified['archive_bytes'] and type(reply['import_exit_code']) is int and
                reply['import_exit_code'] == 0 and reply['runtime_qualified'] is False and
                all(type(reply[k]) is str and reply[k].startswith('sha256:') and b.hexid(reply[k][7:], 64)
                    for k in ('runtime_manifest_digest', 'selected_manifest_digest')), 'node_identity')
            require(expected_manifest in (None, reply['runtime_manifest_digest']), 'node_digest_disagreement')
            expected_manifest = reply['runtime_manifest_digest']; node.update(reply); run.save(); dispatched = False
        run.record.update(phase='completed', completed_at_utc=b.now()); run.save(); result = dict(run.record)
    except Exception as error:
        failure = error.code if isinstance(error, b.BuildRefused) else 'preload_failed'
        run.record['phase'] = 'uncertain' if dispatched else 'refused'; run.record['failure'] = failure
        if run.record['nodes'] and run.record['nodes'][-1]['phase'] == 'pending': run.record['nodes'][-1]['phase'] = 'uncertain'
        try: run.save()
        except Exception: pass
    finally:
        if request is not None: request.clear()
        password = None; run.close()
    if failure: raise b.BuildRefused(failure)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('operation', choices=('export', 'preload'))
    for name in ('build-receipt', 'receipt-sha256', 'source-commit', 'runtime-parent'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--config-image-id'); parser.add_argument('--local-image-id')
    parser.add_argument('--export-receipt'); parser.add_argument('--export-sha256'); parser.add_argument('--attempt-id'); args = parser.parse_args()
    try:
        require((args.config_image_id is None) != (args.local_image_id is None), 'image_identity_argument')
        require(args.operation == 'export' or args.local_image_id is None, 'preload_config_identity')
        values = [args.build_receipt, args.receipt_sha256, args.source_commit,
                  args.config_image_id or args.local_image_id, args.runtime_parent]
        require(args.operation == 'preload' or args.attempt_id is None, 'attempt')
        if args.operation == 'export': result = export_image(*values, invoke=export_execute)
        else:
            raw = __import__('sys').stdin.buffer.readline(8193); require(0 < len(raw) <= 8192 and raw.endswith(b'\n'), 'stdin_request')
            request = json.loads(raw, object_pairs_hook=b.unique); require(type(request) is dict and set(request) == {'sudo_password'}, 'stdin_request')
            result = preload(args.build_receipt, args.receipt_sha256, args.export_receipt, args.export_sha256,
                args.source_commit, args.config_image_id, args.runtime_parent, request.pop('sudo_password'), attempt_id=args.attempt_id)
            raw = None
        print(json.dumps({k: result[k] for k in ('phase', 'source_commit', 'image_tag', 'config_image_id', 'runtime_qualified', 'deployed')})); return 0
    except Exception:
        print('Image staging refused or uncertain; inspect protected receipts without replay.', file=__import__('sys').stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
