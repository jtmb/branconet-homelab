"""Bounded exact old analysis-cache retirement; no remote staging or scans."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
from ansible.plugins.action import ActionBase

N = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/node-cleanup-20261027/master-generated-cleanup')


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        target = N / 'master-analysis-cache-retirement.json'
        if target.exists() or task_vars['inventory_hostname'] != 'masternode':
            raise ValueError('fixed_master_and_prior_receipt_preservation')
        raw = (Path(self._loader.get_basedir()).parent / 'roles/retired_master_analysis_cache/files/retire.py').read_bytes()
        payload = {'guardSource': base64.b64encode((N / 'reference-full-properties.py').read_bytes()).decode()}
        receipt = {'sourceSHA256': hashlib.sha256(raw).hexdigest(), 'phases': {}}
        try:
            for phase in ('inventory', 'retire'):
                payload['mode'] = phase
                if phase == 'retire':
                    payload['qualification'] = receipt['phases']['inventory']['result']
                command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                           '--unit=branconet-master-analysis-cache-' + phase + '-20261028',
                           '--description=Branconet exact inactive Trivy analysis cache retirement',
                           '--property=MemoryMax=536870912', '--property=MemorySwapMax=0',
                           '--property=CPUQuota=100%', '--property=TasksMax=64', '--property=Nice=15',
                           '--property=RuntimeMaxSec=600', '--property=PrivateNetwork=yes',
                           '--property=ProtectSystem=' + ('strict' if phase == 'inventory' else 'full'),
                           '--property=ProtectHome=' + ('read-only' if phase == 'inventory' else 'no'),
                           '/usr/bin/python3', '-B', '-c', raw.decode()]
                p = self._low_level_execute_command(shlex.join(command), sudoable=True, in_data=json.dumps(payload).encode())
                record = {'rc': p['rc'], 'stderr': p.get('stderr', '')}
                try:
                    record['result'] = json.loads(p.get('stdout', ''))
                except (ValueError, TypeError):
                    record['unparsedStdout'] = p.get('stdout', '')
                receipt['phases'][phase] = record
                if p['rc'] != 0:
                    break
        finally:
            with target.open('x') as f:
                json.dump(receipt, f)
        return dict(result, failed=receipt['phases'].get('retire', {}).get('rc') != 0,
                    changed=bool(receipt['phases'].get('retire', {}).get('result', {}).get('removed')), receipt=str(target))
