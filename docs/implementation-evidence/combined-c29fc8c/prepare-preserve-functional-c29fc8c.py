from pathlib import Path
import hashlib,subprocess,sys,json
b=Path(__file__).parent;o=b/'preserve-functional-4668ceb.py';raw=o.read_bytes();text=raw.decode('utf-8').replace('functional-4668ceb','functional-c29fc8c').replace("[('unit',211),('http',4)]","[('unit',214),('http',4)]")
text=text.replace("retainedLaunchFailures=['functional-c29fc8c-attempt1-launch-failure.json','functional-c29fc8c-attempt2-launch-failure.json']","retainedLaunchFailures=[]")
p=b/'preserve-functional-c29fc8c.py';assert not p.exists();p.write_bytes(text.encode());(b/'functional-c29fc8c-preservation-provenance.json').write_bytes((json.dumps({'templateSHA256':hashlib.sha256(raw).hexdigest(),'scriptSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'delta':'Current owner prefix and actual214 unit count; no original runner/test/acceptance change, no inherited unrelated attempt failures'},indent=2)+'\n').encode())
raise SystemExit(subprocess.call([sys.executable,str(p)]))
