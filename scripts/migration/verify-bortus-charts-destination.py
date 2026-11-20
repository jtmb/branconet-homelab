"""Read the existing Git credential in memory; verify private destination and Actions off."""
import json,os,subprocess,urllib.request
def main():
 p=subprocess.run(['git','credential','fill'],input=b'protocol=https\nhost=github.com\n\n',capture_output=True,timeout=30,env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'))
 if p.returncode:raise RuntimeError('existing_git_credential_unavailable')
 fields=dict(line.split('=',1)for line in p.stdout.decode().splitlines()if'='in line)
 def get(suffix):
  r=urllib.request.Request('https://api.github.com/repos/jtmb/branconet-charts'+suffix,headers={'Authorization':'Bearer '+fields['password'],'Accept':'application/vnd.github+json','User-Agent':'BORTUS-release-verifier'})
  with urllib.request.urlopen(r,timeout=30)as response:return json.load(response)
 repo=get('');actions=get('/actions/permissions');fields.clear()
 if repo.get('private')is not True or actions.get('enabled')is not False:raise RuntimeError('private_actions_disabled_gate_failed')
 print(json.dumps({'repository':'jtmb/branconet-charts','private':True,'actions_enabled':False}))
if __name__=='__main__':main()
