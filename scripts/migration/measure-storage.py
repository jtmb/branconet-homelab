#!/usr/bin/env python3
"""Read actual source path sizes/ownership without touching source content."""
import concurrent.futures
import datetime
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    request=json.load(sys.stdin)
    register=json.loads((ROOT/'evidence/service-register.json').read_text())
    paths={host:set() for host in ['192.168.0.4','192.168.0.5','192.168.0.6']}
    for entry in register['entries']:
        instances=entry.get('source_instances',[])
        if entry.get('source_instance'):
            instances=[{'host':entry['source'].split('/')[0],**entry['source_instance']}]
        for instance in instances:
            for mount in instance['mounts']:
                path=mount['Source']
                if mount['Type']!='bind' or path.startswith(('/dev/','/proc/','/sys/','/var/run/','/etc/')):continue
                if path.startswith('/mnt/plex_smb_share') and 'ets2' not in path:continue
                host='192.168.0.5' if path.startswith('/mnt/container-program-files') else instance['host']
                paths[host].add(path)
    def get(host):
        root="import json,os,subprocess\nout=[]\n"
        root+='for path in '+repr(sorted(paths[host]))+':\n'
        root+=" try:\n  stat=os.stat(path);r=subprocess.run(['du','--bytes','--summarize','--',path],capture_output=True,text=True);out.append({'path':path,'uid':stat.st_uid,'gid':stat.st_gid,'mode':oct(stat.st_mode & 0o7777),'bytes':int(r.stdout.split()[0]) if r.stdout else None,'complete':r.returncode==0})\n except OSError as e:out.append({'path':path,'complete':False,'error':type(e).__name__})\nprint(json.dumps(out))\n"
        wrapper="import json,subprocess,sys\nr=subprocess.run("+repr(['sudo','-S','-p','','python3','-c',root])+",input="+repr(request['sudo_password']+'\n')+",text=True,capture_output=True)\nif r.returncode:raise SystemExit('Storage metadata read failed')\nsys.stdout.write(r.stdout)\n"
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,'python3','-'],input=wrapper,capture_output=True,text=True,timeout=180)
        if result.returncode:raise RuntimeError('Storage measurement failed on '+host)
        return host,json.loads(result.stdout)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':dict(pool.map(get,paths))}
    output=ROOT/'evidence/source-storage-sizes.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'paths':sum(map(len,report['nodes'].values())),'incomplete':[{'host':h,'path':p['path']} for h,items in report['nodes'].items() for p in items if not p['complete']],'evidence':str(output)}))

if __name__=='__main__':main()
