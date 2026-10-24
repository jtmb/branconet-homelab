from pathlib import Path
import subprocess
base=Path(__file__).parent
s=(base/'preserve-analyze-phase-7e30.py').read_text().replace('characterize-phase-7e30b9b-complete','characterize-phase-baseline-51e8-complete').replace('characterize-phase-7e30b9b-v2','characterize-phase-baseline-51e8-v1').replace('7e30b9b428a66cd3f5e618cec5e694d5f03302ac','51e8cd66379c1f40a95ea02f4da7c8aed848f2a4').replace('acceptedEndHandlerSynchronousSumMs','endEventHandlerSynchronousSumMs').replace('rejectedResponses','responsesWithoutEndEvent').replace('rejectedDataHandlerSynchronousSumMs','noEndEventDataHandlerSynchronousSumMs').replace('bodyReadBeforeEndHandlerSumMs','bodyHeaderToEndEventBeforeHandlerCombinedSumMs')
p=base/'preserve-analyze-baseline-phase.py';p.write_text(s,encoding='utf-8');r=subprocess.run([__import__('sys').executable,'-B',str(p)]);raise SystemExit(r.returncode)
