from pathlib import Path
import json,hashlib
base=Path(__file__).parent;out=base/'characterize-phase-7e30b9b-complete';d=json.loads((out/'analysis.json').read_bytes())
for row in d['rows']:
 row['endEventHandlerSynchronousSumMs']=row.pop('acceptedEndHandlerSynchronousSumMs')
 row['responsesWithoutEndEvent']=row.pop('rejectedResponses')
 row['noEndEventDataHandlerSynchronousSumMs']=row.pop('rejectedDataHandlerSynchronousSumMs')
 row['bodyHeaderToEndEventBeforeHandlerCombinedSumMs']=row.pop('bodyReadBeforeEndHandlerSumMs')
d['limitations'].append('Original analysis used accepted/rejected labels inferred from presence of an end event; those labels are not justified because a settled oversized response may emit late end. V2 uses neutral event labels only. No response/error/body inspection was added.')
(out/'analysis-v2.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'analysisV2SHA256':hashlib.sha256((out/'analysis-v2.json').read_bytes()).hexdigest(),'dominantTopFrames':[{ 'fixture':r['fixture'],'frames':r['topWeightedCPUFrames'][:6]} for r in d['rows']]},indent=2))
