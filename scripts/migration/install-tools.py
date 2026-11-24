#!/usr/bin/env python3
"""Install isolated migration CLI tools from checksum-verified upstream releases."""
import concurrent.futures
import hashlib
import io
import json
import os
import pathlib
import tarfile
import urllib.request

ROOT=pathlib.Path.home()/".local/share/branconet-migration"
BIN=ROOT/"bin"
TOOLS={
 "age":("https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz","cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10","age/age"),
 "flux":("https://github.com/fluxcd/flux2/releases/download/v2.9.6/flux_2.9.6_linux_amd64.tar.gz","b4d22673e9246cbd628881f1a9ef3b090085dced291e42d804555cee8e8d42c5","flux"),
 "helm":("https://get.helm.sh/helm-v4.3.0-linux-amd64.tar.gz",None,"linux-amd64/helm"),
 "kubectl":("https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl",None,None),
}

def get(url):
    request=urllib.request.Request(url,headers={"User-Agent":"branconet-migration"})
    with urllib.request.urlopen(request,timeout=120) as response:return response.read()

def install(item):
    name,(url,expected,member)=item
    if expected is None:
        suffix=".sha256sum" if name=="helm" else ".sha256"
        expected=get(url+suffix).decode().split()[0]
    target=BIN/name
    data=get(url)
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected:raise RuntimeError(f"Checksum mismatch for {name}")
    if member:
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
            data=archive.extractfile(member).read()
    temporary=target.with_suffix(".new")
    temporary.write_bytes(data);temporary.chmod(0o755);os.replace(temporary,target)
    return name,{"url":url,"sha256":actual,"path":str(target)}

def main():
    BIN.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        lock=dict(pool.map(install,TOOLS.items()))
    (ROOT/"tool-downloads.json").write_text(json.dumps(lock,indent=2)+"\n")
    print(json.dumps({"installed":sorted(lock),"directory":str(BIN)}))

if __name__=="__main__":main()
