"""Disposable Linux producer qualification. Run with an isolated ansible-core on PYTHONPATH.

Usage: python3 tests/qualify-ansible-callback.py <generated-bortus_progress.py>
Only synthetic localhost debug/fail/shell-output tasks run. No operator files are read.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

marker = "private-local-ansible-output-fixture"
callback = pathlib.Path(sys.argv[1]).read_bytes()
evidence = {"python": sys.version.split()[0], "cases": []}
with tempfile.TemporaryDirectory(prefix="bortus-callback-qualification-") as temp:
    root = pathlib.Path(temp)
    plugins = root / "plugins"
    plugins.mkdir()
    (plugins / "bortus_progress.py").write_bytes(callback)
    config = root / "ansible.cfg"
    config.write_text("[defaults]\n")
    env = dict(os.environ, ANSIBLE_CALLBACK_PLUGINS=str(plugins),
               ANSIBLE_STDOUT_CALLBACK="bortus_progress", ANSIBLE_CALLBACKS_ENABLED="bortus_progress",
               ANSIBLE_CONFIG=str(config), ANSIBLE_LOCAL_TEMP=str(root / "ansible-tmp"),
               PYTHONNOUSERSITE="1", ANSIBLE_LOG_PATH="/dev/null", ANSIBLE_FORCE_COLOR="0", ANSIBLE_NOCOLOR="1")
    for outcome in ("success", "failed"):
        tasks = root / "roles" / "kubernetes" / "tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        task_source = "- name: " + marker + " task label\n  ansible.builtin.debug:\n    msg: " + marker + "\n"
        task_source += "- name: " + marker + " result payload\n  ansible.builtin.shell: \"printf '" + marker + "'; printf '" + marker + "' >&2\"\n  changed_when: false\n"
        if outcome == "failed":
            task_source += "- name: " + marker + " error label\n  ansible.builtin.fail:\n    msg: " + marker + "\n"
        (tasks / "main.yml").write_text(task_source)
        private_role = marker + "-role"
        private_tasks = root / "roles" / private_role / "tasks"
        private_tasks.mkdir(parents=True, exist_ok=True)
        (private_tasks / "main.yml").write_text("- ansible.builtin.debug:\n    msg: " + marker + "\n")
        playbook = root / "site.yml"
        playbook.write_text("- hosts: all\n  gather_facts: false\n  roles:\n    - " + private_role + "\n    - kubernetes\n")
        run = subprocess.run([sys.executable, "-m", "ansible.cli.playbook", str(playbook), "-i", "localhost,", "-c", "local"],
                             cwd=root, env=env, capture_output=True, text=True, timeout=60)
        expected = ["BORTUS_PROGRESS_V1 start", "BORTUS_PROGRESS_V1 role:kubernetes:running"]
        if outcome == "failed":
            expected.append("BORTUS_PROGRESS_V1 role:kubernetes:failed")
        expected.append("BORTUS_PROGRESS_V1 complete:" + outcome)
        # Core diagnostics may still reach stderr. The Node consumer discards that channel.
        if run.stdout.splitlines() != expected:
            # Synthetic owned fixture diagnostics only; never used by the application runner.
            print(json.dumps({"exitCode": run.returncode, "stdout": run.stdout.replace(marker, "[synthetic-private]")[:1200],
                              "stderr": run.stderr.replace(marker, "[synthetic-private]")[:2000]}))
            raise AssertionError("Unexpected producer stdout (content withheld)")
        assert (run.returncode == 0) == (outcome == "success"), "Unexpected producer process status"
        assert marker not in run.stdout, "Private payload reached producer records"
        evidence["cases"].append({"outcome": outcome, "exitCode": run.returncode,
                                   "protocolRecords": len(expected), "stdoutPrivate": False,
                                   "stderrPrivate": marker in run.stderr})
    version = subprocess.run([sys.executable, "-m", "ansible.cli.playbook", "--version"],
                             env=env, capture_output=True, text=True, timeout=20)
    evidence["ansible"] = version.stdout.splitlines()[0]
print(json.dumps(evidence))
