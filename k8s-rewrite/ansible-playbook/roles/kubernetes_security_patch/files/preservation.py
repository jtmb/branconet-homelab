"""Host preservation projection and native image checks; never prints key bytes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess
import sys

COMPONENTS = ['kube-apiserver', 'kube-controller-manager', 'kube-scheduler']
CRI = ['crictl', '--runtime-endpoint', 'unix:///run/containerd-k8s/containerd.sock']
CRI[0] = '/opt/containerd-k8s/bin/crictl'


def run(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise ValueError('Preservation command failed: ' + argv[0])
    return p.stdout.strip()


def snapshot():
    import yaml  # Existing capability required; this role installs no helpers.
    protected = [Path('/etc/containerd-k8s/config.toml'), Path('/var/lib/kubelet/config.yaml'),
                 Path('/var/lib/kubelet/kubeadm-flags.env'), Path('/etc/kubernetes/kubelet.conf')]
    unit_properties = {}
    for unit in ['kubelet', 'containerd-k8s']:
        props = {key: run(['systemctl', 'show', unit, '--property=' + key, '--value'])
                 for key in ['FragmentPath', 'DropInPaths', 'UnitFileState']}
        assert props['FragmentPath'].startswith('/')
        protected += [Path(props['FragmentPath'])] + [Path(p) for p in shlex.split(props['DropInPaths'])]
        unit_properties[unit] = props
    if platform.node() == 'masternode':
        protected += [Path('/etc/kubernetes') / n for n in ['admin.conf', 'controller-manager.conf', 'scheduler.conf', 'manifests/etcd.yaml']]
        protected += sorted(p for p in Path('/etc/kubernetes/pki').rglob('*') if p.is_file())
    hashes = {}
    for p in protected:
        assert p.is_file(), 'Protected source missing'
        s = p.stat()
        attrs = {n: os.getxattr(p, n).hex() for n in sorted(os.listxattr(p))}
        hashes[str(p)] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'uid': s.st_uid, 'gid': s.st_gid,
                          'mode': stat.S_IMODE(s.st_mode), 'mtimeNs': s.st_mtime_ns,
                          'xattrsSHA256': hashlib.sha256(json.dumps(attrs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
    pods = {}
    if platform.node() == 'masternode':
        for name in COMPONENTS:
            pods[name] = yaml.safe_load((Path('/etc/kubernetes/manifests') / (name + '.yaml')).read_text())
            assert pods[name]['kind'] == 'Pod' and pods[name]['metadata']['name'] == name
    return {'host': platform.node(), 'files': hashes, 'staticPods': pods, 'unitProperties': unit_properties}


def main():
    data = json.load(sys.stdin); plan = data['plan']
    assert platform.node() in plan['nodeUIDs']
    assert run(['uname', '-r']) == '5.15.0-202-generic', 'Finish kernel recovery before this separate patch'
    # This pinned crictl version exposes no output flag for `version`.
    # Require its complete actual response rather than relying on a JSON option
    # accepted by other subcommands.
    version_rows = [line.split(':', 1) for line in run(CRI + ['version']).splitlines()]
    assert len(version_rows) == 4 and len({r[0] for r in version_rows}) == 4
    assert {k: v.strip() for k, v in version_rows} == {
        'Version': '0.1.0', 'RuntimeName': 'containerd',
        'RuntimeVersion': 'v2.4.2', 'RuntimeApiVersion': 'v1'}
    for name, img in plan['images'].items():
        state = json.loads(run(CRI + ['inspecti', 'registry.k8s.io/' + name + ':v1.37.2']))['status']
        assert state['id'] == img['configDigest'], 'Native cached image config differs'
        assert 'registry.k8s.io/' + name + ':v1.37.2' in state.get('repoTags', []), 'Required kubeadm tag not staged'
        assert any('registry.k8s.io/' + name + '@' + img[k] in state.get('repoDigests', [])
                   for k in ['rootDigest', 'amd64Digest']), 'Native cached digest differs'
    current = snapshot()
    if sys.argv[1] == 'capture':
        for name, pod in current['staticPods'].items():
            containers = pod['spec']['containers']
            assert len(containers) == 1 and containers[0]['name'] == name
            assert re.fullmatch(r'registry\.k8s\.io/' + name + r':v1\.37\.1(?:@sha256:[a-f0-9]{64})?', containers[0]['image']), 'Only original1.37.1 static source accepted'
        print(json.dumps(current))
    elif sys.argv[1] == 'verify':
        expected = copy.deepcopy(data['before'])
        for name, pod in expected['staticPods'].items():
            pod['spec']['containers'][0]['image'] = plan['images'][name]['reference']
        assert current == expected, 'Protected config, certificate, etcd, static arguments/mounts/principals changed'
        print(json.dumps({'passed': True, 'host': platform.node(), 'protectedFiles': len(current['files']), 'onlyStaticImageChange': True}))
    else:
        raise ValueError('Unknown mode')


if __name__ == '__main__':
    main()
