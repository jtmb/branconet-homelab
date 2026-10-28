"""Read-only bounded source export qualification; no node-side staging."""
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
        source = Path(self._loader.get_basedir()).parent / 'roles/retired_master_source_exports/files/qualify.py'
        raw = source.read_bytes()
        guard = (N / 'reference-full-properties.py').read_bytes()
        target = N / 'source-export-full-qualification-v2.json'
        if target.exists():
            raise ValueError('original_qualification_or_refusal_preserved')
        payload = json.dumps({'guardSource': base64.b64encode(guard).decode(),
                              'archiveBindings': json.loads((N / 'original-source-archive-bindings.json').read_text())}).encode()
        command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                   '--unit=branconet-master-source-export-qualification-20261027',
                   '--description=Branconet read-only original source export qualification',
                   '--property=MemoryMax=536870912', '--property=MemorySwapMax=0',
                   '--property=CPUQuota=100%', '--property=TasksMax=64', '--property=Nice=15',
                   '--property=RuntimeMaxSec=1200', '--property=ProtectSystem=strict',
                   '--property=ProtectHome=read-only', '/usr/bin/python3', '-B', '-c', raw.decode()]
        response = self._low_level_execute_command(shlex.join(command), sudoable=True, in_data=payload)
        receipt = {'rc': response['rc'], 'sourceSHA256': hashlib.sha256(raw).hexdigest(),
                   'stderr': response.get('stderr', '')}
        try:
            receipt['result'] = json.loads(response.get('stdout', ''))
        except (ValueError, TypeError):
            receipt['unparsedStdout'] = response.get('stdout', '')
        with target.open('x') as out:
            json.dump(receipt, out)
        return dict(result, changed=False, failed=response['rc'] != 0, receipt=str(target))
