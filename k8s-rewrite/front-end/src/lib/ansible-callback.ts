import { ANSIBLE_ROLES } from "./ansible-selection";

// Imported source is included in standalone bundles. The generated temporary plugin
// contains fixed code/role names only, never task labels, hosts, results or values.
export const ansibleCallbackSource = `from ansible.plugins.callback import CallbackBase
import sys

DOCUMENTATION = """
name: bortus_progress
type: stdout
short_description: Emit only fixed BORTUS provisioning lifecycle and role statuses
description:
  - No task names, hosts, module results, values or exception text are emitted.
requirements:
  - Configure as the stdout callback for the optional local BORTUS runner.
"""
ROLES = frozenset(${JSON.stringify(ANSIBLE_ROLES)})

def emit(event):
    sys.stdout.write("BORTUS_PROGRESS_V1 " + event + "\\n")
    sys.stdout.flush()

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "bortus_progress"

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._seen = set()
        self._failed = set()

    def v2_playbook_on_start(self, playbook):
        emit("start")

    def _role(self, task):
        try:
            role = task._role.get_name() if task._role is not None else None
            return role if type(role) is str and role in ROLES else None
        except Exception:
            return None

    def v2_playbook_on_task_start(self, task, is_conditional):
        role = self._role(task)
        if role is not None and role not in self._seen:
            self._seen.add(role)
            emit("role:" + role + ":running")

    def v2_playbook_on_handler_task_start(self, task):
        self.v2_playbook_on_task_start(task, False)

    def _failure(self, result):
        role = self._role(result._task)
        if role is not None and role not in self._failed:
            self._failed.add(role)
            emit("role:" + role + ":failed")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        if not ignore_errors:
            self._failure(result)

    def v2_runner_on_unreachable(self, result):
        self._failure(result)

    def v2_playbook_on_stats(self, stats):
        try:
            failed = any(stats.summarize(host).get("failures", 0) or stats.summarize(host).get("unreachable", 0) for host in stats.processed)
        except Exception:
            failed = True
        emit("complete:failed" if failed else "complete:success")
`;
