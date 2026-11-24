#!/usr/bin/env python3
"""Prepare an immutable raw-Git BORTUS Docker context; never build or deploy."""
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile

PREFIX = 'k8s-rewrite/front-end/'
MAX_FILES = 2000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
REQUIRED = {'Dockerfile', 'package.json', 'package-lock.json',
            'docker-entrypoint.sh', 'prisma/schema.prisma'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(repo, args, limit):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30)
    require(result.returncode == 0 and len(result.stdout) <= limit,
            'Bounded source query failed; Git output withheld')
    return result.stdout


def excluded(path):
    parts = pathlib.PurePosixPath(path).parts
    name = parts[-1].lower()
    return (any(p.lower() in {'node_modules', '.next', '.git', 'tests', 'coverage'}
                or p.lower().startswith('.env') for p in parts)
            or bool(re.search(r'\.(?:db|sqlite|sqlite3)(?:$|[-.])', name))
            or name.endswith(('.log', '.tmp', '.tsbuildinfo', '.pem', '.key', '.p12', '.pfx'))
            or name in {'id_ed25519', 'id_rsa', 'kubeconfig', 'admin.conf'})


def entries(repo, commit):
    require(bool(re.fullmatch(r'[0-9a-f]{40}', commit)), 'Exact full source commit required')
    require(git(repo, ['rev-parse', commit + '^{commit}'], 128).decode().strip() == commit,
            'Source commit differs')
    raw = git(repo, ['ls-tree', '-r', '-l', '-z', commit, '--', PREFIX], 2 * 1024 * 1024)
    rows = raw.split(b'\0')
    require(len(rows) <= MAX_FILES + 1 and rows[-1] == b'', 'Source entry bound exceeded')
    included, skipped, total = [], 0, 0
    for row in rows[:-1]:
        fields, encoded_path = row.split(b'\t', 1)
        mode, kind, blob, size = fields.decode('ascii').split()
        path = encoded_path.decode('utf-8')
        require(path.startswith(PREFIX), 'Source path escaped application tree')
        name = path[len(PREFIX):]
        parts = pathlib.PurePosixPath(name).parts
        require(name and not name.startswith('/') and '\\' not in name and ':' not in name
                and all(p not in ('', '.', '..') for p in parts)
                and not any(ord(c) < 32 or ord(c) == 127 for c in name), 'Invalid source path')
        if excluded(name):
            skipped += 1
            continue  # Excluded payloads are never read from Git.
        require(kind == 'blob' and mode in ('100644', '100755')
                and bool(re.fullmatch(r'[0-9a-f]{40}', blob)), 'Unsupported source entry')
        count = int(size)
        require(0 <= count <= MAX_FILE_BYTES, 'Source file byte bound exceeded')
        total += count
        require(total <= MAX_TOTAL_BYTES, 'Source total byte bound exceeded')
        included.append({'path': name, 'mode': mode, 'git_blob': blob, 'bytes': count})
    require(REQUIRED <= {e['path'] for e in included}, 'Required release source absent')
    return included, skipped, total


def prepare(repo, commit, output, evidence):
    repo, output, evidence = map(pathlib.Path, (repo, output, evidence))
    require(output.resolve() != evidence.resolve(), 'Distinct output paths required')
    require(all(p.parent.is_dir() and not os.path.lexists(p) for p in (output, evidence)),
            'Existing output parent and new output paths required')
    require(all(not p.resolve().is_relative_to(repo.resolve()) for p in (output, evidence)),
            'Release artifacts must remain outside source checkout')
    selected, skipped, total = entries(repo, commit)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tree = git(repo, ['rev-parse', commit + ':' + PREFIX.rstrip('/')], 128).decode().strip()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    # On failure retain the partial exclusive artifact; never overwrite or remove it.
    with os.fdopen(fd, 'wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                for entry in selected:
                    raw = git(repo, ['cat-file', 'blob', entry['git_blob']], MAX_FILE_BYTES)
                    require(len(raw) == entry['bytes'] and hashlib.sha1(
                        b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['git_blob'],
                        'Raw source blob differs')
                    entry['sha256'] = hashlib.sha256(raw).hexdigest()
                    member = tarfile.TarInfo(entry['path'])
                    member.size = len(raw)
                    member.mode = 0o755 if entry['mode'] == '100755' else 0o644
                    member.mtime = member.uid = member.gid = 0
                    archive.addfile(member, io.BytesIO(raw))
        stream.flush()
        os.fsync(stream.fileno())
    digest = hashlib.sha256()
    with output.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    migrations = [e for e in selected if e['path'].startswith('prisma/migrations/')
                  and e['path'].endswith('/migration.sql')]
    record = {'scope': 'Immutable raw-Git build context only; no image or release acceptance',
              'source_commit': commit, 'application_tree': tree, 'source_prefix': PREFIX,
              'started_at_utc': started,
              'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'context_sha256': digest.hexdigest(), 'context_bytes': output.stat().st_size,
              'source_bytes': total, 'included_files': len(selected), 'excluded_entries': skipped,
              'files': selected, 'migrations': migrations, 'working_tree_read': False,
              'excluded_payloads_read': False, 'dependencies_installed': False,
              'image_built': False, 'cluster_mutations': 0, 'live_acceptance': False}
    fd = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', type=pathlib.Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--evidence', type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        record = prepare(args.source_repo, args.source_commit, args.output, args.evidence)
        print(json.dumps({k: record[k] for k in ('source_commit', 'context_sha256',
              'included_files', 'excluded_entries', 'image_built', 'cluster_mutations')}))
        return 0
    except Exception:
        print('Release context preparation failed; retained artifacts require inspection. '
              'Private source and Git output withheld.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
