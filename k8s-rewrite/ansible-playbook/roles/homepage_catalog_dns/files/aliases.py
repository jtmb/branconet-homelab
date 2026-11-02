"""Preserve Pi-hole records and add the two existing Homepage ingress aliases."""
import argparse
import json
import re
import shlex
import subprocess

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
       '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519',
       '-p', '2002', 'james@192.168.0.4']
ALIASES = ['jackett.branconet.lan,branconet.lan', 'whoami.branconet.lan,branconet.lan']


def call(args):
    result = subprocess.run(SSH + [shlex.join(['kubectl', *args])],
                            capture_output=True, text=True, timeout=30)
    if result.returncode or len(result.stdout) > 1048576:
        raise RuntimeError('bounded Kubernetes operation failed')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    pods = json.loads(call(['get', 'pods', '-n', 'pihole', '-l', 'app=pihole', '-o', 'json']))['items']
    pods = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
    assert len(pods) == 1
    pod = pods[0]
    assert any(c['name'] == 'pihole' and c['ready'] for c in pod['status']['containerStatuses'])
    container = next(c for c in pod['spec']['containers'] if c['name'] == 'pihole')
    assert not any(e['name'] == 'FTLCONF_dns_cnameRecords' for e in container.get('env', []))
    base = ['exec', '-n', 'pihole', pod['metadata']['name'], '-c', 'pihole', '--']

    def aliases():
        text = call(base + ['pihole-FTL', '--config', 'dns.cnameRecords'])
        assert text.startswith('[ ') and text.endswith(' ]')
        values = text[2:-2].split(', ') if text[2:-2] else []
        assert len(values) <= 1000 and len(values) == len(set(values))
        assert all(re.fullmatch(r'[a-zA-Z0-9_.-]+,[a-zA-Z0-9_.-]+(?:,[0-9]+)?', v) for v in values)
        return values

    before = aliases()
    missing = [v for v in ALIASES if v not in before]
    for wanted in missing:
        assert not any(v.split(',')[0] == wanted.split(',')[0] for v in before), 'conflicting existing alias'
    after = before + missing
    if args.apply and missing:
        assert aliases() == before, 'configuration changed before write'
        call(base + ['pihole-FTL', '--config', 'dns.cnameRecords', json.dumps(after)])
        assert aliases() == after, 'readback differs'
        call(base + ['pihole', 'reloaddns'])
    observed = json.loads(call(['get', 'pod', '-n', 'pihole', pod['metadata']['name'], '-o', 'json']))
    assert observed['metadata']['uid'] == pod['metadata']['uid']
    assert observed['status']['containerStatuses'] == pod['status']['containerStatuses']
    print(json.dumps({'changed': bool(args.apply and missing), 'missing': missing,
                      'previousRecordsPreserved': len(before), 'aliases': ALIASES,
                      'podUID': pod['metadata']['uid'], 'podRestarted': False}))


if __name__ == '__main__':
    main()
