"""Bind maintained scanner metadata to the newly built, source-verified security tool."""
import hashlib,importlib.util,json,os,subprocess,urllib.request
from pathlib import Path
s=importlib.util.spec_from_file_location('security_pin_inputs',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
SOURCE=Path('/mnt/c/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration/k8s-rewrite/front-end/scripts/scanner-inputs.json')
def main():
 root=m.OUT;report=root.parent/'security-source-update.json';m.need(not report.exists());build=json.loads((root/'trivy-build-state.json').read_bytes());m.need(build['state']=='completed' and m.sha(Path(build['binary']))==build['sha256'])
 text=(root/'trivy-binary-version.log').read_text();m.need('Version: 0.76.1-bortus.3' in text and 'go1.27.4' in (root/'trivy-build-info.log').read_text().splitlines()[0])
 verified=json.loads((root/'trivy-source-verification.json').read_bytes());m.need(verified['all_git_blobs_verified']);before=SOURCE.read_bytes();pins=json.loads(before);m.need(pins['version']=='0.76.1-bortus.2' and pins['maintainedSource']['commit']==verified['source_commit'])
 source=root/'trivy-source';m.need(m.sha(source/'LICENSE')==pins['licenseSHA256']);inventory={}
 for p in sorted(source.rglob('*')):
  if p.is_symlink():inventory[str(p.relative_to(source))]={'link':os.readlink(p)}
  elif p.is_file():inventory[str(p.relative_to(source))]={'sha256':m.sha(p)}
 modules={}
 for line in (root/'trivy-build-info.log').read_text().splitlines():
  parts=line.split()
  if len(parts)>=3 and parts[0]=='dep':modules[parts[1]]=parts[2]
 for name in ('go.opentelemetry.io/otel','go.opentelemetry.io/otel/sdk','go.opentelemetry.io/otel/trace'):m.need(modules[name]=='v1.47.0')
 release=json.load(urllib.request.urlopen('https://go.dev/dl/?mode=json',timeout=30));go=next(f for r in release if r['version']=='go1.27.4' for f in r['files']if f['os']=='linux' and f['arch']=='amd64' and f['kind']=='archive');m.need(m.sha(root/go['filename'])==go['sha256'])
 pins.update(version='0.76.1-bortus.3',binarySHA256=build['sha256'],binaryBytes=build['bytes'],source='Maintained Trivy0.76.1-bortus.3 from the pinned upstream Git tree with verified Go1.27.4 and Otel1.47 modules. Official archive fields are upstream references only; no binary fallback. Runtime advisory database remains the deliberately pinned snapshot; current release scan is recorded separately.')
 maintained=pins['maintainedSource'];maintained.update(sourceArchiveSHA256=verified['archive_sha256'],upstreamGitTree=verified['git_tree'],allUpstreamGitBlobsVerified=True,goVersion='go1.27.4',goArchiveSHA256=go['sha256'],sourceTreeSHA256=hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest(),sourceTreeHashFormat='sorted relative file SHA256 or symlink records as canonical JSON',goModSHA256=m.sha(source/'go.mod'),goSumSHA256=m.sha(source/'go.sum'))
 for name in list(maintained['modules'])+['go.opentelemetry.io/otel','go.opentelemetry.io/otel/sdk','go.opentelemetry.io/otel/trace','go.opentelemetry.io/otel/metric']:
  if name in modules:maintained['modules'][name]=modules[name]
 raw=(json.dumps(pins,indent=2)+'\n').encode();m.need(SOURCE.read_bytes()==before);SOURCE.write_bytes(raw)
 record={'state':'updated','path':'k8s-rewrite/front-end/scripts/scanner-inputs.json','before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(raw).hexdigest(),'scanner_sha256':build['sha256'],'scanner_version':pins['version'],'go':'go1.27.4','source_git_commit':verified['source_commit'],'current_image_scan_still_required':True};report.write_text(json.dumps(record));print(json.dumps(record))
if __name__=='__main__':main()
