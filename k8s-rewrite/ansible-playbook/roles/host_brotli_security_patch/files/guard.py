#!/usr/bin/env python3
"""Finite Ubuntu Jammy Brotli preflight and continuity snapshot; no mutations."""
import datetime,json,os,re,subprocess,sys
FIXED='1.0.9-2ubuntu0.1'
def run(argv):return subprocess.check_output(argv,stderr=subprocess.DEVNULL,timeout=40).decode()
def snapshot():
 assert os.uname().nodename.split('.')[0]=='workernode1'
 version=run(['dpkg-query','-W','-f=${Version}','libbrotli1']).strip()
 assert version in ['1.0.9-2build6',FIXED]
 packages=dict(line.split('\t',1)for line in run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\n']).splitlines())
 services={}
 for name in ['kubelet','containerd-k8s','ssh']:
  services[name]=dict(line.split('=',1)for line in run(['systemctl','show',name,'--property=MainPID,ActiveState,ActiveEnterTimestampMonotonic,NRestarts']).splitlines())
  assert services[name]['ActiveState']=='active'
 return {'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'version':version,'packages':packages,'kernel':os.uname().release,'bootID':open('/proc/sys/kernel/random/boot_id').read().strip(),'services':services,'rebootRequired':os.path.exists('/var/run/reboot-required')}
def main():
 mode=sys.argv[1]
 if mode in ['preflight','snapshot']:
  value=snapshot()
  if mode=='preflight':
   assert run(['dpkg','--print-architecture']).strip()=='amd64'
   release=dict(line.split('=',1)for line in open('/etc/os-release').read().splitlines()if '='in line)
   assert release['VERSION_CODENAME']=='jammy'
   policy=run(['apt-cache','policy','libbrotli1']);assert 'http://security.ubuntu.com/ubuntu jammy-security/main amd64 Packages'in policy and FIXED in policy
   simulation=run(['apt-get','--simulate','-o','Debug::NoLocking=true','install','libbrotli1='+FIXED]);inst=[x for x in simulation.splitlines()if x.startswith('Inst ')];remove=[x for x in simulation.splitlines()if x.startswith('Remv ')]
   assert not remove and (not inst if value['version']==FIXED else len(inst)==1 and inst[0].startswith('Inst libbrotli1 ') and FIXED in inst[0])
   value.update(simulatedInstallLines=inst,onlyOneSecurityPackage=True)
  print(json.dumps(value));return
 if mode=='verify':
  request=json.load(sys.stdin);before=request['before'];after=request['after'];assert after['version']==FIXED
  expected=dict(before['packages']);expected['libbrotli1:amd64']=FIXED
  assert after['packages']==expected
  assert all(before[k]==after[k]for k in ['kernel','bootID','services','rebootRequired'])
  print(json.dumps({'passed':True,'fixedVersion':FIXED,'CVE':'CVE-2026-111497','onlyLibbrotliChanged':True,'noRuntimeRestartOrReboot':True}));return
 raise ValueError('unsupported_mode')
if __name__=='__main__':main()
