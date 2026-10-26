#!/usr/bin/env python3
"""Apply the maintained CoreDNS release, preserving its kubeadm-owned identity."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'docker.io/library/coredns-security-20261023@sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9'
NEW = 'docker.io/coredns/coredns:1.15.0@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26'
CHILD = 'sha256:3429e3bbffb1e839470c4a3541d4d78aca84a1394c75a539d0200c58c63196ac'
ROOT = BASE / 'local-image-build-offload-20261025'
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
def name_end(raw,at):
 for _ in range(128):
  need(at<len(raw));n=raw[at]
  if n&192==192:need(at+1<len(raw));return at+2
  need(n<=63 and at+1+n<=len(raw));at+=1+n
  if n==0:return at
 raise ValueError('invalid_dns_name')
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
   need(answers<=256);at=name_end(raw,12)+4;ips=[]
   for _ in range(answers):
    at=name_end(raw,at);need(at+10<=len(raw));kind,cls,ttl,size=struct.unpack('!HHIH',raw[at:at+10]);at+=10;need(at+size<=len(raw))
    if kind==1 and cls==1:need(size==4);ips.append(socket.inet_ntoa(raw[at:at+4]))
    at+=size
   need(bool(ips))
   if name in request['expectedServiceA']:need(set(ips)=={request['expectedServiceA'][name]})
   checks.append({'address':address,'name':name,'tcp':tcp,'answers':answers,'IPv4':ips})
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


def get(kind, name, namespace='kube-system'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind, name, '-o', 'json']))


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
        need(cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if image == NEW else OLD.rsplit('@', 1)[-1]], 'actual_dns_manifest')
    ips = [pod['status']['podIP'] for pod in pods]
    request = {'addresses': [service['spec']['clusterIP']] + ips, 'pods': ips,
               'expectedServiceA': {'kubernetes.default.svc.cluster.local': get('service', 'kubernetes', 'default')['spec']['clusterIP'],
                                    'wordpress-db.wordpress.svc.cluster.local': get('service', 'wordpress-db', 'wordpress')['spec']['clusterIP']}}
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
    need(ROOT.is_mount() and a.output_dir == ROOT / 'upstream-coredns-20261026', 'private_existing_output_scope')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = a.output_dir / ('coredns-' + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    report = {'passed': False, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'oldImage': OLD, 'newImage': NEW,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'dataVolumesChanged': False}
    try:
        need(a.scan_receipt.resolve() == a.scan_receipt and not a.scan_receipt.stat().st_mode & 0o077
             and hashlib.sha256(a.scan_receipt.read_bytes()).hexdigest() == a.scan_sha256, 'exact_private_scan_receipt')
        need(a.scan_receipt == ROOT / 'security-review-20261026/apps-coredns-current-r3-0/receipt.json', 'finite_vendor_scan_scope')
        scan = json.loads(a.scan_receipt.read_bytes())
        need(scan['scanComplete'] and scan['state'] == 'completed' and scan['image'] == NEW
             and scan['inputHashesReverifiedAfterScan'] and scan['suppressionUsed'] is False and scan['scannerExitCode'] == 0
             and hashlib.sha256((a.scan_receipt.parent / 'results.json').read_bytes()).hexdigest() == scan['resultsSHA256'], 'complete_unsuppressed_exact_upstream_scan')
        vendor = json.loads((a.output_dir / 'vendor-image-inspection.json').read_bytes())['image']
        need(vendor['reference'] == NEW and vendor['amd64Manifest'] == CHILD, 'exact_upstream_platform_metadata')
        updated = datetime.datetime.fromisoformat(scan['databaseUpdatedAt'].replace('Z', '+00:00'))
        need(0 <= (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() <= 86400, 'fresh_vendor_scan')
        version = json.loads((a.output_dir / 'version-probe-retirement.json').read_bytes())
        need(version['passed'] and version['probeAndPolicyRetiredByUID'] and version['image'] == NEW
             and version['version'] == '1.15.0' and version['goVersion'] == '1.27.3'
             and re.fullmatch('[a-f0-9]{40}', version['releaseCommit'])
             and version['releaseCommit'].startswith('a6fde3fe339c')
             and version['imageID'].rsplit('@', 1)[-1] in [NEW.rsplit('@', 1)[-1], CHILD], 'actual_released_binary_identity')
        # Preserve raw scanner rows. The upstream binary identifies itself as
        # 1.15.0 at the release tag, while its Go module has a v0.0.0 pseudo-
        # version. Accept only that exact module/commit and older fixed ranges;
        # any other available Critical/High fix still refuses the rollout.
        results = json.loads((a.scan_receipt.parent / 'results.json').read_bytes())
        findings = [v for x in results for v in x.get('Vulnerabilities') or []
                    if v['Severity'] in ['CRITICAL', 'HIGH'] and v.get('FixedVersion')]
        attributed = []
        for finding in findings:
            need(finding['PkgName'] == 'github.com/coredns/coredns'
                 and re.fullmatch('v0\\.0\\.0-[0-9]{14}-' + version['releaseCommit'][:12], finding['InstalledVersion'])
                 and re.fullmatch('[0-9]+\\.[0-9]+\\.[0-9]+', finding['FixedVersion'])
                 and tuple(map(int, finding['FixedVersion'].split('.'))) <= (1, 15, 0), 'no_unresolved_available_critical_high_fix')
            attributed.append({'id': finding['VulnerabilityID'], 'rawInstalledVersion': finding['InstalledVersion'],
                               'fixedVersion': finding['FixedVersion'], 'actualReleasedVersion': version['version']})
        need(len(attributed) == scan['fixableCriticalHigh'], 'complete_raw_finding_attribution')
        report['versionAttribution'] = {'inference': 'Exact official binary/tag/commit is newer than these fixed ranges; raw pseudo-version findings remain retained.',
                                      'rawRows': attributed, 'upstreamVersionProofSHA256': hashlib.sha256((a.output_dir / 'version-probe-retirement.json').read_bytes()).hexdigest()}
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
                      rawSeverityCounts=scan['severityCounts'], rawFixableCriticalHigh=scan['fixableCriticalHigh'],
                      unresolvedAvailableCriticalHighAfterVersionAttribution=0)
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
        if report.get('imagePatched'):
            # Roll back only our exact image-only change; never overwrite a
            # concurrent operator's specification or alter Corefile/Service.
            try:
                live = get('deployment', 'coredns')
                expected = copy.deepcopy(before['spec'])
                expected['template']['spec']['containers'][0]['image'] = NEW
                need(live['metadata']['uid'] == UID and live['spec'] == expected, 'unchanged_owned_rollback_target')
                rollback = [{'op': 'test', 'path': '/metadata/uid', 'value': UID},
                            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': live['metadata']['resourceVersion']},
                            {'op': 'test', 'path': '/spec/template/spec/containers/0/image', 'value': NEW},
                            {'op': 'replace', 'path': '/spec/template/spec/containers/0/image', 'value': OLD}]
                call(['kubectl', '-n', 'kube-system', 'patch', 'deployment', 'coredns', '--type=json', '--patch', json.dumps(rollback)])
                call(['kubectl', '-n', 'kube-system', 'rollout', 'status', 'deployment/coredns', '--timeout=240s'], timeout=260)
                restored, restored_cm, restored_svc, proof = observe(OLD)
                need(restored['spec'] == before['spec'] and restored_cm['data'] == cm['data'] and restored_svc['spec'] == service['spec'], 'verified_original_dns_restored')
                report.update(rolledBack=True, rollbackProof=proof)
            except Exception as rollback_error:
                report.update(rolledBack=False, rollbackFailureType=type(rollback_error).__name__)
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = folder / 'receipt.json'
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'alreadyPatched': report.get('alreadyPatched', False), 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
