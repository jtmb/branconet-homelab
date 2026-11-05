from pathlib import Path
import io,json,zipfile,subprocess
base=Path(__file__).parent;old=base/'characterize-phase-7e30b9b-v2';owner='characterize-phase-baseline-51e8-v1';prep=base/owner;prep.mkdir(exist_ok=False)
files={n:(old/n).read_bytes() for n in ['child-shim.cjs','request-profiler.cjs','supervisor.py']}
s=files['supervisor.py'].decode().replace('run-05381825cdec/candidate','run-05381825cdec/baseline').replace('7e30b9b428a66cd3f5e618cec5e694d5f03302ac','51e8cd66379c1f40a95ea02f4da7c8aed848f2a4').replace("r['candidate_commit']","r['baseline_commit']").replace("r['sources']['candidate']","r['sources']['baseline']").replace('BORTUS_PERF_LABEL=candidate','BORTUS_PERF_LABEL=baseline')
files['supervisor.py']=s.encode();b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for n,d in files.items():(prep/n).write_bytes(d);z.writestr(n,d)
script=(base/'dispatch-phase-observer-7e30.py').read_text();start=script.index("linux=r'''")+len("linux=r'''");end=script.index("'''",start);linux=script[start:end]
linux=linux.replace('characterize-phase-7e30b9b-v2',owner).replace('run-05381825cdec/candidate','run-05381825cdec/baseline').replace('7e30b9b428a66cd3f5e618cec5e694d5f03302ac','51e8cd66379c1f40a95ea02f4da7c8aed848f2a4')
linux=linux.replace("work.mkdir(mode=0o700,exist_ok=False)","prior=root/'characterize-phase-7e30b9b-v2';t=json.loads((prior/'terminal.json').read_bytes());assert t['actualExit']==0 and t['ownedLiveContainers']==[];assert all(not pathlib.Path('/proc/'+str(x)).exists() for x in [t['pid'],t['childPID']]);\nwork.mkdir(mode=0o700,exist_ok=False)")
r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-B','-c',linux],input=b.getvalue(),capture_output=True);(prep/'dispatch.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace'));raise SystemExit(r.returncode)
