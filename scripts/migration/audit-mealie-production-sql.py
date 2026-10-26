#!/usr/bin/env python3
"""Apply the qualified full-row vendor mapping to a captured production snapshot."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'
SOURCES = ROOT / 'control-source/upstream-mealie-20261026'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['after', 'restart'], required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    assert args.apply and os.getuid() == 1000 and len(args.revision) == 40
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    assert cg.endswith('/branconet-mealie-production-audit-' + args.phase + '-r2-20261026.service')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    assert (group / 'memory.max').read_text().strip() == str(1024**3) and (group / 'memory.swap.max').read_text().strip() == '0'
    assert not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK)
    os.umask(0o077)
    qualified = SOURCES / 'audit-mealie-upstream-copy-r2.py'
    assert hashlib.sha256(qualified.read_bytes()).hexdigest() == '67b169357981ab86418827e51eb7e5ff918eb141b90078de58ba7ea0e428d873'
    tree = ast.parse(qualified.read_bytes())
    program = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'PROGRAM' for t in n.targets))
    report = json.loads((OUT / 'production' / (args.phase + '.json')).read_text())
    assert report['passed'] and report['revision'] == args.revision
    assert json.loads((ROOT / 'operator-control/mealie-cold-sql-proof.json').read_text())['completeSQLMatchesQualifiedOriginalAndLiveBaseline']
    database = OUT / 'production' / (args.phase + '.db')
    original = OUT / 'db-copy/sqlite-original.db'
    assert str(database) == report['databaseCopy'] and database.resolve() == database
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original, database]}
    target = OUT / 'production' / (args.phase + '-mapped-sql.json')
    assert not target.exists()
    cmd = ['/usr/bin/bwrap', '--unshare-all', '--new-session', '--die-with-parent', '--cap-drop', 'ALL',
           '--ro-bind', str(OUT / 'vendor-rootfs'), '/', '--proc', '/proc', '--dev', '/dev',
           '--ro-bind', str(OUT / 'db-copy'), '/mnt', '--bind', str(OUT / 'migration-data'), '/app/data',
           '--ro-bind', str(database), '/app/data/mealie.db', '--bind', str(OUT / 'migration-tmp'), '/tmp',
           '--chdir', '/app', '--clearenv', '--setenv', 'PATH', '/opt/mealie/bin:/usr/bin:/bin',
           '--setenv', 'HOME', '/tmp', '--setenv', 'TMPDIR', '/tmp', '--setenv', 'PRODUCTION', 'true',
           '--setenv', 'TESTING', 'false', '--setenv', 'DATA_DIR', '/app/data', '--',
           '/opt/mealie/bin/python', '-I', '-B', '-c', program]
    prefix = OUT / 'production' / (args.phase + '-mapped-sql')
    with Path(str(prefix) + '.stderr').open('xb') as errors:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=errors, timeout=120)
    assert len(result.stdout) <= 1024**2
    with Path(str(prefix) + '.stdout').open('xb') as stream:
        stream.write(result.stdout)
    packets = [json.loads(line) for line in result.stdout.splitlines() if line.startswith(b'{"passed":')]
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original, database]}
    assert before == after
    accepted = result.returncode == 0 and len(packets) == 1 and packets[0]['passed']
    receipt = {'passed': accepted, 'phase': args.phase, 'revision': args.revision, 'productionModified': False,
               'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'qualifiedAuditSHA256': hashlib.sha256(qualified.read_bytes()).hexdigest(),
               'allDatabaseCopiesUnchanged': True, 'databaseSHA256': after,
               'networkDisabled': True, 'vendorExit': result.returncode,
               'result': packets[0] if accepted else None}
    with target.open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt))
    return int(not accepted)


if __name__ == '__main__':
    raise SystemExit(main())
