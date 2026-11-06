"""Verify actual Ready native image IDs and preserve addon/configmap identities."""
import copy
import json
import subprocess
import sys


def read(args):
    p = subprocess.run(['kubectl'] + args, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise ValueError('Read-only runtime verification unavailable')
    return json.loads(p.stdout)


def configs():
    result = {}
    for name in ['kubeadm-config', 'kubelet-config', 'kube-proxy', 'coredns']:
        o = read(['-n', 'kube-system', 'get', 'configmap', name, '-o', 'json'])
        result[name] = {'uid': o['metadata']['uid'], 'data': o.get('data', {})}
    return result


def main():
    import yaml
    data = json.load(sys.stdin)
    if sys.argv[1] == 'capture':
        print(json.dumps(configs())); return
    assert sys.argv[1] == 'verify'
    expected = copy.deepcopy(data['before'])
    actual = configs()
    # kubeadm is allowed to record only its new Kubernetes version. Compare
    # parsed ClusterConfiguration, preserving all other config data and UIDs.
    a = yaml.safe_load(actual['kubeadm-config']['data'].pop('ClusterConfiguration'))
    e = yaml.safe_load(expected['kubeadm-config']['data'].pop('ClusterConfiguration'))
    assert e['kubernetesVersion'] == 'v1.37.1' and a['kubernetesVersion'] == 'v1.37.2'
    e['kubernetesVersion'] = 'v1.37.2'
    assert a == e and actual == expected, 'Unreviewed cluster/addon configuration mutation'
    version = read(['version', '-o', 'json'])['serverVersion']
    assert version['gitVersion'] == 'v1.37.2' and version['goVersion'] == 'go1.26.10'
    pods = [p for p in read(['-n', 'kube-system', 'get', 'pods', '-o', 'json'])['items']
            if not p['metadata'].get('deletionTimestamp')]
    for name, image in data['plan']['images'].items():
        selected = [p for p in pods if p['metadata'].get('labels', {}).get('component') == name
                    or (name == 'kube-proxy' and p['metadata'].get('labels', {}).get('k8s-app') == name)]
        assert len(selected) == (3 if name == 'kube-proxy' else 1), 'Missing original native component pods'
        for pod in selected:
            c = next(c for c in pod['spec']['containers'] if c['name'] == name)
            s = next(c for c in pod['status']['containerStatuses'] if c['name'] == name)
            assert c['image'] == image['reference'] and s['ready'] is True
            assert any(s['imageID'].endswith('@' + image[k]) or s['imageID'] == image[k]
                       for k in ['rootDigest', 'amd64Digest', 'configDigest']), 'Running native digest differs from scan authority'
    print(json.dumps({'passed': True, 'server': 'v1.37.2', 'goVersion': 'go1.26.10', 'nativeReadyImages': 6}))


if __name__ == '__main__':
    main()
