#!/usr/bin/env python3
"""One real Unpackerr ZIP -> mock Radarr import -> cleanup qualification.

Run in WSL/Linux with an extracted, reviewed binary and its expected SHA256:
  python3 scripts/migration/qualify-unpackerr-fixture.py \
    --binary /absolute/path/unpackerr --sha256 EXACT_BINARY_SHA256

Use --expected-go-version 1.27.0 for the reviewed official 0.16.1 binary;
the legacy custom-image profile defaults to 1.27.3. This is an identity check,
not a statement that either toolchain is free of vulnerabilities.

Requires Python 3.11+, util-linux unshare, and unprivileged user/network namespaces.
Refuses missing isolation; never falls back to the host network. All evidence is
retained under the dedicated native build mount. No Docker, NAS, credentials,
production configuration, image build, scan or automatic deletion is involved.
This exercises ZIP and the queue-disappearance cleanup contract, not real Radarr
import, multipart/encrypted formats, all security limits, or production ACLs.
"""
import argparse
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
import zipfile

BASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
TIMEOUT = 120
TITLE = 'Branconet.Unpackerr.Disposable.Fixture'
PAYLOADS = {'movie.mkv': bytes(range(256)) * 16,
            'Subs/fixture.srt': b'1\n00:00:00,000 --> 00:00:01,000\nUnpackerr fixture only.\n'}


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def snapshot(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode), 'expected regular fixture file: ' + str(path))
    return {'sha256': sha(path), 'bytes': info.st_size, 'uid': info.st_uid,
            'gid': info.st_gid, 'mode': oct(stat.S_IMODE(info.st_mode))}


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 ** 2, 4 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    # Do not constrain virtual address space: Go reserves large sparse mappings.


def isolated(args):
    work = args.run_dir
    result = {'status': 'failed', 'fixture': 'zip-radarr-postimport-cleanup',
              'binarySHA256': args.sha256, 'expectedGoVersion': args.expected_go_version, 'milestones': [], 'limitations': [
                  'Mock queue disappearance simulates import; no real Radarr importer.',
                  'ZIP only; no encrypted/multipart archive or security-limit qualification.',
                  'Ownership is the invoking Linux UID/GID through a user namespace, not NAS ACLs.',
                  'Network namespace isolation is not a complete filesystem sandbox.']}
    process = None
    server = None
    server_thread = None
    started = time.monotonic()
    try:
        need(os.stat('/proc/self/ns/net').st_ino != args.parent_netns, 'host network namespace refused')
        need(os.getuid() == 0 and os.getgid() == 0, 'expected mapped namespace root')
        need([name for _, name in socket.if_nameindex()] == ['lo'], 'non-loopback interface refused')
        # Bring up only the new namespace's loopback, without needing iproute2.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            request = struct.pack('16sH14x', b'lo', 0)
            flags = struct.unpack('16sH14x', fcntl.ioctl(sock, 0x8913, request))[1]
            fcntl.ioctl(sock, 0x8914, struct.pack('16sH14x', b'lo', flags | 1))
        result['networkNamespace'] = os.readlink('/proc/self/ns/net')
        result['interfaces'] = ['lo']
        result['uidMap'] = Path('/proc/self/uid_map').read_text().strip()
        result['gidMap'] = Path('/proc/self/gid_map').read_text().strip()
        # Match the measured production umask0022 inside this disposable namespace.
        # The private outer evidence directory remains0700.
        os.umask(0o022)
        need(sha(args.binary) == args.sha256, 'copied binary checksum mismatch')
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work / 'tmp'),
               'LANG': 'C.UTF-8', 'TZ': 'UTC', 'GOMAXPROCS': '1', 'GOMEMLIMIT': '256MiB'}
        (work / 'tmp').mkdir()
        version = subprocess.check_output([str(args.binary), '--version'], env=env, cwd=work,
                                          timeout=10, preexec_fn=limits).decode()
        need(re.search(r'unpackerr, version 0\.16\.1(?:\s|$)', version) is not None
             and re.search(r'\bgo' + re.escape(args.expected_go_version) + r'\b', version) is not None,
             'unexpected application/toolchain version')
        result['version'] = version.strip()
        downloads = work / 'downloads'
        item = downloads / TITLE
        item.mkdir(parents=True)
        library = work / 'mock-library'
        library.mkdir()
        archive = item / 'fixture.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_STORED) as output:
            for name, content in PAYLOADS.items():
                member = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                member.external_attr = (stat.S_IFREG | 0o644) << 16
                output.writestr(member, content)
        archive.chmod(0o600)
        sentinel = item / 'original-download.nfo'
        sentinel.write_bytes(b'Preexisting download metadata must survive.\n')
        sentinel.chmod(0o600)
        outside = work / 'outside-sentinel.txt'
        outside.write_bytes(b'Outside the extraction tree must survive.\n')
        outside.chmod(0o600)
        retained = {str(path.relative_to(work)): snapshot(path) for path in [archive, sentinel, outside]}
        state = {'imported': False, 'requests': []}

        class MockRadarr(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def reject_write(self):
                state['requests'].append({'method': self.command, 'path': urlsplit(self.path).path,
                                          'imported': state['imported']})
                self.send_error(405, 'Read-only disposable mock')

            do_POST = reject_write
            do_PUT = reject_write
            do_PATCH = reject_write
            do_DELETE = reject_write

            def do_GET(self):
                path = urlsplit(self.path).path
                state['requests'].append({'method': 'GET', 'path': path, 'imported': state['imported']})
                records = [] if state['imported'] else [{
                    'id': 1, 'movieId': 1, 'title': TITLE, 'status': 'completed',
                    'protocol': 'torrent', 'size': archive.stat().st_size, 'sizeleft': 0,
                    'downloadId': 'DISPOSABLE-FIXTURE-ONLY', 'outputPath': str(item),
                    'trackedDownloadStatus': 'warning', 'trackedDownloadState': 'importPending',
                    'statusMessages': []}]
                body = {'page': 1, 'pageSize': 2000, 'totalRecords': len(records), 'records': records}
                data = json.dumps(body if path == '/api/v3/queue' else {'error': 'unexpected fixture route'}).encode()
                self.send_response(200 if path == '/api/v3/queue' else 404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(('127.0.0.1', 0), MockRadarr)
        # All paths and the dummy API key are generated locally; no live config is loaded.
        config = work / 'fixture.conf'
        config.write_text('debug = true\ninterval = "15s"\nstart_delay = "1s"\n'
                          'delete_delay = "2s"\nretry_delay = "1m"\nmax_retries = 2\n'
                          'parallel = 1\nfile_mode = "0644"\ndir_mode = "0755"\n'
                          'remnant_action = "rename"\nlog_file = ""\n'
                          '[webserver]\nmetrics = false\n[[radarr]]\n'
                          f'url = "http://127.0.0.1:{server.server_port}"\n'
                          'api_key = "00000000000000000000000000000000"\n'
                          f'paths = [{json.dumps(str(downloads))}]\n'
                          'protocols = "torrent"\ndelete_orig = false\ndelete_delay = "2s"\n')
        config.chmod(0o600)
        log = work / 'unpackerr.log'
        with log.open('xb') as stream:
            process = subprocess.Popen([str(args.binary), '--config', str(config)], cwd=work,
                                       env=env, stdin=subprocess.DEVNULL, stdout=stream,
                                       stderr=subprocess.STDOUT, preexec_fn=limits)
        # Start the mock thread after fork/preexec to avoid threaded preexec hazards.
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        deadline = time.monotonic() + TIMEOUT

        def wait_for(predicate, failure):
            while time.monotonic() < deadline:
                need(process.poll() is None, 'binary exited before fixture completed')
                need(log.stat().st_size <= 4 * 1024 ** 2, 'fixture log exceeded bound')
                if predicate():
                    return
                time.sleep(0.25)
            raise RuntimeError(failure)

        def extracted():
            return all((item / name).is_file() and (item / name).read_bytes() == content
                       for name, content in PAYLOADS.items()) and 'Extraction Finished:' in log.read_text(errors='replace')

        wait_for(extracted, 'timed out waiting for actual extraction')
        before_import = {name: snapshot(item / name) for name in PAYLOADS}
        for row in before_import.values():
            need(row['uid'] == 0 and row['gid'] == 0 and row['mode'] == '0o644', 'extracted ownership/mode mismatch')
        need(stat.S_IMODE((item / 'Subs').stat().st_mode) == 0o755, 'extracted directory mode mismatch')
        result['extracted'] = before_import
        result['milestones'].append('real ZIP extraction completed with exact content and ownership')
        hold_until = time.monotonic() + 7  # Beyond the configured delay and a cleaner tick.
        while time.monotonic() < hold_until:
            need(extracted(), 'output disappeared while mock queue still retained the item')
            time.sleep(0.25)
        for name, content in PAYLOADS.items():
            target = library / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item / name, target)
            need(target.read_bytes() == content, 'mock imported copy mismatch')
        state['imported'] = True  # Queue disappearance is Unpackerr's import signal.
        result['milestones'].append('verified output copied to mock library; queue item removed')
        wait_for(lambda: all(not (item / name).exists() for name in PAYLOADS),
                 'timed out waiting for post-import extraction cleanup')
        need(any(row['imported'] for row in state['requests']), 'empty queue was never observed')
        need(all(row['method'] == 'GET' and row['path'] == '/api/v3/queue' for row in state['requests']),
             'unexpected HTTP method/route')
        for relative, expected in retained.items():
            need(snapshot(work / relative) == expected, 'archive/preexisting sentinel changed: ' + relative)
        need(all((library / name).read_bytes() == content for name, content in PAYLOADS.items()),
             'mock imported content changed during cleanup')
        need(not (item / 'Subs').exists(), 'empty extracted parent directory was not cleaned')
        result.update(status='passed', retained=retained,
                      imported={name: snapshot(library / name) for name in PAYLOADS},
                      mockRequests=state['requests'], cleanupDeletedOnlyExtractedPayloads=True)
        result['milestones'].append('post-import cleanup removed extracted files; original/archive/library retained')
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if server is not None:
            if server_thread is not None and server_thread.is_alive():
                server.shutdown()
            server.server_close()
        result['elapsedSeconds'] = round(time.monotonic() - started, 3)
        write_json(work / 'result.json', result)
    return 0 if result['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--expected-go-version', choices=['1.27.3', '1.27.0'], default='1.27.3',
                        help='Explicit legacy custom or official vendor toolchain; never a security-fix claim')
    parser.add_argument('--run-dir', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--parent-netns', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    need(sys.platform == 'linux', 'run using native WSL/Linux Python')
    need(re.fullmatch('[0-9a-f]{64}', args.sha256), 'expected exact lowercase binary SHA256')
    if args.run_dir is not None:
        return isolated(args)
    need(BASE.is_mount() and BASE.stat().st_dev != Path('/').stat().st_dev, 'dedicated native build mount required')
    binary = args.binary
    need(binary.is_absolute() and binary.resolve() == binary and binary.is_file() and not binary.is_symlink(),
         'binary must be an absolute regular nonsymlink path')
    need(binary.stat().st_size <= 64 * 1024 ** 2 and sha(binary) == args.sha256, 'binary size/checksum mismatch')
    unshare = shutil.which('unshare')
    need(unshare is not None, 'util-linux unshare is required; no network fallback')
    work = Path(tempfile.mkdtemp(prefix='unpackerr-fixture-', dir=BASE))
    copy = work / 'unpackerr'
    shutil.copyfile(binary, copy)
    copy.chmod(0o700)
    command = [unshare, '--user', '--map-root-user', '--net', '--fork', '--kill-child=SIGKILL',
               sys.executable, str(Path(__file__).resolve()), '--binary', str(copy), '--sha256', args.sha256,
               '--expected-go-version', args.expected_go_version,
               '--run-dir', str(work), '--parent-netns', str(os.stat('/proc/self/ns/net').st_ino)]
    with (work / 'isolation.log').open('xb') as output:
        child = subprocess.Popen(command, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            code = child.wait(timeout=150)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
            code = 1
    report_path = work / 'result.json'
    if report_path.exists():
        report = json.loads(report_path.read_bytes())
    else:
        report = {'status': 'failed', 'error': 'isolation setup failed or fixture exceeded wall timeout'}
    report['evidenceDirectory'] = str(work)
    report['externalUid'] = os.getuid()
    report['externalGid'] = os.getgid()
    report['externalRetainedOwnershipVerified'] = False
    if code == 0 and report.get('status') == 'passed':
        try:
            for relative in report['retained']:
                info = (work / relative).stat()
                need((info.st_uid, info.st_gid) == (os.getuid(), os.getgid()), 'external retained ownership mismatch')
            for name in PAYLOADS:
                info = (work / 'mock-library' / name).stat()
                need((info.st_uid, info.st_gid) == (os.getuid(), os.getgid()), 'external imported ownership mismatch')
            report['externalRetainedOwnershipVerified'] = True
        except Exception as error:
            report['status'] = 'failed'
            report['error'] = str(error)
    else:
        report['status'] = 'failed'
    write_json(report_path, report)
    print(json.dumps({'status': report['status'], 'evidenceDirectory': str(work),
                      'result': str(report_path), 'binarySHA256': args.sha256}, sort_keys=True))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'refused', 'error': str(error)}), file=sys.stderr)
        raise SystemExit(1)
