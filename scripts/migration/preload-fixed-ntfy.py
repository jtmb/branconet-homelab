#!/usr/bin/env python3
"""Stream retained privately published ntfy to node01/node02; no disk carrier.

Reuses the established sealed-memory receiver and saved credential transport,
without altering their original BORTUS identity contract.
"""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-zlib-fixed"
SCRIPT = Path(__file__).resolve().parent
MANIFEST = "sha256:e26ace78ff6edc73a78e68ef96d8282b4ac80415623671dcee5c9edd764a525e"
REFERENCE = "docker.io/jtmb92/bortus@" + MANIFEST


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def receiver():
    # Source is interpreted from stdin memory on each node, never installed.
    legacy = (SCRIPT / "bortus-qualified-preload-node.py").read_text()
    return (
        "namespace={'__name__':'retained_transport'}\nexec(" + repr(legacy) + ",namespace)\n"
        "globals().update({k:v for k,v in namespace.items() if not k.startswith('__')})\n"
        "namespace.update(MANIFEST=" + repr(MANIFEST) + ",REFERENCE=" + repr(REFERENCE) +
        ",ARCHIVE_SHA='f2e9d0893435b9e45f6f9f992b4fde3bf7415204da2b2f5590f83d45a1a910a5',ARCHIVE_BYTES=37076480)\n"
        "import json,subprocess,sys,hashlib,os,time\n"
        "request=json.loads(sys.stdin.buffer.readline(8193))\n"
        "assert set(request)=={'password','reference'} and request['reference']==namespace['REFERENCE']\n"
        "password=request.pop('password')\n"
        "assert isinstance(password,str) and 0<len(password.encode())<=4096 and not any(c in password for c in '\\0\\r\\n')\n"
        "auth=subprocess.run(['sudo','-S','-p','','-v'],input=(password+'\\n').encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25)\n"
        "assert auth.returncode==0\npassword=None\n"
        "assert os.uname().nodename in ('node01','node02')\n"
        "fd=namespace['receive_archive'](sys.stdin.buffer)\n"
        "try:\n"
        " existing=namespace['image_digest']()\n"
        " assert existing in (None,namespace['MANIFEST'])\n"
        " space=os.statvfs('/var/lib/containerd-k8s');free=space.f_bavail*space.f_frsize\n"
        " assert free>max(15*1024**3,space.f_blocks*space.f_frsize*.15)+250000000\n"
        " if existing is None:\n"
        "  process=subprocess.run(namespace['CTR']+['images','import','--platform','linux/amd64','--base-name','docker.io/jtmb92/bortus','--digests','/proc/'+str(os.getpid())+'/fd/'+str(fd)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180)\n"
        "  assert process.returncode==0\n"
        " assert namespace['image_digest']()==namespace['MANIFEST']\n"
        " manifest=namespace['content'](namespace['MANIFEST'])\n"
        " assert len(manifest['layers'])==4 and manifest['config']['digest']=='sha256:c7054886cc52c7bd54bb1bb4d41d31b0c4c6648228fc28f9d160b1bd4662316b'\n"
        " config=namespace['content'](manifest['config']['digest'])\n"
        " assert config['architecture']=='amd64' and config['os']=='linux' and config['config']['User']=='1000:1000'\n"
        " assert namespace['REFERENCE'] in namespace['metadata'](['images','check','--quiet']).decode().splitlines()\n"
        " for layer in manifest['layers']:\n"
        "  raw=namespace['metadata'](['content','get',layer['digest']]) if layer['size']<8*1024**2 else None\n"
        "  if raw is not None: assert len(raw)==layer['size'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==layer['digest'];continue\n"
        "  p=subprocess.Popen(namespace['CTR']+['content','get',layer['digest']],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)\n"
        "  digest=hashlib.sha256();count=0\n"
        "  for block in iter(lambda:p.stdout.read(1024*1024),b''): digest.update(block);count+=len(block);assert count<=layer['size']\n"
        "  assert p.wait(timeout=30)==0 and count==layer['size'] and 'sha256:'+digest.hexdigest()==layer['digest']\n"
        " print(json.dumps({'node':os.uname().nodename,'reference':namespace['REFERENCE'],'manifest':namespace['MANIFEST'],'config':manifest['config']['digest'],'allFourStoredLayerBytesVerified':True,'downloadedAndUnpacked':True,'preexisting':existing is not None,'diskCarrierCreated':False,'deployed':False,'freeBytesBeforeImport':free}))\n"
        "finally:\n os.close(fd)\n")


def main():
    assert not (WORK / "preload-started.json").exists(), "reconcile_existing_preload"
    publication = json.loads((WORK / "publication-result.json").read_text())
    assert publication["state"] == "published-private-verified" and publication["reference"] == REFERENCE
    archive = WORK / "candidate-image.tar"
    with archive.open("rb") as source:
        assert hashlib.file_digest(source, "sha256").hexdigest() == "f2e9d0893435b9e45f6f9f992b4fde3bf7415204da2b2f5590f83d45a1a910a5"
    credential = load("fixed_ntfy_saved_credential", SCRIPT / "saved-node-credential.py")
    password = credential.existing_password()
    code = receiver()
    compile(code, "ntfy-memory-receiver", "exec")
    with (WORK / "preload-started.json").open("x") as stream:
        json.dump({"at": dt.datetime.now(dt.timezone.utc).isoformat(), "nodes": ["node01", "node02"],
                   "reference": REFERENCE, "receiverSHA256": hashlib.sha256(code.encode()).hexdigest(),
                   "nodeImportReserveBytesEach": 250_000_000, "deployed": False}, stream, indent=2)
    results = []
    try:
        for name, ip in (("node01", "192.168.0.4"), ("node02", "192.168.0.6")):
            command = ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                       "-o", "ConnectTimeout=10", "-i", "/home/brajam/.ssh/id_ed25519", "james@" + ip,
                       "python3 -B -c " + shlex.quote(code)]
            # 37 MB already exists as the unique export; transport does not
            # create another archive/tree on host or node.
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                process.stdin.write((json.dumps({"password": password, "reference": REFERENCE}) + "\n").encode())
                with archive.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        process.stdin.write(block)
                process.stdin.close()
                process.wait(timeout=240)
                raw = process.stdout.read(16385)
                assert process.returncode == 0 and len(raw) <= 16384, "preload_failed_reconcile_node"
                reply = json.loads(raw)
                assert reply["node"] == name and reply["manifest"] == MANIFEST
                assert reply["allFourStoredLayerBytesVerified"] and reply["downloadedAndUnpacked"]
                with (WORK / ("preload-" + name + ".json")).open("x") as stream:
                    json.dump(reply, stream, indent=2)
                results.append(reply)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        result = {"passed": True, "nodes": results, "privateReference": REFERENCE,
                  "credentialsPersisted": False, "newDiskCarriers": False, "productionDeployed": False}
        with (WORK / "preload-result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result, indent=2))
    finally:
        password = None


if __name__ == "__main__":
    main()
