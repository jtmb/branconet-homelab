from pathlib import Path
import subprocess,sys
base=Path(__file__).parent
s=(base/'run-scan-selected-ascii-raw-source.py').read_text().replace('7e30b9b428a66cd3f5e618cec5e694d5f03302ac','4668ceb40c3120c7e4053d94edff31f57b7e1f7f').replace('native-summary-selected-ascii-raw-git','native-distinct-span-raw-git').replace('native-summary-selected-ascii-v3-prequalification-source.json','native-distinct-span-quality-v1/source-manifest.json')
p=base/'run-scan-distinct-span-raw-source.py';p.write_text(s,encoding='utf-8');r=subprocess.run([sys.executable,'-B',str(p)]);raise SystemExit(r.returncode)
