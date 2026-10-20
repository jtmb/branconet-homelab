#!/usr/bin/env python3
"""Distinct overlay node protocol. Credentials enter one protected stdin line."""
import hashlib
import importlib.util
import os
import pathlib
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The fixed controller launcher injects the reviewed modules in memory. Local
# source imports do not dispatch anything. No transmitted module is executable
# input: the launcher source itself is pinned/copied by the controller.
if 'IO' not in globals():
    IO = load('overlay_io', 'bortus-compiled-overlay-io.py')
if 'CONTRACT' not in globals():
    CONTRACT = load('overlay_contract', 'bortus-compiled-overlay-contract.py')

CTR = ['sudo', '-n', '/opt/containerd-k8s/bin/ctr', '--address',
       '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']


def command(run, stage, argv, **kwargs):
    return IO.child(run, stage, argv, **kwargs)


def absent(raw, contract):
    IO.require(type(raw) is bytes and len(raw) <= 1024 ** 2, 'inventory_bound')
    lines = raw.decode('utf-8').splitlines()
    IO.require(lines and lines[0].split()[:3] == ['REF', 'TYPE', 'DIGEST']
               and len(lines) <= 16385, 'inventory_header')
    rows = [line.split() for line in lines[1:] if line.split()]
    IO.require(all(len(r) >= 3 and CONTRACT.sha(r[2]) for r in rows), 'inventory_rows')
    IO.require(not any(r[0] in (contract['image_tag'], contract['canonical_alias']) for r in rows),
               'existing_tag')


def authorize(password):
    # Deliberately no new session: subsequent sudo -n shares this timestamp context.
    result = IO.subprocess.run(['sudo', '-S', '-p', '', '-v'], input=password.encode() + b'\n',
                               stdout=IO.subprocess.DEVNULL, stderr=IO.subprocess.DEVNULL,
                               timeout=30, check=False, start_new_session=False)
    return result.returncode == 0


def password_ok(password):
    IO.require(type(password) is str and 0 < len(password.encode()) <= 4096
               and not any(c in password for c in '\0\r\n'), 'stdin_authorization')


def request_contract(request, expected_host):
    fields = {'format', 'purpose', 'contract_raw', 'contract_sha256', 'envelope',
              'export_execution_sha256', 'sudo_password'}
    IO.require(type(request) is dict and len(IO.encoded(request)) <= 256 * 1024 and set(request) == fields
               and request['format'] == IO.FORMAT and request['purpose'] == 'node-preload'
               and request['contract_sha256'] == IO.CONTRACT_PIN
               and type(request['contract_raw']) is str, 'node_protocol')
    contract = CONTRACT.load_contract(request['contract_raw'].encode(), IO.CONTRACT_PIN)
    export = CONTRACT.encoded(CONTRACT.expected_export_record(contract))
    candidates = CONTRACT.preload_envelopes(contract, export, IO.digest(export))
    IO.require(expected_host in CONTRACT.HOSTS
               and IO.encoded(request['envelope']) == IO.encoded(candidates[CONTRACT.HOSTS.index(expected_host)])
               and CONTRACT.hexid(request['export_execution_sha256']), 'node_envelope')
    return contract


def reply_for(contract, envelope, export_pin):
    return {'format': IO.FORMAT, 'purpose': 'node-preload', 'phase': 'completed',
            'host': envelope['host'], 'ordinal': envelope['ordinal'],
            'contract_sha256': IO.CONTRACT_PIN, 'export_execution_sha256': export_pin,
            'source_commit': contract['source_commit'], 'archive_sha256': contract['archive_sha256'],
            'archive_bytes': contract['archive_bytes'], 'manifest_digest': contract['manifest_digest'],
            'raw_config_digest': contract['raw_config_digest'], 'import_exit_code': 0,
            'packaging_content_matches': True, 'runtime_qualified': False, 'deployed': False}


def receive(request, source, home, expected_host, invoke=command, authenticate=authorize):
    """Full byte pin before import, then exact direct-OCI/config observations."""
    run, password, dispatched = None, None, False
    try:
        contract = request_contract(request, expected_host)
        password = request.pop('sudo_password')
        password_ok(password)
        run = IO.Run(home, contract['source_commit'], 'node')
        run.record.update(host=expected_host, ordinal=request['envelope']['ordinal'],
                          contract_sha256=IO.CONTRACT_PIN,
                          export_execution_sha256=request['export_execution_sha256'])
        run.save()
        IO.require(authenticate(password), 'authorization')
        password = None
        absent(invoke(run, 'images-before', CTR + ['images', 'list'], cap=1024 ** 2), contract)
        with os.fdopen(run.create('image.tar'), 'w+b') as archive:
            count, hashed = 0, hashlib.sha256()
            while True:
                raw = source.read(min(65536, contract['archive_bytes'] - count + 1))
                if not raw:
                    break
                count += len(raw)
                IO.require(count <= contract['archive_bytes'], 'archive_bound')
                archive.write(raw)
                hashed.update(raw)
            IO.require(count == contract['archive_bytes'] and hashed.hexdigest() == contract['archive_sha256'],
                       'archive_identity')
            archive.flush()
            os.fsync(archive.fileno())
            os.fsync(run.fd)
            run.inputs['image.tar'] = IO.stable(os.fstat(archive.fileno()))
            absent(invoke(run, 'images-preimport', CTR + ['images', 'list'], cap=1024 ** 2), contract)
            run.check('image.tar', archive.fileno())
            run.record['phase'] = 'pending'
            run.save()
            run.check('image.tar', archive.fileno())
            dispatched = True
            invoke(run, 'import', CTR + ['images', 'import', str(run.directory / 'image.tar')],
                   timeout=1200, cap=65536)
            run.check('image.tar', archive.fileno())
        inventory = invoke(run, 'images-after', CTR + ['images', 'list'], cap=1024 ** 2)
        manifest = invoke(run, 'manifest', CTR + ['content', 'get', contract['manifest_digest']])
        config = invoke(run, 'config', CTR + ['content', 'get', contract['raw_config_digest']])
        CONTRACT.verify_node_observation(request['envelope'], contract,
            request['envelope']['export_record_sha256'], inventory, manifest, config)
        with run.opened('image.tar', contract['archive_sha256']):
            pass
        reply = reply_for(contract, request['envelope'], request['export_execution_sha256'])
        run.record.update(reply)
        run.save()
        return reply
    except BaseException:
        if run is not None:
            run.record.update(phase='uncertain' if dispatched else 'refused', failure='node_staging_failed')
            try:
                run.save()
            except Exception:
                pass  # The durable pending record remains if completion cannot be persisted.
        raise RuntimeError('node_staging_failed') from None
    finally:
        if type(request) is dict:
            request.pop('sudo_password', None)
        password = None
        if run is not None:
            run.close()


def main(expected_host=None):
    try:
        # Only the fixed SSH launcher supplies the host out of band. Standalone
        # invocation cannot infer its host from untrusted request data.
        IO.require(expected_host in CONTRACT.HOSTS, 'bound_host_required')
        raw = sys.stdin.buffer.readline(256 * 1024 + 1)
        IO.require(0 < len(raw) <= 256 * 1024 and raw.endswith(b'\n'), 'request_bound')
        request = IO.decode(raw)
        raw = None
        reply = receive(request, sys.stdin.buffer, pathlib.Path.home(), expected_host)
        print(IO.encoded(reply).decode(), flush=True)
        return 0
    except BaseException:
        print('Overlay node staging refused or uncertain; inspect protected record.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
