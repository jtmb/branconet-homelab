#!/usr/bin/env python3
"""Read the one existing private key directly into RAM; call the pinned HA core.

No key in argv, environment, Ansible variables, module JSON, logs or temp files.
The caller must supply already-existing private F-only controller directories.
"""
import argparse
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import resource
import stat
import sys

FBASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
KEY = FBASE / 'acceptance-ruckus-20261025/hmac-key.hex'
OUT = FBASE / 'ruckus-ha-recovery-20261025'
CORE = Path(__file__).resolve().with_name('ruckus-ha-recovery.py')
CORE_SHA = 'd7c75aecb6c2e2b60de72f7a8c014839ab779230b781f25880f7c803e4ef11d9'
REMOTE_SHA = '8a383106e0e31bef3f59a25fc1f4e886bf8b4110198ff03f08bdb3a5744ace0d'
PHASES = ('baseline', 'plan-cold', 'cold', 'plan-restore', 'restore', 'plan-after', 'after', 'restart')


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def private_dir(path):
    need(path.is_absolute() and path.resolve() == path and path.is_relative_to(FBASE), 'f_directory_location')
    s = path.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == 1000 and stat.S_IMODE(s.st_mode) == 0o700, 'f_directory_owner_mode')
    need(s.st_dev == FBASE.stat().st_dev, 'f_native_device')


def protected_key():
    need(KEY.resolve() == KEY and not KEY.is_symlink(), 'fixed_key_location')
    private_dir(KEY.parent)
    fd = os.open(KEY, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid == 1000 and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1, 'key_owner_mode')
        need(before.st_size in (64, 65), 'key_length')
        raw = os.read(fd, 66)
        need(not os.read(fd, 1) and re.fullmatch(b'[0-9a-fA-F]{64}\n?', raw), 'key_format')
        after = os.fstat(fd); current = KEY.lstat()
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after) == fields(current), 'key_stability')
        return raw.decode('ascii').strip() + '\n'
    finally:
        os.close(fd)


def arguments():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase', choices=PHASES)
    for name in ('baseline', 'cold', 'restored', 'previous'):
        ap.add_argument('--' + name)
        ap.add_argument('--' + name + '-sha256')
    for name in ('reader-run-id', 'reader-pod-uid', 'reader-policy-uid'):
        ap.add_argument('--' + name)
    ap.add_argument('--execute-new-sibling-restore', action='store_true')
    a = ap.parse_args()
    required = set()
    if a.phase != 'baseline': required.add('baseline')
    if a.phase in ('plan-restore', 'restore', 'plan-after', 'after', 'restart'): required.add('cold')
    if a.phase in ('plan-after', 'after', 'restart'): required.add('restored')
    if a.phase == 'restart': required.add('previous')
    argv = [str(CORE), a.phase]
    prefixes = {'baseline': 'baseline', 'cold': 'cold', 'restored': 'restore', 'previous': 'after'}
    for name, prefix in prefixes.items():
        path, checksum = getattr(a, name), getattr(a, name + '_sha256')
        if name not in required:
            need(path is None and checksum is None, 'unexpected_proof_argument')
            continue
        need(isinstance(path, str) and re.fullmatch(re.escape(str(OUT)) + '/' + prefix + '-[0-9a-f]{32}/receipt[.]json', path), 'exact_receipt_path')
        need(re.fullmatch('[0-9a-f]{64}', checksum or ''), 'receipt_checksum')
        argv += ['--' + name, path, '--' + name + '-sha256', checksum]
    reader_required = a.phase in ('cold', 'restore', 'after', 'restart')
    for name, pattern in [('reader_run_id', '[0-9a-f]{12}'), ('reader_pod_uid', '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'), ('reader_policy_uid', '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')]:
        value = getattr(a, name)
        need(bool(value and re.fullmatch(pattern, value)) if reader_required else value is None, 'finite_reader_arguments')
        if reader_required: argv += ['--' + name.replace('_', '-'), value]
    need(a.execute_new_sibling_restore == (a.phase == 'restore'), 'explicit_restore_flag')
    if a.execute_new_sibling_restore: argv.append('--execute-new-sibling-restore')
    return argv


def main():
    argv = arguments()  # --help exits before key or runtime inspection.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077); sys.dont_write_bytecode = True
    need(os.getuid() == os.geteuid() == 1000 and FBASE.is_mount() and FBASE.resolve() == FBASE, 'controller_uid_mount')
    for name in ('HOME', 'TMPDIR', 'TEMP', 'TMP', 'XDG_CACHE_HOME', 'ANSIBLE_LOCAL_TEMP'):
        value = os.environ.get(name, '')
        need(value.startswith(str(FBASE) + '/'), 'explicit_f_environment')
        private_dir(Path(value))
    need(os.environ['TMPDIR'] == os.environ['TEMP'] == os.environ['TMP'], 'one_controller_tmp')
    source = CORE.read_bytes()
    need(CORE.resolve() == CORE and hashlib.sha256(source).hexdigest() == CORE_SHA, 'exact_core_source')
    remote = CORE.with_name('ruckus-ha-recovery-remote.py')
    need(remote.resolve() == remote and hashlib.sha256(remote.read_bytes()).hexdigest() == REMOTE_SHA, 'exact_remote_source')
    # Execute exactly the bytes just hashed, avoiding a second loader read.
    spec = importlib.util.spec_from_file_location('pinned_ruckus_ha_core', CORE)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, str(CORE), 'exec'), module.__dict__)
    previous_stdin, previous_argv = sys.stdin, sys.argv
    secret_stdin = io.StringIO(protected_key())
    try:
        sys.stdin, sys.argv = secret_stdin, argv
        return module.main()
    finally:
        secret_stdin.close()
        sys.stdin, sys.argv = previous_stdin, previous_argv


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # No exception value/traceback: accidental credential text cannot escape.
        print('ruckus_ha_wrapper_refused:' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
