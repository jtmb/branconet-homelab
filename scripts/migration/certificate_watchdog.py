"""Off-host monitor/lease observation and its own durable incident outbox.

Missing/invalid API coverage is not evidence that the worker physically died.
Only explicitly armed, UID-pinned observations can establish fresh coverage.
"""
import datetime as dt
import json
import uuid

from certificate_monitor import MAX_DATABASE_BYTES, HISTORY_ROWS, parse_date

OBSERVATIONS = "bortus-certificate-observations"
REASONS = ("monitor-heartbeat", "node02-lease", "coverage")


def assess(observations, lease, enrollment, now):
    try:
        m = observations["metadata"]
        if (observations["kind"] != "ConfigMap" or m["name"] != OBSERVATIONS or
                m["namespace"] != "bortus" or m["uid"] != enrollment["observationsUID"]):
            raise ValueError()
        raw = observations["data"]["snapshot.json"]
        if not isinstance(raw, str) or len(raw.encode()) > 512 * 1024:
            raise ValueError()
        snapshot = json.loads(raw)
        if (type(snapshot["version"]) is not int or snapshot["version"] != 1 or
                snapshot["mode"] not in ("paused", "monitor") or
                snapshot["policy"]["uid"] != enrollment["policyUID"] or
                not isinstance(snapshot["policy"]["revision"], str) or not snapshot["policy"]["revision"]):
            raise ValueError()
        heartbeat = parse_date(snapshot["heartbeatAt"])
        lm = lease["metadata"]
        if (lease["kind"] != "Lease" or lm["namespace"] != "kube-node-lease" or
                lm["name"] != "node02" or lm["uid"] != enrollment["leaseUID"] or
                lease["spec"]["holderIdentity"] != "node02"):
            raise ValueError()
        renew = parse_date(lease["spec"]["renewTime"])
        if not heartbeat or not renew:
            raise ValueError()
        heartbeat_age = (now - heartbeat).total_seconds()
        lease_age = (now - renew).total_seconds()
        if heartbeat_age < -5 or lease_age < -5:
            raise ValueError()
        return {"coverage": "healthy",
                "monitor-heartbeat": "missed" if heartbeat_age > 180 else "healthy",
                "node02-lease": "missed" if lease_age > 90 else "healthy"}
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return {"coverage": "unavailable", "monitor-heartbeat": "unknown", "node02-lease": "unknown"}


class WatchdogState:
    def __init__(self, db):
        self.db = db
        size = db.execute("PRAGMA page_size").fetchone()[0]
        maximum = MAX_DATABASE_BYTES // size
        if db.execute(f"PRAGMA max_page_count={maximum}").fetchone()[0] > maximum:
            raise ValueError("watchdog_database_limit")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS certificate_watchdog_state (
                reason TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS certificate_monitor_outbox (
                id TEXT PRIMARY KEY, resource TEXT NOT NULL, uid TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT);
        """)

    def observe(self, observations, lease, enrollment, now=None):
        now = now or dt.datetime.now(dt.timezone.utc)
        states = assess(observations, lease, enrollment, now)
        with self.db:
            for reason in REASONS:
                state = states[reason]
                previous = self.db.execute("SELECT state FROM certificate_watchdog_state WHERE reason=?", (reason,)).fetchone()
                if state == "unknown":
                    # Coverage loss does not resolve a previously open incident.
                    continue
                if previous != (state,):
                    alert = state if state in ("missed", "unavailable") else (
                        "recovered" if previous in (("missed",), ("unavailable",)) else None)
                    if alert:
                        self.db.execute("INSERT INTO certificate_monitor_outbox VALUES (?,?,?,?,?,NULL)",
                                        (str(uuid.uuid4()), "monitor-heartbeat", reason, alert, now.isoformat()))
                    self.db.execute("INSERT OR REPLACE INTO certificate_watchdog_state VALUES (?,?)", (reason, state))
            self.db.execute("""DELETE FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL AND id NOT IN (
                SELECT id FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL
                ORDER BY delivered_at DESC,rowid DESC LIMIT ?)""", (HISTORY_ROWS,))
        return {"coverage": states["coverage"], "monitorHeartbeat": states["monitor-heartbeat"],
                "node02Lease": states["node02-lease"],
                "pending": self.db.execute("SELECT count(*) FROM certificate_monitor_outbox WHERE delivered_at IS NULL").fetchone()[0],
                "physicalWorkerFailureProven": False}
