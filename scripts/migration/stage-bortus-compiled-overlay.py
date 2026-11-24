#!/usr/bin/env python3
"""Separate compiled-overlay export/preload adapters; no runtime/deployment acceptance."""
import argparse
import importlib.util
import os
import pathlib
import shlex
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IO = load('overlay_io', 'bortus-compiled-overlay-io.py')
C = load('overlay_contract', 'bortus-compiled-overlay-contract.py')
N = load('overlay_node', 'bortus-compiled-overlay-node.py')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ForwardAgent=no',
       '-o', 'ConnectTimeout=15', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']


def pinned(run, source, name, pin, limit=IO.MAX_METADATA):
    run.copy(source, name, limit)
    with run.opened(name, pin) as stream:
        return stream.read(limit + 1)


def contract_input(path, pin):
    # A preliminary read only derives the deterministic run name; the owned copy
    # is independently opened/hashed/validated before any child dispatch.
    IO.require(pin == IO.CONTRACT_PIN, 'exact_contract_pin')
    path = pathlib.Path(path)
    anchors = IO.anchors_for(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=anchors[-1][1])
        with os.fdopen(fd, 'rb') as stream:
            initial = os.fstat(stream.fileno())
            IO.require(IO.stat.S_ISREG(initial.st_mode) and initial.st_uid == os.getuid()
                       and IO.stat.S_IMODE(initial.st_mode) & 0o022 == 0 and initial.st_nlink == 1
                       and 0 < initial.st_size <= IO.MAX_METADATA, 'contract_file')
            raw = stream.read(IO.MAX_METADATA + 1)
            IO.check_anchors(anchors)
            IO.require(IO.stable(initial) == IO.stable(os.fstat(stream.fileno()))
                       == IO.stable(path.lstat()), 'contract_changed')
    finally:
        for _, fd, _ in reversed(anchors):
            os.close(fd)
    return C.load_contract(raw, pin)


def inspect(run, stage, contract, invoke):
    template = '{"id":{{json .Id}},"labels":{' + ','.join(
        IO.encoded(k).decode() + ':{{json (index .Config.Labels ' + IO.encoded(k).decode() + ')}}'
        for k in sorted(contract['labels'])) + '}}'
    raw = invoke(run, stage, ['docker', 'image', 'inspect', '--format', template, contract['image_tag']])
    IO.require(IO.decode(raw) == {'id': contract['local_image_id'], 'labels': contract['labels']},
               'source_identity')


def export_image(contract_path, contract_pin, parent, invoke=IO.child):
    contract = contract_input(contract_path, contract_pin)
    run = IO.Run(parent, contract['source_commit'], 'export')
    dispatched = False
    try:
        raw = pinned(run, contract_path, 'contract.json', contract_pin)
        contract = C.load_contract(raw, contract_pin)
        run.record['contract_sha256'] = contract_pin
        inspect(run, 'source-before', contract, invoke)
        with os.fdopen(run.create('image.tar'), 'w+b') as archive:
            run.record['phase'] = 'pending'
            run.save()
            dispatched = True
            invoke(run, 'save', ['docker', 'image', 'save', contract['image_tag']],
                   output=archive, cap=contract['archive_bytes'], timeout=1200)
            archive.flush()
            os.fsync(archive.fileno())
            os.fsync(run.fd)
            run.inputs['image.tar'] = IO.stable(os.fstat(archive.fileno()))
            run.check('image.tar', archive.fileno())
            C.verify_archive(archive, contract)
            run.check('image.tar', archive.fileno())
        inspect(run, 'source-after', contract, invoke)
        with run.opened('image.tar', contract['archive_sha256']):
            pass  # Keep the retained archive stable through the last metadata query.
        packaging = C.expected_export_record(contract)
        result = {'format': IO.FORMAT, 'purpose': 'export', 'phase': 'completed',
                  'owner': run.record['owner'], 'source_commit': contract['source_commit'],
                  'contract_sha256': contract_pin, 'save_exit_code': 0,
                  'packaging_record': packaging, 'archive_path': str(run.directory / 'image.tar'),
                  'runtime_qualified': False, 'deployed': False}
        # The execution receipt has a distinct closed shape. The expected
        # packaging record/envelope alone never satisfies preload's receipt.
        run.record = result
        run.save()
        return dict(result)
    except BaseException:
        run.record.update(phase='uncertain' if dispatched else 'refused', failure='export_failed')
        try:
            run.save()
        except Exception:
            pass
        raise RuntimeError('export_failed') from None
    finally:
        run.close()


def execution_receipt(raw, contract, contract_pin):
    value = IO.decode(raw)
    expected = {'format', 'purpose', 'phase', 'owner', 'source_commit', 'contract_sha256',
                'save_exit_code', 'packaging_record', 'archive_path', 'runtime_qualified', 'deployed'}
    IO.require(type(value) is dict and set(value) == expected and value['format'] == IO.FORMAT
               and value['purpose'] == 'export' and value['phase'] == 'completed'
               and type(value['save_exit_code']) is int and value['save_exit_code'] == 0
               and value['source_commit'] == contract['source_commit']
               and value['contract_sha256'] == contract_pin
               and value['runtime_qualified'] is False and value['deployed'] is False
               and IO.encoded(value['packaging_record']) == IO.encoded(C.expected_export_record(contract))
               and type(value['owner']) is str
               and str(IO.uuid.UUID(value['owner'])) == value['owner']
               and type(value['archive_path']) is str and pathlib.Path(value['archive_path']).is_absolute(),
               'export_execution_receipt')
    return value


def launcher(run, host, sources):
    """Pinned static source in argv; credentials/archive exclusively on stdin."""
    IO.require(host in C.HOSTS and set(sources) == {'io', 'contract', 'node'}, 'launcher')
    code = 'import types\n'
    for key, injected in (('io', {}), ('contract', {}), ('node', {'IO': 'io', 'CONTRACT': 'contract'})):
        code += key + '=types.ModuleType(' + repr('overlay_' + key) + ')\n'
        code += key + '.__file__=' + repr('/reviewed-overlay/' + key + '.py') + '\n'
        for target, module in injected.items():
            code += key + '.__dict__[' + repr(target) + ']=' + module + '\n'
        code += 'exec(compile(' + repr(sources[key].decode('utf-8')) + ',' + repr(key) + ',"exec"),' + key + '.__dict__)\n'
    code += 'raise SystemExit(node.main(' + repr(host) + '))\n'
    return SSH + ['james@' + host, 'python3 -c ' + shlex.quote(code)]


def transport(run, host, request, archive, sources):
    argv = launcher(run, host, sources)
    prefix = IO.encoded(request) + b'\n'
    IO.require(len(prefix) <= 256 * 1024, 'request_bound')
    try:
        return IO.decode(IO.child(run, host, argv, source=archive, prefix=prefix, cap=65536, timeout=1200))
    finally:
        prefix = None


def preload(contract_path, contract_pin, export_path, export_pin, parent, password, invoke=transport):
    N.password_ok(password)
    contract = contract_input(contract_path, contract_pin)
    IO.require(C.hexid(export_pin), 'export_pin')
    run = IO.Run(parent, contract['source_commit'], 'preload')
    dispatched, request = False, None
    try:
        contract_raw = pinned(run, contract_path, 'contract.json', contract_pin)
        contract = C.load_contract(contract_raw, contract_pin)
        exported = execution_receipt(pinned(run, export_path, 'export.json', export_pin), contract, contract_pin)
        run.copy(exported['archive_path'], 'image.tar', IO.MAX_ARCHIVE)
        with run.opened('image.tar', contract['archive_sha256']) as archive:
            C.verify_archive(archive, contract)
        sources = {}
        for key, filename in (('io', 'bortus-compiled-overlay-io.py'),
                              ('contract', 'bortus-compiled-overlay-contract.py'),
                              ('node', 'bortus-compiled-overlay-node.py')):
            source = pathlib.Path(__file__).with_name(filename)
            # Source provenance is the caller's reviewed tooling checkpoint;
            # stable copies and hashes are bound before SSH, never read again.
            run.copy(source, key + '.py', IO.MAX_METADATA)
            with os.fdopen(os.open(key + '.py', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                   dir_fd=run.fd), 'rb') as stream:
                run.check(key + '.py', stream.fileno())
                sources[key] = stream.read(IO.MAX_METADATA + 1)
                run.check(key + '.py', stream.fileno())
        run.record.update(contract_sha256=contract_pin, export_execution_sha256=export_pin,
                          source_sha256={k: IO.digest(v) for k, v in sources.items()})
        packaging = C.encoded(C.expected_export_record(contract))
        for envelope in C.preload_envelopes(contract, packaging, IO.digest(packaging)):
            node = {'host': envelope['host'], 'ordinal': envelope['ordinal'], 'phase': 'pending'}
            run.record['nodes'].append(node)
            run.record['phase'] = 'pending'
            run.save()
            request = {'format': IO.FORMAT, 'purpose': 'node-preload', 'contract_raw': contract_raw.decode(),
                       'contract_sha256': contract_pin, 'envelope': envelope,
                       'export_execution_sha256': export_pin, 'sudo_password': password}
            with run.opened('image.tar', contract['archive_sha256']) as archive:
                dispatched = True
                reply = invoke(run, envelope['host'], request, archive, sources)
            request.clear()
            IO.require(IO.encoded(reply) == IO.encoded(N.reply_for(contract, envelope, export_pin)), 'node_reply')
            node.update(reply)
            run.save()
            dispatched = False
        run.record['phase'] = 'completed'
        run.save()
        return dict(run.record)
    except BaseException:
        run.record.update(phase='uncertain' if dispatched else 'refused', failure='preload_failed')
        if run.record['nodes'] and run.record['nodes'][-1]['phase'] == 'pending':
            run.record['nodes'][-1]['phase'] = 'uncertain' if dispatched else 'refused'
        try:
            run.save()
        except Exception:
            pass
        raise RuntimeError('preload_failed') from None
    finally:
        if request is not None:
            request.clear()
        password = None
        run.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('export', 'preload'))
    parser.add_argument('--contract', required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--runtime-parent', required=True)
    parser.add_argument('--export-receipt')
    parser.add_argument('--export-sha256')
    args = parser.parse_args()
    try:
        if args.operation == 'export':
            IO.require(args.export_receipt is None and args.export_sha256 is None, 'export_options')
            result = export_image(args.contract, args.contract_sha256, args.runtime_parent)
        else:
            IO.require(args.export_receipt is not None and args.export_sha256 is not None, 'preload_options')
            raw = sys.stdin.buffer.readline(8193)
            IO.require(0 < len(raw) <= 8192 and raw.endswith(b'\n'), 'stdin_bound')
            auth = IO.decode(raw)
            raw = None
            IO.require(type(auth) is dict and set(auth) == {'sudo_password'}, 'stdin_shape')
            try:
                result = preload(args.contract, args.contract_sha256, args.export_receipt,
                                 args.export_sha256, args.runtime_parent, auth['sudo_password'])
            finally:
                auth.clear()
        print(IO.encoded(result).decode(), flush=True)
        return 0
    except BaseException:
        print('Overlay staging refused or uncertain; inspect protected record.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
