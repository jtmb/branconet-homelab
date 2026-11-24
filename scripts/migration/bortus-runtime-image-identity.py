"""Accept an OCI index ID only when its single child is the qualified manifest."""
import json
from pathlib import Path
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
SOURCE='34b8fa18c34576721ff4fb064923f1499598481d'
def matches(observed,expected,proof=None,qualification=None):
 if observed==expected:return True
 if expected!='docker.io/jtmb92/bortus@sha256:e7539b9e79aebe0024f0cfc70dc0a8f2fe89354ab7ffcf9df7a822ffcc343f77':return False
 try:
  p=proof if proof is not None else json.loads((A/'qualified-runtime-index.json').read_bytes())
  q=qualification if qualification is not None else json.loads((A/'qualified-final-image.json').read_bytes())
  return(q['source']==SOURCE and q['image']==expected and q['all_three_nodes_verified']is True and q['current_unfiltered_security_scan_passed']is True and p['manifest']==q['manifest'] and p['archive_sha256']==q['archive_sha256'] and p['single_child_manifest_verified']is True and p['runtime_image_id']=='docker.io/jtmb92/bortus@'+p['index_digest'] and observed==p['runtime_image_id'])
 except (OSError,KeyError,ValueError,TypeError):return False
