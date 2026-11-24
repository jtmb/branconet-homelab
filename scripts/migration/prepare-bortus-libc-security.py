"""Acquire the exact Ubuntu libc security package through signed repository metadata."""
import argparse,hashlib,importlib.util,json,lzma,os,re,subprocess,tarfile,urllib.request
from pathlib import Path
s=importlib.util.spec_from_file_location('runtime_security_input',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--resume-index-format',action='store_true');args=parser.parse_args()
 root=m.OUT/'libc';m.need(os.geteuid()==0);base='https://security.ubuntu.com/ubuntu/'
 if args.resume_index_format:m.need(root.is_dir() and (root/'InRelease').is_file() and not (root/'Packages.xz').exists() and not (root/'receipt.json').exists())
 else:
  m.need(not root.exists());root.mkdir(mode=0o700);(root/'gnupg').mkdir(mode=0o700);m.download(base+'dists/stonking-security/InRelease',root/'InRelease',maximum=4*1024**2)
 with (root/'signature.log').open('wb') as log:result=subprocess.run(['gpgv','--homedir',str(root/'gnupg'),'--keyring','/usr/share/keyrings/ubuntu-archive-keyring.gpg',str(root/'InRelease')],stdout=log,stderr=log,timeout=30)
 m.need(result.returncode==0);text=(root/'InRelease').read_text();algorithm='sha512' if '\nSHA512:\n' in text else 'sha256';section=text.split('\n'+algorithm.upper()+':\n',1)[1].split('\n\n',1)[0];path='main/binary-amd64/Packages.xz';rows=[x.split()for x in section.splitlines() if x.strip()];row=next(x for x in rows if len(x)==3 and x[2]==path);m.need(re.fullmatch('[0-9a-f]{'+('128' if algorithm=='sha512' else '64')+'}',row[0]) is not None)
 index=root/'Packages.xz';m.download(base+'dists/stonking-security/'+path,index,row[0],maximum=32*1024**2,algorithm=algorithm);m.need(index.stat().st_size==int(row[1]));raw=lzma.decompress(index.read_bytes());m.need(len(raw)<128*1024**2)
 package=None
 for paragraph in raw.decode().split('\n\n'):
  values=dict(line.split(': ',1)for line in paragraph.splitlines()if ': ' in line and not line.startswith(' '))
  if values.get('Package')=='libc6' and values.get('Architecture')=='amd64' and values.get('Version')=='2.44-1ubuntu2.1':package=values;break
 m.need(package is not None and package['Filename'].startswith('pool/main/g/glibc/') and '..' not in Path(package['Filename']).parts)
 deb=root/'libc6.deb';package_algorithm='sha512' if 'SHA512' in package else 'sha256';binding=m.download(base+package['Filename'],deb,package[package_algorithm.upper()],maximum=100*1024**2,algorithm=package_algorithm);m.need(deb.stat().st_size==int(package['Size']))
 names=subprocess.check_output(['ar','t',str(deb)]).decode().splitlines();member=next(n for n in names if n.startswith('data.tar.'));data=root/member
 with data.open('xb') as out:subprocess.run(['ar','p',str(deb),member],stdout=out,check=True,timeout=30)
 destination=root/'package';destination.mkdir(mode=0o700)
 with tarfile.open(data) as t:t.extractall(destination,filter='data')
 receipt={'package':'libc6','version':package['Version'],'architecture':'amd64','repository_signature_verified':True,'index_digest':{algorithm:row[0]},'deb':binding,'source':'Ubuntu stonking-security','extracted_root':str(destination),'no_package_scripts_executed':True}
 (root/'receipt.json').write_text(json.dumps(receipt));print(json.dumps(receipt))
if __name__=='__main__':main()
