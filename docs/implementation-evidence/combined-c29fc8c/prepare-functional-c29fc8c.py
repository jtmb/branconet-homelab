from pathlib import Path
import subprocess,sys,hashlib,json
b=Path(__file__).parent;original=b/'dispatch-functional-4668ceb-v3.py';raw=original.read_bytes();text=raw.decode('utf-8')
assert text.count("commit='4668ceb40c3120c7e4053d94edff31f57b7e1f7f'")==1
text=text.replace("commit='4668ceb40c3120c7e4053d94edff31f57b7e1f7f'","commit='c29fc8c44847172e040e83df11c51ad42f1da51e'").replace('functional-4668ceb','functional-c29fc8c')
p=b/'dispatch-functional-c29fc8c.py';assert not p.exists();p.write_bytes(text.encode('utf-8'))
(b/'functional-c29fc8c-launch-provenance.json').write_bytes((json.dumps({'template':str(original),'templateSHA256':hashlib.sha256(raw).hexdigest(),'newScriptSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'delta':'Only exact candidate commit and unique owner/pointer prefixes; all functional commands/limits/raw exporter unchanged'},indent=2)+'\n').encode())
raise SystemExit(subprocess.call([sys.executable,str(p)]))
