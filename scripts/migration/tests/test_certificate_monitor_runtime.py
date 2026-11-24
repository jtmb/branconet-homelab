"""Actual runner entrypoint checks; all synthetic files stay under explicit H."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from certificate_monitor_runtime import (H_ROOT, HOST_CA, HOST_TOKEN,
                                         private_state_file, validate_host_config)

POLICY = "bortus-certificate-policy"
OBSERVATIONS = "bortus-certificate-observations"
FAKE = r'''#!/usr/bin/python3
import json,sys
from pathlib import Path
root=Path(__file__).parent
args=sys.argv[1:]
calls=root/'calls.json'
history=json.loads(calls.read_text()) if calls.exists() else []
history.append(args);calls.write_text(json.dumps(history))
if args[:2]!=['--request-timeout=20s','get'] and args[:2]!=['--request-timeout=20s','patch']:
    sys.exit(91)
if args[1]=='get':
    if args[2]=='configmap' and args[3] in ('bortus-certificate-policy','bortus-certificate-observations'):
        print((root/(args[3]+'.json')).read_text())
    elif args[2]=='certificates.cert-manager.io' and '-A' in args:
        print((root/'inventory.json').read_text())
    elif args[2]=='certificatesigningrequests.certificates.k8s.io':
        print('{"items":[]}')
    else:sys.exit(92)
elif args[2:5]==['configmap','bortus-certificate-observations','-n']:
    assert args[-2:]==['--type=json','--patch-file=/dev/stdin']
    patch=json.load(sys.stdin)
    target=root/'bortus-certificate-observations.json'
    value=json.loads(target.read_text())
    assert patch[0]=={'op':'test','path':'/metadata/uid','value':value['metadata']['uid']}
    assert patch[1]=={'op':'test','path':'/metadata/resourceVersion','value':value['metadata']['resourceVersion']}
    assert patch[2]['path']=='/data/snapshot.json' and patch[2]['op']=='add'
    value['data']['snapshot.json']=patch[2]['value']
    value['metadata']['resourceVersion']=str(int(value['metadata']['resourceVersion'])+1)
    target.write_text(json.dumps(value))
    print('configmap patched')
else:sys.exit(93)
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ["BORTUS_MONITOR_TEST_ROOT"]).resolve()
        if H_ROOT.resolve() not in root.parents:
            raise RuntimeError("Test output must remain under the existing H store")
        root.mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="runner-", dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cli = self.root / "kubectl"
        self.cli.write_text(FAKE)
        self.cli.chmod(0o700)
        self.state = self.root / "state"
        self.env = dict(os.environ, KUBECONFIG=str(self.root / "synthetic-kubeconfig.json"),
                        PYTHONDONTWRITEBYTECODE="1")
        (self.root / "synthetic-kubeconfig.json").write_text("{}")
        policy = {"version": 1, "mode": "monitor", "scanIntervalSeconds": 300, "expiryWarningDays": 7}
        for name, data in [(POLICY, {"policy.json": json.dumps(policy)}), (OBSERVATIONS, {})]:
            value = {"kind": "ConfigMap", "metadata": {"name": name, "namespace": "bortus",
                     "uid": name + "-uid", "resourceVersion": "10"}, "data": data}
            (self.root / (name + ".json")).write_text(json.dumps(value))
        expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()
        (self.root / "inventory.json").write_text(json.dumps({"items": [{
            "metadata": {"uid": "fixture-cert", "name": "fixture-tls"},
            "status": {"notAfter": expiry, "conditions": [{"type": "Ready", "status": "True"}]},
        }]}))

    def command(self, execution="--once"):
        return [sys.executable, "-B", str(SCRIPTS / "run-certificate-monitor.py"),
                "--state-dir", str(self.state), "--kubectl", str(self.cli),
                execution, "--control-plane"]

    def run_once(self):
        return subprocess.run(self.command(), env=self.env, capture_output=True, text=True, timeout=10)

    def test_real_entrypoint_reopens_private_state_and_does_not_rescan_or_duplicate_outbox(self):
        for _ in range(2):
            result = self.run_once()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["runState"], "complete")
        with sqlite3.connect(self.state / "monitor.sqlite") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_runs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_outbox").fetchone()[0], 1)
        calls = json.loads((self.root / "calls.json").read_text())
        self.assertEqual(sum(args[2] == "certificates.cert-manager.io" for args in calls), 1)
        self.assertEqual(sum(args[1] == "patch" for args in calls), 2)
        self.assertFalse((self.state / "monitor.sqlite").stat().st_mode & 0o077)

    def test_real_loop_excludes_contender_and_exits_interval_wait_on_sigterm(self):
        child = subprocess.Popen(self.command("--loop"), env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(10), "No first heartbeat")
            self.assertEqual(json.loads(child.stdout.readline())["runState"], "complete")
            contender = self.run_once()
            self.assertEqual(contender.returncode, 1)
            self.assertEqual(json.loads(contender.stdout)["state"], "already-running")
            started = time.monotonic()
            child.terminate()
            self.assertEqual(child.wait(timeout=5), 0)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(self.run_once().returncode, 0)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
            child.stdout.close()
            child.stderr.close()

    def test_local_entrypoint_cannot_opt_into_host_paths_or_write_outside_H(self):
        command = self.command()
        outside = "/tmp/opencode/forbidden-monitor-state-" + self.root.name
        command[command.index(str(self.state))] = outside
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(Path(outside).exists())
        result = subprocess.run(self.command() + ["--managed-host"], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.state.exists())

    def test_control_failure_is_sanitized_and_cannot_publish_fresh_heartbeat(self):
        (self.root / (POLICY + ".json")).write_text("private-backend-fixture-error")
        before = (self.root / (OBSERVATIONS + ".json")).read_text()
        result = self.run_once()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"state": "control-unavailable", "heartbeatPublished": False})
        self.assertNotIn("private-backend", result.stdout + result.stderr)
        self.assertEqual((self.root / (OBSERVATIONS + ".json")).read_text(), before)

    def test_public_or_symlinked_state_is_refused(self):
        value = self.root / "public.sqlite"
        value.write_text("synthetic")
        value.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "state_file_not_private"):
            private_state_file(value)
        link = self.root / "alias.sqlite"
        link.symlink_to(value)
        with self.assertRaisesRegex(ValueError, "state_file_symlink_refused"):
            private_state_file(link)


class HostConfigTests(unittest.TestCase):
    def test_fixed_host_profile_refuses_exec_insecure_or_extra_identity(self):
        config = {
            "apiVersion": "v1", "kind": "Config",
            "clusters": [{"name": "branconet", "cluster": {
                "server": "https://192.168.0.251:6443", "certificate-authority": str(HOST_CA)}}],
            "users": [{"name": "bortus-certificate-monitor", "user": {"tokenFile": str(HOST_TOKEN)}}],
            "contexts": [{"name": "monitor", "context": {
                "cluster": "branconet", "user": "bortus-certificate-monitor", "namespace": "bortus"}}],
            "current-context": "monitor",
        }
        validate_host_config(config)
        for attack in ("exec", "insecure", "extra-user"):
            candidate = copy.deepcopy(config)
            if attack == "exec":
                candidate["users"][0]["user"]["exec"] = {"command": "not-allowed"}
            elif attack == "insecure":
                candidate["clusters"][0]["cluster"]["insecure-skip-tls-verify"] = True
            else:
                candidate["users"].append({"name": "admin", "user": {}})
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, "host_kubeconfig_not_scoped_profile"):
                validate_host_config(candidate)


if __name__ == "__main__":
    unittest.main()
