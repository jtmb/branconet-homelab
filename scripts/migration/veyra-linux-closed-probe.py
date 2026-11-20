#!/usr/bin/env python3
"""Closed source-context / OCI / ownership / capabilities transport control.

Only literal control programs and signed libcap OS tools run. No application
dependencies, npm scripts, Cargo/TypeScript compile, image publish or deployment.
"""
import argparse
import base64
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True


def load(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def need(value, message):
    if not value:
        raise RuntimeError(message)


ISOLATION = r'''
const fs = require('node:fs');
const assert = require('node:assert/strict');
const status = fs.readFileSync('/proc/self/status', 'utf8');
const value = key => status.match(new RegExp('^' + key + ':\\s*(\\S+)', 'm'))?.[1];
const caps = BigInt('0x' + value('CapEff'));
for (const bit of [16n, 17n, 19n, 21n, 22n, 23n, 38n, 39n]) assert.equal(caps & (1n << bit), 0n);
for (const bit of [0n, 3n, 6n, 7n, 31n]) assert.notEqual(caps & (1n << bit), 0n);
assert.equal(value('NoNewPrivs'), '1'); assert.equal(value('Seccomp'), '2');
assert.equal(process.getuid(), 0); assert.equal(process.version, 'v22.23.4');
assert.equal(process.report.getReport().header.glibcVersionRuntime, '2.36');
assert.notEqual(fs.readlinkSync('/proc/self/ns/pid'), process.env.VEYRA_EXPECTED_HOST_PID_NS);
for (const name of ['/__veyra_host','/__veyra_input','/var/run/docker.sock','/dev/dri','/dev/kmsg']) assert.equal(fs.existsSync(name), false);
for (const key of Object.keys(process.env)) assert.equal(/TOKEN|PASSWORD|SECRET|SSH_AUTH_SOCK/.test(key), false);
let protectedHostFile = false;
try { const fd = fs.openSync('/etc/hosts', 'r+'); fs.closeSync(fd); }
catch (error) { assert.ok(['EROFS','EACCES','EPERM'].includes(error.code)); protectedHostFile = true; }
assert.equal(protectedHostFile, true);
const mounts = fs.readFileSync('/proc/self/mountinfo', 'utf8').split('\n');
for (const target of ['/proc/sys','/sys']) assert.ok(mounts.some(line => {const a=line.split(' '); return a[4]===target && a[5].split(',').includes('ro');}));
fs.mkdirSync('/tmp/veyra-oci-probe', {recursive:true, mode:0o700});
fs.writeFileSync('/tmp/veyra-oci-probe/ownership', 'owned-control\n', {mode:0o600});
fs.chownSync('/tmp/veyra-oci-probe/ownership', 1108, 1108);
assert.equal(fs.statSync('/tmp/veyra-oci-probe/ownership').uid, 1108);
console.log(JSON.stringify({control:'actual-oci-isolation',passed:true,node:process.version,glibc:process.report.getReport().header.glibcVersionRuntime,
capEff:value('CapEff'),capBnd:value('CapBnd'),noNewPrivileges:value('NoNewPrivs'),seccomp:value('Seccomp'),pidNamespace:fs.readlinkSync('/proc/self/ns/pid'),readonlyHostBind:true,protectedProcSys:true}));
'''

APT = r'''export VEYRA_IMAGE_BUILD_CONTEXT=1
apt-get update --error-on=any
node /usr/local/libexec/veyra/reproducible-linux.mjs verify-indexes /usr/local/share/veyra/linux-build.lock.json
apt-get install -y --no-install-recommends libcap2-bin
'''

CAPABILITIES = r'''groupadd --system --gid 1108 ingenium-restore
useradd --system --uid 1108 --gid 1108 --home-dir /nonexistent --shell /usr/sbin/nologin ingenium-restore
install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g ingenium-restore -m 0750 /usr/local/bin/node /usr/local/libexec/ingenium-restore-node
setcap cap_chown,cap_fowner=ep /usr/local/libexec/ingenium-restore-node
getcap /usr/local/libexec/ingenium-restore-node
runuser -u ingenium-restore -- /usr/local/bin/node -e 'const f=require("node:fs"),a=require("node:assert/strict");a.equal(process.getuid(),1108);a.equal(process.getgid(),1108);const s=f.readFileSync("/proc/self/status","utf8");a.match(s,/NoNewPrivs:\s+1/);a.match(s,/CapEff:\s+0+\n/);console.log(JSON.stringify({control:"actual-uid-gid-nnp",passed:true,uid:process.getuid(),gid:process.getgid()}));'
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--lease', type=Path, required=True)
    parser.add_argument('--continue-verified-context', action='store_true')
    args = parser.parse_args()
    o = load('veyra-linux-build')
    source, extension, report = o.inspect(args.revision, o.PHASE / 'windows-source/integrations/browser-extension')
    admission = load('veyra-linux-probe-admission').admit(o, report, args.lease.absolute())
    continuing = args.continue_verified_context
    if not continuing:
        need(not o.WORK.exists() and not o.TOOLS.exists(), 'Prior current preparation/tools require reconciliation; never overwrite')
    need(o.WORK.parent.resolve() == o.WORK.parent and o.TOOLS.parent.resolve() == o.TOOLS.parent,
         'Original canonical output parents required')
    os.umask(0o077)
    if not continuing:
        o.WORK.mkdir(mode=0o700)
    lock = (o.WORK / 'executor.lock').open('r+b' if continuing else 'xb')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    owner = {'owner': o.OWNER, 'executor': o.EXECUTOR, 'root': str(o.ROOT),
        'revision': report['source']['revision'], 'sourceSha256': report['source']['sourceSha256'],
        'regeneration': 'Exact pinned source/tools/locks and this literal closed control; no application compilation'}
    if continuing:
        actual_owner = json.loads((o.WORK / 'owner.json').read_text())
        need(all(actual_owner.get(key) == owner[key] for key in ['owner', 'executor', 'revision', 'sourceSha256']),
             'Existing current owner/source changed; never adopt it')
        receipt = json.loads((o.WORK / 'result.json').read_text())
        need(receipt.get('state') == 'closed-probe-failed-preserve-original-observation' and
             receipt.get('sourceContextProjection', {}).get('completed') is True and
             not any(row.get('ociRuns') for row in receipt.get('streamedProducerStages', [])),
             'Continuation only reconciles known pre-image bootstrap failure, not an uncertain existing runtime')
        receipt.setdefault('preservedOriginalFailures', []).append({
            'failure': receipt['originalFailure'], 'finishedAt': receipt['finishedAt'],
            'baseExtractionLog': {'path': str(o.WORK / 'base-budget-base-0-extract.log'),
                                 'sha256': o.sha(o.WORK / 'base-budget-base-0-extract.log')}})
        receipt['closedProbeAdmission'] = admission
        # gzip failed before extracting ANY data. Prove that exact fact before
        # original safe retirement; never adopt this failed filesystem.
        old = o.WORK / 'qualification-rootfs'
        need(old.resolve() == old and old.is_dir(), 'Expected exact owned failed bootstrap root')
        entries = list(old.rglob('*'))
        need(all(path.is_dir() and not path.is_symlink() and
                 path.relative_to(old).as_posix() in {'dev', 'proc'} for path in entries),
             'Failed bootstrap contains unexpected data; retain it for reconciliation')
        o.retire_targets(receipt, [old], 'failed-empty-bootstrap-original-refs-and-preservation')
        receipt['state'] = 'closed-probe-continuing-verified-context-new-empty-root'
    else:
        o.write_json(o.WORK / 'owner.json', owner)
        receipt = {**owner, 'state': 'closed-context-oci-qualification-preparing',
            'closedProbeAdmission': admission, 'preflight': report, 'stages': [], 'artifacts': {},
            'cleanupPasses': [], 'fullCompilerAdmitted': False, 'applicationDependenciesInstalled': False}
    o.write_json(o.WORK / 'result.json', receipt)
    producer = None
    try:
        if not continuing:
            o.tool_inputs(receipt)
            o.contexts(source, o.PHASE / 'windows-source/integrations/browser-extension', extension)
            context = load('veyra-linux-source-context').prepare(o, report, args.lease, receipt, source,
                                                              probe=True, authority=admission)
        else:
            context = receipt['sourceContextProjection']
            expected = {row['path']: row for row in source['files']}
            for name in context['includedPaths']:
                need(o.sha(o.WORK / 'docker-context' / name) == expected[name]['sha256'],
                     'Successful original filtered source changed; do not replay or rebase it')
        need('packages/veyra-contracts/src/index.ts' not in context['includedPaths'],
             'Original generated contract exclusion was not applied')
        # Exact same-source filtered view is retained for the actual pipeline;
        # the original frontend executables have reached their last consumer.
        if not continuing:
            o.retire_targets(receipt, [o.TOOLS / 'bin/buildctl', o.TOOLS / 'bin/buildkitd'],
                             'closed-context-frontend-tools-last-consumer')
        producer = load('veyra-linux-rootfs-producer').Producer(o, report, args.lease,
            receipt, 'budget', probe=True, authority=admission,
            attempt='bootstrap-fix' if continuing else 'initial')
        producer.load_base('library/node', 'base')
        sandbox = load('veyra-linux-oci-sandbox')
        producer.arguments['VEYRA_EXPECTED_HOST_PID_NS'] = os.readlink('/proc/self/ns/pid')
        environment = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                       'HOME': '/root', **producer.environment, **producer.arguments}

        def control(name, argv, extra=None):
            path = o.WORK / ('closed-control-' + name + '.log')
            with path.open('xb') as log:
                sandbox.run(producer, argv, {**environment, **(extra or {})}, log)
            producer.sequence += 1
            producer.record()
            return path

        isolation = control('isolation', ['/usr/local/bin/node', '-e', ISOLATION])
        expected = {row['path']: row for row in source['files']}
        for name, destination in [
            ('tools/veyra-release/reproducible-linux.mjs', '/usr/local/libexec/veyra/reproducible-linux.mjs'),
            ('tools/veyra-release/linux-build.lock.json', '/usr/local/share/veyra/linux-build.lock.json')]:
            original, target = o.WORK / 'docker-context' / name, producer.path(destination)
            need(o.sha(original) == expected[name]['sha256'], 'Canonical signed-OS control source differs')
            target.parent.mkdir(parents=True, exist_ok=True)
            with original.open('rb') as incoming, target.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            target.chmod(0o444)
        control('configure-signed-snapshot', ['/usr/local/bin/node',
            '/usr/local/libexec/veyra/reproducible-linux.mjs', 'configure',
            '/usr/local/share/veyra/linux-build.lock.json'], {'VEYRA_IMAGE_BUILD_CONTEXT': '1'})
        control('signed-capability-package', ['/bin/sh', '-ec', APT], {'DEBIAN_FRONTEND': 'noninteractive'})
        ownership = control('ownership-capability', ['/bin/sh', '-ec', CAPABILITIES])
        helper = producer.path('/usr/local/libexec/ingenium-restore-node')
        info = helper.stat()
        need(info.st_uid == 0 and info.st_gid == 1108 and info.st_mode & 0o7777 == 0o750 and
             o.sha(helper) == o.sha(producer.path('/usr/local/bin/node')), 'Actual original helper ownership/bytes changed')
        xattr = os.getxattr(helper, 'security.capability')
        need(bool(xattr) and 'cap_chown,cap_fowner=ep' in ownership.read_text(), 'Actual Linux file capabilities absent')
        # One focused roundtrip addresses the observed root/nanosecond/hardlink
        # transport risks; no separate harness or application workload replay.
        fixture = o.WORK / 'transport-control'
        fixture.mkdir(mode=0o750)
        file = fixture / 'control.bin'
        file.write_bytes(b'original-lossless-transport-control\n')
        os.link(file, fixture / 'hardlink.bin')
        (fixture / 'symlink').symlink_to('control.bin')
        nanos = 1793952000123456789
        for path in [file, fixture / 'hardlink.bin', fixture / 'symlink', fixture]:
            os.utime(path, ns=(nanos, nanos), follow_symlinks=False)
        handoffs = load('veyra-linux-streamed-handoff')
        archive = o.WORK / 'transport-control.tar.gz'
        proof = handoffs.pack(fixture, archive, 1024 * 1024)
        restored = handoffs.restore(o.WORK / 'transport-restored', archive, proof)
        qualification = {'passed': True, 'finishedAt': o.now(),
            'runtimeSha256': o.sha(o.TOOLS / 'bin/buildkit-runc'),
            'seccompSourceSha256': sandbox.PROFILE_SHA,
            'sourceContext': {'originalFrontend': True, 'includedFiles': len(context['includedPaths']),
                              'omittedFiles': len(context['omittedPaths']), 'generatedIndexExcluded': True},
            'isolationLog': {'path': str(isolation), 'sha256': o.sha(isolation)},
            'ownershipLog': {'path': str(ownership), 'sha256': o.sha(ownership)},
            'helper': {'sha256': o.sha(helper), 'uid': info.st_uid, 'gid': info.st_gid,
                       'mode': info.st_mode & 0o7777, 'securityCapabilityBase64': base64.b64encode(xattr).decode()},
            'actualTransportRoundtrip': restored,
            'fullCompilerOrRuntimeImageAccepted': False}
        receipt['ociIsolationQualification'] = qualification
        o.write_json(o.WORK / 'oci-isolation-qualification.json', qualification)
        producer.record()
        # Keep exact minimal configs/logs/proofs and actual filtered source/
        # pinned runc for their concrete forthcoming full-build consumer.
        o.retire_targets(receipt, [fixture, o.WORK / 'transport-restored', archive,
                                  producer.root], 'closed-successful-controls-last-consumer')
        receipt['state'] = 'closed-source-context-oci-controls-passed-not-full-build'
    except BaseException as error:
        receipt.update(state='closed-probe-failed-preserve-original-observation',
                       originalFailure={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        receipt['finishedAt'] = o.now()
        o.write_json(o.WORK / 'result.json', receipt)
        lock.close()
    print(json.dumps({'state': receipt['state'], 'qualification': receipt['ociIsolationQualification'],
                      'cleanupPasses': receipt['cleanupPasses']}), flush=True)


if __name__ == '__main__':
    main()
