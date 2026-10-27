"""Apply the exact qualified master profile through SSH stdin, without staging."""
import base64
import hashlib
import json
from pathlib import Path
import shlex

from ansible.plugins.action import ActionBase

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/node-cleanup-20261027/master-generated-cleanup')


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        args = self._task.args
        if args.get('apply') is not True:
            raise ValueError('explicit_master_retirement_apply_required')
        helper = ROOT / 'master-inputs-r4.py'
        safety = ROOT / 'reference-full-properties.py'
        profile = ROOT / 'profile-r4.json'
        receipt = ROOT / 'inventory-receipt-r4.json'
        output = ROOT / 'retirement-result.json'
        for path in (helper, safety, profile, receipt):
            if path.resolve() != path or not path.is_file() or not path.is_relative_to(ROOT):
                raise ValueError('exact_owned_master_retirement_input')
        if output.exists() or profile.stat().st_size > 128 * 1024**2:
            raise ValueError('preserve_prior_result_and_bound_profile')
        provenance = json.loads(receipt.read_text())
        source, safe = helper.read_bytes(), safety.read_bytes()
        if (provenance['status'] != 'completed' or provenance['exitCode'] != 0
                or hashlib.sha256(source).hexdigest() != provenance['sourceSHA256']
                or hashlib.sha256(profile.read_bytes()).hexdigest() != provenance['profileSHA256']):
            raise ValueError('complete_original_inventory_bindings')
        payload = json.dumps({'mode': 'apply', 'apply': True, 'profile': json.loads(profile.read_text()),
                              'safetySource': base64.b64encode(safe).decode(),
                              'safetySHA256': hashlib.sha256(safe).hexdigest()}).encode()
        command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                   '--unit=branconet-master-generated-retirement-20261027',
                   '--description=Branconet qualified master generated input retirement',
                   '--property=MemoryMax=1073741824', '--property=MemorySwapMax=0',
                   '--property=CPUQuota=100%', '--property=TasksMax=64', '--property=Nice=15',
                   '--property=RuntimeMaxSec=1800', '--property=ProtectSystem=full',
                   '--property=ProtectHome=no', '/usr/bin/env', 'PYTHONDONTWRITEBYTECODE=1',
                   '/usr/bin/python3', '-B', '-c', source.decode()]
        response = self._low_level_execute_command(shlex.join(command), sudoable=True, in_data=payload)
        raw = response.get('stdout', '')
        record = {'exitCode': response['rc'], 'helperSHA256': hashlib.sha256(source).hexdigest(),
                  'profileSHA256': provenance['profileSHA256'],
                  'stderrSHA256': hashlib.sha256(response.get('stderr', '').encode()).hexdigest()}
        try:
            record['result'] = json.loads(raw)
        except (ValueError, TypeError):
            record['unparsedStdout'] = raw
        with output.open('x') as out:
            json.dump(record, out)
        result.update(changed=bool(record.get('result', {}).get('removed')), failed=response['rc'] != 0,
                      receipt=str(output), exit_code=response['rc'])
        return result
