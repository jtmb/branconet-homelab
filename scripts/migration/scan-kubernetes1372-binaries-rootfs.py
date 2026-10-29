#!/usr/bin/env python3
"""Finite correction: official compiled-binary rootfs analyzer plus executable source mode."""
from pathlib import Path
import ast,hashlib,json,runpy,subprocess
BASE=Path(__file__).resolve().parent
P=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/autonomous-hardening-20261028/kubernetes1372-binaries')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 authority=runpy.run_path(str(BASE/'scan-kubernetes1372-binaries.py'));cap=authority['capacity']();proof=json.loads((P/'profile-proof.json').read_bytes());old=P/'scan-profile.py';assert sha(old)==proof['profiles']['scan-profile.py']
 for n in range(3):
  r=json.loads((P/('apps-kubernetes1372-native-r5-'+str(n))/'receipt.json').read_bytes());assert not r['scanComplete'] and r['errorCategory']=='results_only_shape'
 mode_changes=[];v=json.loads((P/'verified-binaries.json').read_bytes())
 for name,row in v['binaries'].items():
  blob=Path(row['blob']['path']);assert blob.resolve()==blob and blob.is_relative_to(P/'binaries') and sha(blob)==row['sha256'];before=blob.stat().st_mode&0o777;blob.chmod(0o500);assert sha(blob)==row['sha256'];mode_changes.append({'path':str(blob),'before':oct(before),'after':'0o500','sha256':row['sha256']})
 source=old.read_text().replace('kubernetes1372-native-r5','kubernetes1372-native-rootfs-r5');assert source.count("[str(TOOL), 'filesystem',")==1;source=source.replace("[str(TOOL), 'filesystem',","[str(TOOL), 'rootfs',")
 marker="need(all(identity(p) == ident for p, ident in pins.items()), 'immutable_scanner_inputs')"
 extra="need(any(x.get('Type') == 'gobinary' and any(p.get('Name') == 'stdlib' and p.get('Version') == 'v1.26.10' for p in x.get('Packages') or []) for x in results), 'actual_compiled_go_binary_packages_required')\n            "+marker
 assert source.count(marker)==1;source=source.replace(marker,extra)
 def gates(s):return {n.args[1].value for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)>1 and isinstance(n.args[1],ast.Constant)}
 assert gates(old.read_text())<=gates(source);target=P/'scan-rootfs-profile.py'
 with target.open('x') as f:f.write(source)
 command=json.loads((P/'scan-launch.json').read_bytes())['command'];command=[x.replace('kubernetes1372-native-r5','kubernetes1372-native-rootfs-r5').replace('scan-unit.log','scan-rootfs-unit.log').replace(str(old),str(target)) for x in command]
 record={'capacity':cap,'originalProfileSHA256':sha(old),'newProfileSHA256':sha(target),'allOriginalNamedAssertionsPreserved':True,'extraCompiledBinaryAssertion':True,'modeChanges':mode_changes,'primarySources':['https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/commands/artifact/run.go','https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/fanal/analyzer/language/golang/binary/binary.go'],'reason':'filesystem disables individual-package analyzers; rootfs supports compiled binaries. Go analyzer requires executable mode. Only mode changes on verified binaries, not content; failed null reports remain immutable.','command':command}
 with (P/'rootfs-correction.json').open('x') as f:json.dump(record,f,indent=2)
 r=subprocess.run(command,capture_output=True,text=True)
 with (P/'scan-rootfs-launch.json').open('x') as f:json.dump({'exitCode':r.returncode,'stderr':r.stderr,'command':command},f,indent=2)
 print(r.stderr);assert r.returncode==0
if __name__=='__main__':main()
