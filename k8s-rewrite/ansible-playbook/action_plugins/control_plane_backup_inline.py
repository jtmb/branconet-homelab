"""Keep the operator credential in the Ansible worker's memory and SSH stdin."""
import contextlib
import hashlib
import io
from pathlib import Path
import runpy
import sys

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        args = self._task.args
        helper = Path(args['helper'])
        if helper.resolve() != helper or not helper.is_file():
            raise ValueError('canonical_backup_helper_required')
        source_sha = hashlib.sha256(helper.read_bytes()).hexdigest()
        if source_sha != args['helper_sha256']:
            raise ValueError('backup_helper_changed_before_action')
        credential = self._play_context.become_pass
        if not isinstance(credential, str) or not credential or len(credential) > 256:
            raise ValueError('authorized_in_memory_operator_credential_required')
        original_argv, module, captured = sys.argv, None, io.StringIO()
        try:
            sys.argv = [str(helper)]
            for name in ('output_dir', 'recipient_file', 'identity_file', 'age_binary', 'etcd_image', 'etcd_digest'):
                sys.argv.extend(['--' + name.replace('_', '-'), str(args[name])])
            with contextlib.redirect_stdout(captured):
                module = runpy.run_path(str(helper), run_name='inline_control_plane_backup',
                                        init_globals={'_CONTROL_PLANE_PRIVILEGE_BYTES': credential.encode()})
                code = module['main']()
            result.update(changed=code == 0, failed=code != 0, rc=code,
                          stdout=captured.getvalue(), helper_sha256=source_sha)
        except Exception as error:
            result.update(changed=False, failed=True, error_type=type(error).__name__,
                          msg='Control-plane backup refused; inspect its protected metadata receipt.',
                          helper_sha256=source_sha)
        finally:
            credential = None
            if module:
                module['main'].__globals__.pop('_CONTROL_PLANE_PRIVILEGE_BYTES', None)
                module.clear()
            sys.argv = original_argv
        return result
