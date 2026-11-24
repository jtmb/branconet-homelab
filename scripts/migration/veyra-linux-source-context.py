#!/usr/bin/env python3
"""Let the ORIGINAL pinned frontend apply Dockerignore; never approximate it.

This preparatory COPY-only export executes no application/install code. It
requires the complete original compiler admission and owned pinned tools. No
raw APP tree or unqualified broader source view becomes a compiler context.
"""
import json
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import time


def need(value, message):
    if not value:
        raise RuntimeError(message)


def prepare(operator, report, lease_path, receipt, source, probe=False, authority=None):
    if probe:
        path = Path(__file__).with_name('veyra-linux-probe-admission.py')
        spec = importlib.util.spec_from_file_location('veyra_closed_probe_admission', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lease = (module.retained(operator, report, authority, receipt) if authority is not None else
                 module.admit(operator, report, lease_path.absolute()))
    else:
        if authority is None:
            lease = operator.admit(lease_path.absolute(), report)
        else:
            path = Path(__file__).with_name('veyra-linux-rootfs-producer.py')
            spec = importlib.util.spec_from_file_location('veyra_original_full_authority', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            lease = module.retain_full_authority(operator, report, authority, receipt)
    raw, filtered = operator.WORK / 'context', operator.WORK / 'docker-context'
    need(raw.resolve() == raw and raw.is_dir() and not filtered.exists(),
         'Original verified raw context and exclusive filtered output required')
    expected = {item['path']: item for item in source['files']}
    need(not any(line.lstrip().lower().startswith('# syntax=') for line in
                 (raw / 'Dockerfile').read_text().splitlines()),
         'A changed external Dockerfile frontend needs exact source-context qualification')
    for item in source['files']:
        need(operator.sha(raw / item['path']) == item['sha256'], 'Canonical raw source changed')
    for name, (_, digest) in operator.BINARIES.items():
        need(operator.sha(operator.TOOLS / 'bin' / name) == digest, 'Original pinned frontend tool changed')
    recipe, store = operator.WORK / 'context-filter-recipe', operator.WORK / 'context-filter-store'
    need(not recipe.exists() and not store.exists(), 'Never replace previous context preparation/failure')
    recipe.mkdir(mode=0o700)
    (recipe / 'Dockerfile').write_text('FROM scratch AS canonical-source\nCOPY . /\n')
    specific = raw / 'Dockerfile.dockerignore'
    if specific.exists():
        need('Dockerfile.dockerignore' in expected and not specific.is_symlink(),
             'Original Dockerfile-specific ignore must be canonical source')
        with (recipe / 'Dockerfile.dockerignore').open('xb') as output:
            output.write(specific.read_bytes())
    env = operator.stage_env()
    socket = operator.WORK / 'context-filter-socket'
    address = 'unix://' + str(socket)
    runtime = operator.WORK / 'context-filter-runtime'
    runtime.write_text('#!/bin/sh\nset -eu\nexec ' + str(operator.TOOLS / 'bin/buildkit-runc') +
                       ' --root ' + str(operator.WORK / 'context-filter-runc') + ' "$@"\n')
    runtime.chmod(0o700)
    daemon = client = None
    row = {'sourceSha256': report['source']['sourceSha256'], 'path': str(filtered),
           'originalDockerignoreFrontend': True, 'applicationRunInstructions': 0, 'completed': False}
    receipt['sourceContextProjection'] = row
    operator.write_json(operator.WORK / 'result.json', receipt)
    try:
        with (operator.WORK / 'context-filter-daemon.log').open('xb') as daemon_log, \
             (operator.WORK / 'context-filter-build.log').open('xb') as build_log:
            daemon = subprocess.Popen([str(operator.TOOLS / 'bin/buildkitd'), '--root', str(store),
                '--addr', address, '--oci-worker=true', '--containerd-worker=false',
                '--oci-worker-snapshotter', 'overlayfs', '--oci-worker-net', 'host',
                '--oci-worker-binary', str(runtime), '--oci-max-parallelism', '1', '--cdi-disabled'],
                cwd=operator.WORK, env=env, stdin=subprocess.DEVNULL,
                stdout=daemon_log, stderr=daemon_log, start_new_session=True)
            daemon_birth = operator.birth(daemon.pid)
            row['daemon'] = {'pid': daemon.pid, 'startTicks': daemon_birth}
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                need(daemon.poll() is None, 'Original pinned context frontend exited')
                probe = subprocess.run([str(operator.TOOLS / 'bin/buildctl'), '--addr', address,
                    'debug', 'workers'], cwd=operator.WORK, env=env, capture_output=True, timeout=5)
                if probe.returncode == 0:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('Original context frontend did not become ready')
            client = subprocess.Popen([str(operator.TOOLS / 'bin/buildctl'), '--addr', address,
                'build', '--frontend', 'dockerfile.v0', '--local', 'context=' + str(raw),
                '--local', 'dockerfile=' + str(recipe), '--opt', 'target=canonical-source',
                '--opt', 'platform=linux/amd64', '--output', 'type=local,dest=' + str(filtered),
                '--metadata-file', str(operator.WORK / 'context-filter-metadata.json'), '--progress', 'plain'],
                cwd=operator.WORK, env=env, stdin=subprocess.DEVNULL,
                stdout=build_log, stderr=build_log, start_new_session=True)
            client_birth = operator.birth(client.pid)
            row['client'] = {'pid': client.pid, 'startTicks': client_birth}
            while client.poll() is None:
                try:
                    client.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    need(operator.task_allocated() + lease['nativeBudgetBytes'] <= operator.CEILING,
                         'Original paired boundary reached during context preparation')
            row['originalExitCode'] = client.returncode
            need(client.returncode == 0, 'Original Dockerignore frontend failed; preserve original logs')
    finally:
        if client is not None and client.poll() is None:
            need(operator.birth(client.pid) == client_birth, 'Context client identity changed; do not signal')
            os.killpg(client.pid, signal.SIGINT)
            try:
                client.wait(timeout=20)
            except subprocess.TimeoutExpired:
                row['clientStopFailed'] = True
        if (client is None or client.poll() is not None) and daemon is not None and daemon.poll() is None:
            need(operator.birth(daemon.pid) == daemon_birth, 'Context daemon identity changed; do not signal')
            daemon.terminate()
            try:
                daemon.wait(timeout=20)
            except subprocess.TimeoutExpired:
                row['daemonStopFailed'] = True
        row['clientTerminal'] = client is None or client.poll() is not None
        row['daemonTerminal'] = daemon is None or daemon.poll() is not None
        operator.write_json(operator.WORK / 'result.json', receipt)
    need(row['clientTerminal'] and row['daemonTerminal'], 'Context producer remains active; do not advance/clean')
    included = []
    def fail(error):
        raise error
    for directory, names, files in os.walk(filtered, followlinks=False, onerror=fail):
        need(not any((Path(directory) / name).is_symlink() for name in names),
             'Canonical source directory alias requires explicit manifest semantics')
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(filtered).as_posix()
            need(not path.is_symlink() and relative in expected and
                 operator.sha(path) == expected[relative]['sha256'], 'Frontend output is not exact canonical source')
            included.append(relative)
    row.update(completed=True, includedPaths=sorted(included),
               omittedPaths=sorted(set(expected) - set(included)),
               rawDockerignoreSha256=operator.sha(raw / '.dockerignore'))
    operator.write_json(operator.WORK / 'result.json', receipt)
    # Original last-consumer checks, including process/mount/container and
    # diagnostic preservation, remain authoritative for these exact new paths.
    operator.retire_targets(receipt, [store, recipe, runtime, socket,
        operator.WORK / 'context-filter-runc', raw], 'original-context-frontend-last-consumer')
    return row
