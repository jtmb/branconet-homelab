"""Send the bounded preservation profile over the existing SSH stdin channel."""
import base64
import hashlib
import json
from pathlib import Path
import shlex

from ansible.plugins.action import ActionBase

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/node-cleanup-20261027/worker2-legacy-plex-preservation')


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        args = self._task.args
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        profile = ROOT / 'profile.json'
        proof = Path(args['proof'])
        helper, safety = Path(args['helper']), Path(args['safety'])
        output = ROOT / 'retirement-result.json'
        for path in (profile, proof, helper, safety, ROOT / 'archive-frozen.py'):
            if path.resolve() != path or not path.is_file() or not path.is_relative_to(ROOT):
                raise ValueError('exact_owned_retirement_inputs')
        if output.exists() or profile.stat().st_size > 192 * 1024**2:
            raise ValueError('preserve_prior_retirement_and_bound_profile')
        source = helper.read_text()
        archive = (ROOT / 'archive-frozen.py').read_bytes()
        safe = safety.read_bytes()
        payload = json.dumps({'profile': json.loads(profile.read_text()), 'proof': json.loads(proof.read_text()),
                              'archiveSource': base64.b64encode(archive).decode(),
                              'archiveSHA256': hashlib.sha256(archive).hexdigest(),
                              'safetySource': base64.b64encode(safe).decode(),
                              'safetySHA256': hashlib.sha256(safe).hexdigest(), 'apply': bool(args['apply'])}).encode()
        response = self._low_level_execute_command(shlex.join(['/usr/bin/python3', '-B', '-c', source]),
                                                   sudoable=True, in_data=payload)
        raw = response.get('stdout', '')
        record = {'exitCode': response['rc'], 'helperSHA256': hashlib.sha256(source.encode()).hexdigest(),
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
