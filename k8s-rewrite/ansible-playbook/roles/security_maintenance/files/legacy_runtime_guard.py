"""Read-only task inventory of the retired stock runtime, never the K8s socket."""
import json
import subprocess


def read(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SystemExit('Cannot verify stock runtime ownership; refuse retirement')
    return result.stdout.strip()


def main():
    legacy_pid = read(['systemctl', 'show', 'containerd.service', '-p', 'MainPID', '--value'])
    independent_pid = read(['systemctl', 'show', 'containerd-k8s.service', '-p', 'MainPID', '--value'])
    if independent_pid == '0' or legacy_pid == independent_pid:
        raise SystemExit('Independent runtime identity is not distinct; refuse retirement')
    if legacy_pid == '0':
        print(json.dumps({'stock_runtime_running': False, 'namespace_tasks': {}}))
        return 0
    address = '/run/containerd/containerd.sock'
    namespaces = read(['ctr', '--address', address, 'namespaces', 'list', '-q']).splitlines()
    tasks = {ns: read(['ctr', '--address', address, '--namespace', ns, 'tasks', 'list', '-q']).splitlines() for ns in namespaces}
    print(json.dumps({'stock_runtime_running': True, 'namespace_tasks': tasks}, sort_keys=True))
    return int(any(tasks.values()))


if __name__ == '__main__':
    raise SystemExit(main())
