#!/usr/bin/env python3
"""Apply the reviewed CoreDNS security build, preserving Corefile and Service."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'registry.k8s.io/coredns/coredns:v1.14.6'
NEW = 'docker.io/library/coredns-security-20261023@sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9'
CHILD = NEW.rsplit('@', 1)[-1]
UID = 'adee85f5-3155-4be2-bc2f-8a602b15c17d'

DNS_PROBE = r'''import json,os,socket,struct,sys,urllib.request
request=json.load(sys.stdin); checks=[]
def need(ok):
 if not ok: raise ValueError('dns_or_health_check_failed')
def receive(s,n):
 out=b''
 while len(out)<n:
  b=s.recv(n-len(out));need(bool(b));out+=b
 return out
for address in request['addresses']:
 for name in ['kubernetes.default.svc.cluster.local','wordpress-db.wordpress.svc.cluster.local','example.com']:
  question=b''.join(bytes([len(x)])+x.encode() for x in name.split('.'))+b'\0'+struct.pack('!HH',1,1)
  ident=int.from_bytes(os.urandom(2),'big'); packet=struct.pack('!HHHHHH',ident,0x0100,1,0,0,0)+question
  for tcp in [False,True]:
   with socket.socket(socket.AF_INET,socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as s:
    s.settimeout(5);s.connect((address,53))
    if tcp:s.sendall(struct.pack('!H',len(packet))+packet);raw=receive(s,struct.unpack('!H',receive(s,2))[0])
    else:s.send(packet);raw=s.recv(65535)
   need(len(raw)>=12);got,flags,qd,answers,_,_=struct.unpack('!HHHHHH',raw[:12]);need(got==ident and flags&0x8000 and flags&15==0 and qd==1 and answers>0)
   checks.append({'address':address,'name':name,'tcp':tcp,'answers':answers})
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for address in request['pods']:
 for port,path in [(8080,'/health'),(8181,'/ready')]:
  with opener.open('http://'+address+':'+str(port)+path,timeout=5) as r:need(r.status==200 and len(r.read(4097))<=4096)
print(json.dumps({'passed':True,'dnsChecks':checks,'podHealthChecks':2*len(request['pods'])}))
'''


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, body=None, timeout=40):
    p = subprocess.run(SSH + [shlex.join(args)], input=body, capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024 ** 2, 'bounded_cluster_operation')
    return p.stdout


def get(kind, name):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', 'kube-system', 'get', kind, name, '-o', 'json']))


def observe(image):
    d = get('deployment', 'coredns')
    cm = get('configmap', 'coredns')
    service = get('service', 'kube-dns')
    need(d['metadata']['uid'] == UID and not d['metadata'].get('deletionTimestamp')
         and not d['metadata'].get('labels', {}).get('helm.toolkit.fluxcd.io/name'), 'original_kubeadm_owner')
    need(d['spec']['replicas'] == 2 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 2 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'two_ready_dns_replicas')
    need(len(d['spec']['template']['spec']['containers']) == 1 and d['spec']['template']['spec']['containers'][0]['image'] == image, 'expected_dns_image')
    for attempt in range(16):
        pods = json.loads(call(['kubectl', '-n', 'kube-system', 'get', 'pods', '-l', 'k8s-app=kube-dns', '-o', 'json']))['items']
        if len(pods) == 2:
            break
        need(all(p.get('metadata', {}).get('deletionTimestamp') or p['spec']['containers'][0]['image'] == image for p in pods), 'only_expected_or_terminating_dns_pods')
        if attempt < 15:
            time.sleep(2)
    need(len(pods) == 2, 'two_live_dns_pods')
    for pod in pods:
        cs = pod['status']['containerStatuses'][0]
        need(not pod['metadata'].get('deletionTimestamp') and cs['ready'] and pod['spec']['containers'][0]['image'] == image, 'ready_exact_dns_pod')
        if image == NEW:
            need(cs['imageID'].rsplit('@', 1)[-1] in [NEW.rsplit('@', 1)[-1], CHILD], 'actual_dns_manifest')
    ips = [pod['status']['podIP'] for pod in pods]
    request = {'addresses': [service['spec']['clusterIP']] + ips, 'pods': ips}
    probes = json.loads(call(['python3', '-B', '-c', DNS_PROBE], json.dumps(request).encode(), timeout=125))
    need(probes['passed'] and len(probes['dnsChecks']) == 18, 'actual_udp_tcp_cluster_and_forwarded_dns')
    return d, cm, service, {'pods': [{'uid': p['metadata']['uid'], 'name': p['metadata']['name'], 'imageID': p['status']['containerStatuses'][0]['imageID']} for p in pods], 'probes': probes}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--scan-receipt', required=True, type=Path)
    p.add_argument('--scan-sha256', required=True)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    need(a.apply and os.name == 'posix', 'explicit_native_patch')
    os.umask(0o077)
    need(a.output_dir.is_absolute() and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_output_scope')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = a.output_dir / ('coredns-' + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    report = {'passed': False, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'oldImage': OLD, 'newImage': NEW,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'dataVolumesChanged': False}
    try:
        need(a.scan_receipt.resolve() == a.scan_receipt and not a.scan_receipt.stat().st_mode & 0o077
             and hashlib.sha256(a.scan_receipt.read_bytes()).hexdigest() == a.scan_sha256, 'exact_private_scan_receipt')
        scan = json.loads(a.scan_receipt.read_bytes())
        need(scan['state'] == 'scan_complete' and scan['service'] == 'coredns' and scan['sourceKind'] == 'local-operator'
             and scan['localProvenance']['rootDescriptor'] == CHILD and scan['scannerExitCode'] == 0
             and hashlib.sha256((a.scan_receipt.parent / 'results.json').read_bytes()).hexdigest() == scan['resultSHA256'], 'complete_unsuppressed_exact_scan')
        archive = Path(scan['originalArchive'])
        need(archive.resolve() == archive and not archive.stat().st_mode & 0o077, 'retained_private_original_artifact')
        digest = hashlib.sha256()
        with archive.open('rb') as f:
            for block in iter(lambda: f.read(1024 ** 2), b''):
                digest.update(block)
        need(digest.hexdigest() == scan['originalArchiveSHA256'] == scan['localProvenance']['archiveSHA256'], 'same_complete_scanned_archive')
        updated = datetime.datetime.fromisoformat(scan['inputs']['vulnerabilityDB']['UpdatedAt'].replace('Z', '+00:00'))
        need(0 <= (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() <= 86400
             and scan['fixedCriticalHighRows'] == 0, 'fresh_scan_without_available_critical_high_fixes')
        report['scanReceiptSHA256'] = a.scan_sha256
        current = get('deployment', 'coredns')['spec']['template']['spec']['containers'][0]['image']
        need(current in [OLD, NEW], 'original_or_already_patched_image')
        before, cm, service, proof = observe(current)
        (folder / 'original-deployment.json').write_text(json.dumps(before, sort_keys=True, indent=2))
        (folder / 'original-configmap.json').write_text(json.dumps(cm, sort_keys=True, indent=2))
        report['before'] = proof
        patch = [{'op': 'test', 'path': '/metadata/uid', 'value': UID},
                 {'op': 'test', 'path': '/metadata/resourceVersion', 'value': before['metadata']['resourceVersion']},
                 {'op': 'test', 'path': '/spec/template/spec/containers/0/name', 'value': 'coredns'},
                 {'op': 'test', 'path': '/spec/template/spec/containers/0/image', 'value': current},
                 {'op': 'replace', 'path': '/spec/template/spec/containers/0/image', 'value': NEW}]
        if current != NEW:
            call(['kubectl', '-n', 'kube-system', 'patch', 'deployment', 'coredns', '--type=json', '--patch', json.dumps(patch)])
            report['imagePatched'] = True
            call(['kubectl', '-n', 'kube-system', 'rollout', 'status', 'deployment/coredns', '--timeout=240s'], timeout=260)
        else:
            report.update(imagePatched=False, alreadyPatched=True)
        after, cm_after, service_after, proof_after = observe(NEW)
        expected = copy.deepcopy(before['spec'])
        expected['template']['spec']['containers'][0]['image'] = NEW
        need(after['spec'] == expected, 'only_image_changed')
        need(cm_after['metadata']['uid'] == cm['metadata']['uid'] and cm_after['data'] == cm['data']
             and service_after['metadata']['uid'] == service['metadata']['uid'] and service_after['spec'] == service['spec'], 'same_corefile_and_dns_service')
        report.update(passed=True, after=proof_after, corefileSHA256=hashlib.sha256(cm['data']['Corefile'].encode()).hexdigest(),
                      deploymentUID=UID, configmapUID=cm['metadata']['uid'], serviceUID=service['metadata']['uid'],
                      residualSeverityCounts=scan['severityCounts'], residualFixableCriticalHigh=scan['fixedCriticalHighRows'])
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = folder / 'receipt.json'
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'alreadyPatched': report.get('alreadyPatched', False), 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
