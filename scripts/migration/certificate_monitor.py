"""Durable metadata-only certificate monitoring; no approval/renewal authority.

The caller supplies a scoped Kubernetes reader. This module never reads TLS
Secrets or raw CSR requests, and never runs host maintenance.
"""
import datetime as dt
import json
import uuid

RESOURCES = ("certificates.cert-manager.io", "certificatesigningrequests.certificates.k8s.io")
# Serving-certificate endpoints probed over the wire by scan_tls_endpoints().
# The notification sender allows exactly RESOURCES, TLS_ENDPOINT_RESOURCE and
# "monitor-heartbeat" — nothing else can ever reach the ntfy topic.
TLS_ENDPOINT_RESOURCE = "tls-endpoint"
MAX_DATABASE_BYTES = 16 * 1024 * 1024
HISTORY_ROWS = 1000


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def normalize(resource, value, now, expiry_warning_days=7):
    """Bound and project only public fields; do not persist API response blobs."""
    if not isinstance(value, dict):
        raise ValueError("inventory_invalid")
    rows = value.get("items")
    if rows is None and value.get("kind") in ("CertificateList", "CertificateSigningRequestList"):
        rows = []
    meta = value.get("metadata") or {}
    if (not isinstance(rows, list) or len(rows) > 1000 or not isinstance(meta, dict) or
            meta.get("continue") or meta.get("remainingItemCount", 0)):
        raise ValueError("inventory_incomplete")
    result = []
    for row in rows:
        metadata, spec, status = row.get("metadata", {}), row.get("spec", {}), row.get("status", {})
        if not all(isinstance(part, dict) for part in (metadata, spec, status)):
            raise ValueError("inventory_invalid")
        if not all(isinstance(metadata.get(key), str) and 0 < len(metadata[key]) <= 512 for key in ("uid", "name")):
            raise ValueError("inventory_identity_invalid")
        conditions = {c.get("type") for c in status.get("conditions", []) if c.get("status") == "True"}
        record = {"uid": metadata["uid"], "name": metadata["name"], "namespace": metadata.get("namespace", ""),
                  "resource": resource}
        if resource == RESOURCES[0]:
            expiry, renewal = parse_date(status.get("notAfter")), parse_date(status.get("renewalTime"))
            state = ("expired" if expiry and expiry <= now else "renewing" if "Issuing" in conditions else
                     "unknown" if not expiry else "warning" if "Ready" not in conditions or
                     (renewal and renewal <= now) or (expiry - now).total_seconds() <= expiry_warning_days * 86400 else "healthy")
            record.update(state=state, notAfter=expiry.isoformat() if expiry else None,
                          renewalTime=renewal.isoformat() if renewal else None, renewalOwner="cert-manager")
        else:
            state = ("denied" if "Denied" in conditions else "failed" if "Failed" in conditions else
                     "issued" if status.get("certificate") else "approved" if "Approved" in conditions else "pending")
            record.update(state=state, requester=spec.get("username", "Unknown"), signer=spec.get("signerName", "Unknown"))
        result.append(record)
    return result


def normalize_tls_endpoint(name, value, now, expiry_warning_days=7):
    """Project only the leaf certificate's expiry from a live TLS probe result.

    The probe is a plain TLS handshake against the node's own API server or
    kubelet port; it never reads host files or requires any host privilege,
    matching the existing low-privilege UID998 monitor design.
    """
    if not isinstance(value, dict) or set(value) != {"notAfter"}:
        raise ValueError("tls_probe_invalid")
    expiry = parse_date(value["notAfter"])
    if not expiry:
        raise ValueError("tls_probe_expiry_invalid")
    state = ("expired" if expiry <= now else
             "warning" if (expiry - now).total_seconds() <= expiry_warning_days * 86400 else "healthy")
    return {"uid": name, "name": name, "resource": TLS_ENDPOINT_RESOURCE, "state": state,
            "notAfter": expiry.isoformat()}


class CertificateMonitor:
    def __init__(self, connection):
        self.db = connection
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        maximum_pages = MAX_DATABASE_BYTES // page_size
        actual_pages = self.db.execute(f"PRAGMA max_page_count={maximum_pages}").fetchone()[0]
        if actual_pages > maximum_pages:
            raise ValueError("monitor_database_exceeds_limit")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS certificate_monitor_runs (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS certificate_monitor_sources (
                resource TEXT PRIMARY KEY, checked_at TEXT NOT NULL, available INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS certificate_monitor_observations (
                resource TEXT NOT NULL, uid TEXT NOT NULL, metadata TEXT NOT NULL, observed_at TEXT NOT NULL,
                PRIMARY KEY (resource, uid));
            CREATE TABLE IF NOT EXISTS certificate_monitor_outbox (
                id TEXT PRIMARY KEY, resource TEXT NOT NULL, uid TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL, delivered_at TEXT);
            CREATE TABLE IF NOT EXISTS certificate_monitor_alert_state (
                resource TEXT NOT NULL, uid TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY (resource, uid));
            CREATE TABLE IF NOT EXISTS certificate_monitor_policy (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                uid TEXT NOT NULL, revision TEXT NOT NULL, policy TEXT NOT NULL);
        """)
        # An interrupted read-only scan can be safely retried; no mutation is replayed.
        with self.db:
            self.db.execute("UPDATE certificate_monitor_runs SET state='interrupted', finished_at=? WHERE state='running'",
                            (timestamp(),))

    def scan(self, read, now=None, expiry_warning_days=7):
        now = now or dt.datetime.now(dt.timezone.utc)
        at, run = now.isoformat(), str(uuid.uuid4())
        with self.db:
            self.db.execute("INSERT INTO certificate_monitor_runs VALUES (?, ?, NULL, 'running')", (run, at))
        failures = []
        for resource in RESOURCES:
            try:
                records = normalize(resource, read(resource), now, expiry_warning_days)
                with self.db:
                    # A successful complete list replaces this source only.
                    self.db.execute("DELETE FROM certificate_monitor_observations WHERE resource=?", (resource,))
                    for record in records:
                        self.db.execute("INSERT INTO certificate_monitor_observations VALUES (?, ?, ?, ?)",
                                        (resource, record["uid"], json.dumps(record, sort_keys=True), at))
                        previous = self.db.execute(
                            "SELECT state FROM certificate_monitor_alert_state WHERE resource=? AND uid=?",
                            (resource, record["uid"])).fetchone()
                        state = record["state"]
                        if state in ("expired", "warning", "unknown", "pending", "failed", "denied") and previous != (state,):
                            self.db.execute("INSERT INTO certificate_monitor_outbox VALUES (?, ?, ?, ?, ?, NULL)",
                                            (str(uuid.uuid4()), resource, record["uid"], state, at))
                        self.db.execute("INSERT OR REPLACE INTO certificate_monitor_alert_state VALUES (?, ?, ?)",
                                        (resource, record["uid"], state))
                    # Replace the per-source availability incident only after success.
                    self.db.execute("DELETE FROM certificate_monitor_alert_state WHERE resource=? AND uid='source-unavailable'", (resource,))
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_sources VALUES (?, ?, 1)", (resource, at))
            except Exception:
                # Backend exceptions may contain sensitive process output. Persist only a fixed incident code.
                failures.append(resource)
                with self.db:
                    previous = self.db.execute("SELECT state FROM certificate_monitor_alert_state WHERE resource=? AND uid='source-unavailable'", (resource,)).fetchone()
                    if previous != ("unavailable",):
                        self.db.execute("INSERT INTO certificate_monitor_outbox VALUES (?, ?, ?, ?, ?, NULL)",
                                        (str(uuid.uuid4()), resource, "source-unavailable", "unavailable", at))
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_alert_state VALUES (?, ?, 'unavailable')",
                                    (resource, "source-unavailable"))
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_sources VALUES (?, ?, 0)", (resource, at))
        with self.db:
            self.db.execute("UPDATE certificate_monitor_runs SET finished_at=?, state=? WHERE id=?",
                             (timestamp(), "partial" if failures else "complete", run))
            # Keep recent diagnostic history, but never delete an undelivered
            # alert to make space or pretend its delivery succeeded.
            self.db.execute("""
                DELETE FROM certificate_monitor_runs WHERE state!='running' AND id NOT IN
                (SELECT id FROM certificate_monitor_runs ORDER BY started_at DESC, rowid DESC LIMIT ?)
            """, (HISTORY_ROWS,))
            self.db.execute("""
                DELETE FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL AND id NOT IN
                (SELECT id FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL
                 ORDER BY delivered_at DESC, rowid DESC LIMIT ?)
            """, (HISTORY_ROWS,))
        return {"runId": run, "state": "partial" if failures else "complete", "unavailable": failures}

    def scan_tls_endpoints(self, probe, endpoints, now=None, expiry_warning_days=30):
        """Watch control-plane/kubelet serving certs via a live TLS handshake.

        cert-manager Certificates and CSRs are Kubernetes API objects; kubeadm
        and kubelet serving certificates are host files with no API
        equivalent. Rather than grant this monitor host filesystem or root
        access, each endpoint's own live leaf certificate is read over the
        wire (the same approach already qualified for kubelet-serving CSR
        verification), so the privilege boundary is unchanged. `endpoints` is
        an iterable of (name, probe_args) pairs; `probe(*probe_args)` returns
        {"notAfter": "<iso8601>"} or raises on an unreachable/failed probe.
        """
        now = now or dt.datetime.now(dt.timezone.utc)
        at = now.isoformat()
        resource = TLS_ENDPOINT_RESOURCE
        failures = []
        for name, probe_args in endpoints:
            uid = "tls-endpoint:" + name
            try:
                record = normalize_tls_endpoint(name, probe(*probe_args), now, expiry_warning_days)
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_observations VALUES (?, ?, ?, ?)",
                                    (resource, uid, json.dumps(record, sort_keys=True), at))
                    previous = self.db.execute(
                        "SELECT state FROM certificate_monitor_alert_state WHERE resource=? AND uid=?",
                        (resource, uid)).fetchone()
                    state = record["state"]
                    if state in ("expired", "warning") and previous != (state,):
                        self.db.execute("INSERT INTO certificate_monitor_outbox VALUES (?, ?, ?, ?, ?, NULL)",
                                        (str(uuid.uuid4()), resource, uid, state, at))
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_alert_state VALUES (?, ?, ?)",
                                    (resource, uid, state))
            except Exception:
                failures.append(name)
                with self.db:
                    previous = self.db.execute(
                        "SELECT state FROM certificate_monitor_alert_state WHERE resource=? AND uid=?",
                        (resource, uid)).fetchone()
                    if previous != ("unavailable",):
                        self.db.execute("INSERT INTO certificate_monitor_outbox VALUES (?, ?, ?, ?, ?, NULL)",
                                        (str(uuid.uuid4()), resource, uid, "unavailable", at))
                    self.db.execute("INSERT OR REPLACE INTO certificate_monitor_alert_state VALUES (?, ?, 'unavailable')",
                                    (resource, uid))
        with self.db:
            self.db.execute("""
                DELETE FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL AND id NOT IN
                (SELECT id FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL
                 ORDER BY delivered_at DESC, rowid DESC LIMIT ?)
            """, (HISTORY_ROWS,))
        return {"state": "partial" if failures else "complete", "unavailable": failures}

    def delivery_state(self):
        """Derived delivery state: never assume a sender exists.

        pending-delivery  the outbox holds undelivered events
        delivered         at least one event was delivered and none is pending
        no-delivery-yet   a sender path has been used, but nothing succeeded yet
        not-configured    no delivery has ever been observed
        """
        row = self.db.execute(
            "SELECT COUNT(*) FILTER (WHERE delivered_at IS NULL),"
            " COUNT(*) FILTER (WHERE delivered_at IS NOT NULL)"
            " FROM certificate_monitor_outbox").fetchone()
        pending, delivered = int(row[0] or 0), int(row[1] or 0)
        if pending:
            return "pending-delivery"
        if delivered:
            return "delivered"
        attempted = self.db.execute("SELECT COUNT(*) FROM certificate_monitor_outbox").fetchone()[0]
        return "no-delivery-yet" if attempted else "not-configured"

    def snapshot(self, now=None):
        now = now or dt.datetime.now(dt.timezone.utc)
        sources = []
        for resource, at, available in self.db.execute("SELECT resource, checked_at, available FROM certificate_monitor_sources ORDER BY resource"):
            observed = parse_date(at)
            stale = not observed or not 0 <= (now - observed).total_seconds() <= 15 * 60
            sources.append({"resource": resource, "checkedAt": at, "available": bool(available), "stale": stale})
        observations = [json.loads(row[0]) | {"observedAt": row[1]} for row in self.db.execute(
            "SELECT metadata, observed_at FROM certificate_monitor_observations ORDER BY resource, uid")]
        last = self.db.execute("SELECT id, started_at, finished_at, state FROM certificate_monitor_runs ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        return {"sources": sources, "observations": observations,
                "lastRun": dict(zip(("id", "startedAt", "finishedAt", "state"), last)) if last else None,
                "notificationsPending": self.db.execute("SELECT COUNT(*) FROM certificate_monitor_outbox WHERE delivered_at IS NULL").fetchone()[0],
                "notificationDelivery": self.delivery_state(),
                "hostCoverage": "not-connected", "endpointVerification": "not-connected"}
