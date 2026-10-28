"""Verify preserved controller primary around bounded fixed node-copy retirement."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
from ansible.plugins.action import ActionBase

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
N = F / 'node-cleanup-20261027/master-generated-cleanup'
A = F / 'bortus-cached-runtime-audit-20261025/attempts/3da0b68becea'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        name = task_vars['inventory_hostname']
        if name not in ('masternode', 'workernode2'):
            raise ValueError('fixed_nodes_only')
        target = N / ('fixed-transfer-copies-' + name + '.json')
        if target.exists() or not F.is_mount():
            raise ValueError('preserve_prior_receipt_and_original_physical_root')
        raw = (Path(self._loader.get_basedir()).parent / 'roles/retired_fixed_transfer_copies/files/retire.py').read_bytes()
        exported = json.loads((A / 'export.json').read_text())
        transfer = json.loads((A / 'export.controller.json').read_text())
        archive = A / 'runtime.oci.tar'
        if (exported['archiveSHA256'] != 'fa7df63ec2a22c2eedff17a16e5d1e7b555d6b93802b5c470aafdccad90731d4'
                or exported['archiveBytes'] != archive.stat().st_size or transfer['exitCode'] != 0
                or transfer['remoteReceiptSHA256'] != sha(A / 'export.json')
                or sha(archive) != exported['archiveSHA256']):
            raise ValueError('exact_original_completed_export_and_full_primary_hash')
        proof = {'path': str(archive), 'sha256': exported['archiveSHA256'], 'bytes': exported['archiveBytes'],
                 'fullHashVerified': True, 'originalExportAndTransferCompleted': True}
        payload = {'hostname': name, 'controllerArchiveProof': proof,
                   'guardSource': base64.b64encode((N / 'reference-full-properties.py').read_bytes()).decode()}
        receipt = {'sourceSHA256': hashlib.sha256(raw).hexdigest(), 'controllerPrimary': proof, 'phases': {}}
        try:
            for phase in ('inventory', 'retire'):
                payload['mode'] = phase
                if phase == 'retire':
                    payload['qualification'] = receipt['phases']['inventory']['result']
                command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                           '--unit=branconet-fixed-transfer-copies-' + phase + '-20261028',
                           '--description=Branconet exact redundant transfer file retirement',
                           '--property=MemoryMax=536870912', '--property=MemorySwapMax=0',
                           '--property=CPUQuota=100%', '--property=TasksMax=64', '--property=Nice=15',
                           '--property=RuntimeMaxSec=600', '--property=PrivateNetwork=yes',
                           '--property=ProtectSystem=' + ('strict' if phase == 'inventory' else 'full'),
                           '--property=ProtectHome=' + ('read-only' if phase == 'inventory' else 'no'),
                           '/usr/bin/python3', '-B', '-c', raw.decode()]
                response = self._low_level_execute_command(shlex.join(command), sudoable=True, in_data=json.dumps(payload).encode())
                record = {'rc': response['rc'], 'stderr': response.get('stderr', '')}
                try:
                    record['result'] = json.loads(response.get('stdout', ''))
                except (ValueError, TypeError):
                    record['unparsedStdout'] = response.get('stdout', '')
                receipt['phases'][phase] = record
                if response['rc'] != 0:
                    break
        finally:
            receipt['controllerPrimaryUnchanged'] = sha(archive) == proof['sha256']
            with target.open('x') as f:
                json.dump(receipt, f)
        success = (receipt.get('controllerPrimaryUnchanged') and receipt['phases'].get('retire', {}).get('rc') == 0)
        return dict(result, failed=not success, changed=bool(receipt['phases'].get('retire', {}).get('result', {}).get('removed')), receipt=str(target))
