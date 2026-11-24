"""Off-host detector behavior; synthetic API/state only, no live enrollment."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from certificate_watchdog import WatchdogState, assess
from certificate_monitor_runtime import H_ROOT
from ntfy_acl_contract import validate_material, USERS

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)
ENROLLMENT = dict(version=1, armed=True, observationsUID="observations-uid", policyUID="policy-uid", leaseUID="lease-uid")


def inputs(now=NOW):
    observation = {"kind": "ConfigMap", "metadata": {"name": "bortus-certificate-observations",
        "namespace": "bortus", "uid": "observations-uid"}, "data": {"snapshot.json": json.dumps({
        "version": 1, "heartbeatAt": now.isoformat(), "mode": "paused",
        "policy": {"uid": "policy-uid", "revision": "10"}})}}
    lease = {"kind": "Lease", "metadata": {"name": "node02", "namespace": "kube-node-lease", "uid": "lease-uid"},
             "spec": {"holderIdentity": "node02", "renewTime": now.isoformat()}}
    return observation, lease


class WatchdogTests(unittest.TestCase):
    def test_thresholds_paused_heartbeat_and_future_clock_are_distinct(self):
        observation, lease = inputs()
        self.assertEqual(assess(observation, lease, ENROLLMENT, NOW)["monitor-heartbeat"], "healthy")
        fresh_observation, _ = inputs(NOW + dt.timedelta(seconds=90))
        self.assertEqual(assess(fresh_observation, lease, ENROLLMENT, NOW + dt.timedelta(seconds=90))["node02-lease"], "healthy")
        self.assertEqual(assess(fresh_observation, lease, ENROLLMENT, NOW + dt.timedelta(seconds=91))["node02-lease"], "missed")
        _, fresh_lease = inputs(NOW + dt.timedelta(seconds=180))
        self.assertEqual(assess(observation, fresh_lease, ENROLLMENT, NOW + dt.timedelta(seconds=180))["monitor-heartbeat"], "healthy")
        self.assertEqual(assess(observation, fresh_lease, ENROLLMENT, NOW + dt.timedelta(seconds=181))["monitor-heartbeat"], "missed")
        future_observation, future_lease = inputs(NOW + dt.timedelta(seconds=6))
        self.assertEqual(assess(future_observation, future_lease, ENROLLMENT, NOW)["coverage"], "unavailable")

    def test_missing_invalid_or_recreated_resources_are_unknown_not_worker_death(self):
        observation, lease = inputs()
        for bad_observation, bad_lease in [(None, lease), (observation, None),
                (dict(observation, data={"snapshot.json": "{}"}), lease),
                (dict(observation, metadata=observation["metadata"] | {"uid": "recreated"}), lease),
                (observation, dict(lease, metadata=lease["metadata"] | {"uid": "recreated"}))]:
            result = assess(bad_observation, bad_lease, ENROLLMENT, NOW)
            self.assertEqual(result, {"coverage": "unavailable", "monitor-heartbeat": "unknown", "node02-lease": "unknown"})

    def test_persisted_incident_dedup_unknown_does_not_resolve_and_recovery_notifies(self):
        with sqlite3.connect(":memory:") as db:
            observation, lease = inputs()
            WatchdogState(db).observe(observation, lease, ENROLLMENT, NOW + dt.timedelta(minutes=5))
            self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_outbox").fetchone()[0], 2)
            WatchdogState(db).observe(observation, lease, ENROLLMENT, NOW + dt.timedelta(minutes=6))
            self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_outbox").fetchone()[0], 2)
            WatchdogState(db).observe(None, None, ENROLLMENT, NOW + dt.timedelta(minutes=7))
            self.assertEqual(db.execute("SELECT state FROM certificate_watchdog_state WHERE reason='monitor-heartbeat'").fetchone()[0], "missed")
            observation, lease = inputs(NOW + dt.timedelta(minutes=8))
            result = WatchdogState(db).observe(observation, lease, ENROLLMENT, NOW + dt.timedelta(minutes=8))
            self.assertEqual(result["coverage"], "healthy")
            self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_outbox WHERE state='recovered'").fetchone()[0], 3)
            self.assertEqual(result["pending"], 6)
            self.assertFalse(result["physicalWorkerFailureProven"])


class EntrypointTests(unittest.TestCase):
    def test_unarmed_no_network_then_separate_process_restart_preserves_own_outbox(self):
        root = Path(os.environ["BORTUS_MONITOR_TEST_ROOT"]).resolve()
        if H_ROOT.resolve() not in root.parents:
            raise RuntimeError("H-only test output required")
        root.mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="watchdog-", dir=root) as directory:
            base = Path(directory)
            config = base / "enrollment.json"
            config.write_text(json.dumps(ENROLLMENT | {"armed": False}))
            (base / "kubeconfig.json").write_text("{}")
            observation, lease = inputs(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10))
            (base / "observation.json").write_text(json.dumps(observation))
            (base / "lease.json").write_text(json.dumps(lease))
            cli = base / "kubectl"
            cli.write_text("""#!/usr/bin/python3
import json,sys
from pathlib import Path
p=Path(__file__).parent
args=sys.argv[1:]
assert args[:2]==['--kubeconfig',str(p/'kubeconfig.json')]
assert args[2:5]==['--request-timeout=10s','get','--raw']
endpoints={'/api/v1/namespaces/bortus/configmaps/bortus-certificate-observations':'observation.json',
 '/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/node02':'lease.json'}
(p/'called').touch()
print((p/endpoints[args[5]]).read_text())
""")
            cli.chmod(0o700)
            command = [sys.executable, "-B", str(SCRIPTS / "run-certificate-watchdog.py"), "--config", str(config),
                       "--state-dir", str(base / "state"), "--kubectl", str(cli), "--once"]
            env = dict(os.environ, KUBECONFIG=str(base / "kubeconfig.json"))
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertFalse((base / "state").exists())
            self.assertFalse((base / "called").exists())
            config.write_text(json.dumps(ENROLLMENT))
            for _ in range(2):
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)["node02Lease"], "missed")
                self.assertEqual(json.loads(result.stdout)["pending"], 2)
            with sqlite3.connect(base / "state/watchdog.sqlite") as db:
                self.assertEqual(db.execute("SELECT count(*) FROM certificate_monitor_outbox").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='certificate_monitor_runs'").fetchall(), [])
            self.assertFalse((base / "state/monitor.sqlite").exists())
            self.assertFalse((base / "state/watchdog.sqlite").stat().st_mode & 0o077)


class ACLMaterialTests(unittest.TestCase):
    def material(self):
        return {"users": ",".join(f"{name}:$2b$10${chr(65+i)*53}:user" for i, name in enumerate(USERS)),
                "tokens": ",".join(f"{name}:tk_{chr(65+i)*29}" for i, name in enumerate(USERS))}

    def test_exact_ordinary_users_and_distinct_material(self):
        self.assertTrue(validate_material(self.material())["validSyntax"])
        self.assertFalse(validate_material(self.material())["effectiveACLVerified"])
        for change in ("admin", "duplicate-token", "extra-user", "weak-hash", "wrong-token-length"):
            value = self.material()
            if change == "admin":
                value["users"] = value["users"].replace(":user", ":admin", 1)
            elif change == "duplicate-token":
                value["tokens"] = value["tokens"].replace("B" * 29, "A" * 29)
            elif change == "extra-user":
                value["users"] += ",other:$2b$10$" + "D" * 53 + ":user"
            elif change == "wrong-token-length":
                value["tokens"] = value["tokens"].replace("A" * 29, "A" * 60)
            else:
                value["users"] = value["users"].replace("$10$", "$04$")
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "^ntfy_provisioning_invalid$"):
                validate_material(value)

    def test_cli_never_echoes_rejected_credential_material(self):
        value = self.material() | {"unexpected": "synthetic-private-material"}
        p = subprocess.run([sys.executable, "-B", str(SCRIPTS / "ntfy_acl_contract.py")],
                           input=json.dumps(value), capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 1)
        self.assertNotIn("synthetic-private-material", p.stdout + p.stderr)
        self.assertNotIn(value["tokens"], p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
