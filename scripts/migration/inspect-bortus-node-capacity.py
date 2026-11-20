"""Read exact candidate cache/capacity metadata using the saved node credential."""
import importlib.util
import argparse
import json
from pathlib import Path
import subprocess
import shlex
import yaml

ROOT = Path(__file__).parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging-host', choices=('192.168.0.4', '192.168.0.5', '192.168.0.6'))
    parser.add_argument('--disk-host', choices=('192.168.0.4', '192.168.0.5', '192.168.0.6'))
    parser.add_argument('--journal-host', choices=('192.168.0.4', '192.168.0.5', '192.168.0.6'))
    args = parser.parse_args()
    credential = load('capacity_saved_credential', 'saved-node-credential.py')
    binding = json.loads(Path('/mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z/BORTUS-qualified-OCI-binding-20261114.json').read_text())
    password = credential.existing_password()
    rows = []
    try:
        if args.journal_host:
            program = """import pathlib,time,json,os
base=pathlib.Path('/var/log/journal'); rows=[]
for p in base.glob('*/system@*.journal'):
 s=p.lstat()
 if not p.is_symlink() and s.st_nlink==1 and s.st_mtime<time.time()-72*3600:
  rows.append({'path':str(p),'bytes':s.st_size,'allocated_bytes':s.st_blocks*512,'mtime_ns':s.st_mtime_ns})
print(json.dumps({'closed_name_candidates':rows}))"""
            command = ['sudo', '-S', '-k', '-p', '', 'python3', '-c', program]
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
                'james@' + args.journal_host, shlex.join(command)], input=(password + '\n').encode(),
                capture_output=True, timeout=30)
            if r.returncode or len(r.stdout) > 65536:
                raise RuntimeError('bounded_journal_metadata_query_failed')
            print(r.stdout.decode())
            return
        if args.disk_host:
            command = ['sudo', '-S', '-k', '-p', '', 'du', '-x', '-B1', '-d1',
                       '/var/lib', '/home', '/opt', '/var/cache', '/root', '/var/log']
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
                'james@' + args.disk_host, shlex.join(command)], input=(password + '\n').encode(),
                capture_output=True, timeout=60)
            if r.returncode or len(r.stdout) > 65536:
                raise RuntimeError('bounded_disk_usage_query_failed')
            print(json.dumps({'host': args.disk_host, 'allocated_paths': r.stdout.decode().splitlines()}))
            return
        if args.staging_host:
            command = ['sudo', '-S', '-k', '-p', '', 'find', '/home/james', '/root', '/var/tmp', '/tmp',
                       '/var/cache/apt/archives', '-xdev', '-maxdepth', '3', '-type', 'f',
                       '-size', '+100M', '-printf', '%p %s\n']
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
                'james@' + args.staging_host, shlex.join(command)], input=(password + '\n').encode(),
                capture_output=True, timeout=30)
            if r.returncode or len(r.stdout) > 65536:
                raise RuntimeError('bounded_staging_query_failed')
            scans = {}
            for query in ('images list', 'containers list'):
                cmd = "sudo -S -k -p '' /opt/containerd-k8s/bin/ctr --address /run/containerd-k8s/containerd.sock --namespace k8s.io " + query
                result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
                    'james@' + args.staging_host, cmd], input=(password + '\n').encode(),
                    capture_output=True, timeout=30)
                if result.returncode or len(result.stdout) > 4 * 1024**2:
                    raise RuntimeError('bounded_old_image_query_failed')
                scans[query] = [line.split() for line in result.stdout.decode().splitlines()[1:] if line.split()]
            old = [row for row in scans['images list'] if 'bortus' in row[0]
                   or row[2] == 'sha256:bfc78b697373727aebccf50c70ef1944c76691cc435da0ad3bcc4e44670ff211']
            aliases = {row[0] for row in old}
            consumers = [row[0] for row in scans['containers list'] if row[1] in aliases or
                         'bfc78b697373727aebccf50c70ef1944c76691cc435da0ad3bcc4e44670ff211' in row[1]]
            print(json.dumps({'host': args.staging_host, 'large_staging_paths': r.stdout.decode().splitlines(),
                              'old_image_rows': old, 'old_image_container_consumers': consumers}))
            return
        for host in credential.NATIVE_NODES:
            ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o',
                   'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@' + host]
            ctr = "sudo -S -k -p '' /opt/containerd-k8s/bin/ctr --address /run/containerd-k8s/containerd.sock --namespace k8s.io "
            def read(suffix):
                r = subprocess.run(ssh + [ctr + suffix], input=(password + '\n').encode(),
                                   capture_output=True, timeout=30)
                if r.returncode or len(r.stdout) > 4 * 1024**2:
                    raise RuntimeError('bounded_node_capacity_query_failed')
                return r.stdout.decode()
            contents = set(read('content list --quiet').splitlines())
            snapshots = {row.split()[0] for row in read('snapshots list').splitlines()[1:] if row.split()}
            config_result = subprocess.run(ssh + ["sudo -S -k -p '' cat /var/lib/kubelet/config.yaml"],
                input=(password + '\n').encode(), capture_output=True, timeout=30)
            if config_result.returncode:
                raise RuntimeError('node_capacity_configuration_unavailable')
            config = yaml.safe_load(config_result.stdout)
            rows.append({'host': host,
                         'candidate_layer_blobs_cached': [d in contents for d in binding['layer_blob_digests']],
                         'candidate_base_snapshot_cached': binding['ordered_diff_ids'][0] in snapshots,
                         'evictionHard': config.get('evictionHard'),
                         'imageGCHighThresholdPercent': config.get('imageGCHighThresholdPercent'),
                         'imageGCLowThresholdPercent': config.get('imageGCLowThresholdPercent')})
    finally:
        password = None
    print(json.dumps({'scope': 'Read-only exact candidate cached layers', 'nodes': rows}))


if __name__ == '__main__':
    main()
