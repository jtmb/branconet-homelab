"""Private ntfy transport and durable at-least-once outbox delivery.

No default destination, redirects, proxies, public relay, or Kubernetes access.
The caller supplies an explicit reviewed configuration and owns serialization.
Server acknowledgement is not proof of delivery to a subscribed human.
"""
import datetime as dt
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlsplit

from certificate_monitor import MAX_DATABASE_BYTES, RESOURCES


class NotificationError(RuntimeError):
    """Fixed public codes; never backend output, endpoints or credentials."""


def validate_destination(value):
    try:
        if not isinstance(value, dict) or set(value) != {"version", "url", "address", "caFile", "tokenFile"}:
            raise ValueError()
        target = urlsplit(value["url"])
        address = ipaddress.ip_address(value["address"])
        private = any(address in network for network in (
            ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("127.0.0.0/8")))
        if (type(value["version"]) is not int or value["version"] != 1 or
                target.scheme != "https" or not target.hostname or target.username or target.password or
                target.query or target.fragment or not re.fullmatch(r"/[-_A-Za-z0-9]{1,64}", target.path) or
                not 1 <= (target.port or 443) <= 65535 or not private or
                any(not isinstance(value[key], str) or not value[key].startswith("/")
                    for key in ("caFile", "tokenFile"))):
            raise ValueError()
        return target
    except (ValueError, TypeError, KeyError, AttributeError):
        raise NotificationError("notification_config_invalid") from None


def event_message(event):
    """Project only existing outbox fields, not arbitrary resource payloads."""
    if (not isinstance(event, dict) or set(event) != {"id", "resource", "uid", "state", "createdAt"} or
            event["resource"] not in (*RESOURCES, "monitor-heartbeat") or
            event["state"] not in ("expired", "warning", "unknown", "pending", "failed", "denied", "unavailable", "missed", "recovered") or
            not all(isinstance(event[key], str) and re.fullmatch(r"[-_.:A-Za-z0-9+TZ]{1,128}", event[key])
                    for key in ("id", "uid", "createdAt"))):
        raise NotificationError("notification_event_invalid")
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to the reviewed private address; verify the URL hostname."""
    def __init__(self, target, address, context):
        # F12 (2026-11-17): a 2026-11-16 delivery took 66.2 minutes across six
        # failures. The strongest supported (not reproduced) cause is this
        # connect/TLS/request timeout racing the sender's 50ms/s CPU quota:
        # measured full child runs took 1.8-2.4s against this 3s budget while
        # the actual network round trip measured ~55ms. Raised to 8s, which
        # still leaves headroom inside the caller's fixed 10s whole-process
        # child deadline (deliver-certificate-notifications.py).
        super().__init__(target.hostname, target.port or 443, timeout=8, context=context)
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def publish_ntfy(config, event, *, token, ca_file):
    """One HTTPS attempt; caller must impose a whole-process deadline as well."""
    connection = None
    stage = "configuration"
    try:
        target = validate_destination(config)
        message = event_message(event)
        if not isinstance(token, str) or not re.fullmatch(r"[-_A-Za-z0-9=]{1,4096}", token):
            raise NotificationError("notification_credential_invalid")
        stage = "trust-context"
        context = ssl.create_default_context(cafile=str(ca_file))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = PinnedHTTPSConnection(target, config["address"], context)
        stage = "request"
        connection.request("POST", target.path, body=message.encode(), headers={
            "Authorization": "Bearer " + token, "Content-Type": "text/plain; charset=utf-8",
            "Title": "BORTUS certificate monitoring", "X-Firebase": "no"})
        stage = "response"
        response = connection.getresponse()
        # Do not follow redirects, consume backend error bodies, or accept a
        # scheduled/partial acknowledgement as a successfully published message.
        if response.status != 200:
            raise NotificationError("notification_not_acknowledged")
        stage = "response-read"
        raw = response.read(16385)
        if len(raw) > 16384:
            raise NotificationError("notification_response_limit")
        stage = "response-decode"
        result = json.loads(raw)
        if (not isinstance(result, dict) or result.get("event") != "message" or
                result.get("topic") != target.path[1:] or result.get("message") != message or
                not isinstance(result.get("id"), str) or
                not re.fullmatch(r"[-_A-Za-z0-9]{1,128}", result["id"])):
            raise NotificationError("notification_ack_invalid")
        return {"accepted": True}
    except NotificationError:
        raise
    except Exception as error:
        failure = NotificationError("notification_transport_unavailable")
        failure.transport_stage = stage
        failure.transport_kind = (
            "trust" if isinstance(error, ssl.SSLCertVerificationError) else
            "tls" if isinstance(error, ssl.SSLError) else
            "timeout" if isinstance(error, TimeoutError) else
            "permission" if isinstance(error, PermissionError) else
            "os" if isinstance(error, OSError) else "unexpected")
        raise failure from None
    finally:
        if connection is not None:
            connection.close()


class OutboxDelivery:
    """Use only with the separate notifier lock held; never initialize a monitor.

    In particular, constructing CertificateMonitor here would incorrectly mark
    another process's active scan interrupted. No DB write lock spans HTTP I/O.
    """
    def __init__(self, connection):
        self.db = connection
        size = self.db.execute("PRAGMA page_size").fetchone()[0]
        maximum = MAX_DATABASE_BYTES // size
        if self.db.execute(f"PRAGMA max_page_count={maximum}").fetchone()[0] > maximum:
            raise NotificationError("notification_database_limit")
        self.db.execute("SELECT id FROM certificate_monitor_outbox LIMIT 1")
        self.db.execute("""CREATE TABLE IF NOT EXISTS certificate_monitor_delivery_retry (
            event_id TEXT PRIMARY KEY, failures INTEGER NOT NULL, due_at TEXT NOT NULL)""")
        self.db.commit()

    def deliver(self, send, now=None, limit=3):
        if type(limit) is not int or not 1 <= limit <= 3:
            raise NotificationError("notification_batch_limit")
        now = now or dt.datetime.now(dt.timezone.utc)
        rows = self.db.execute("""
            SELECT o.id,o.resource,o.uid,o.state,o.created_at,COALESCE(r.failures,0)
            FROM certificate_monitor_outbox o
            LEFT JOIN certificate_monitor_delivery_retry r ON r.event_id=o.id
            WHERE o.delivered_at IS NULL AND (r.due_at IS NULL OR r.due_at<=?)
            ORDER BY o.created_at,o.rowid LIMIT ?""", (now.isoformat(), limit)).fetchall()
        accepted, failed = 0, 0
        for event_id, resource, uid, state, created_at, failures in rows:
            event = dict(id=event_id, resource=resource, uid=uid, state=state, createdAt=created_at)
            # Commit before the call. Crash/unknown outcome retains the event and
            # retry delay; the same stable event ID may be delivered again.
            failures = min(failures + 1, 16)
            due = now + dt.timedelta(seconds=min(3600, 60 * (2 ** min(failures - 1, 6))))
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO certificate_monitor_delivery_retry VALUES (?,?,?)",
                                (event_id, failures, due.isoformat()))
            try:
                event_message(event)
                result = send(event)
                if result != {"accepted": True}:
                    raise NotificationError("notification_ack_invalid")
            except Exception:
                failed += 1
                continue
            with self.db:
                self.db.execute("UPDATE certificate_monitor_outbox SET delivered_at=? WHERE id=? AND delivered_at IS NULL",
                                (now.isoformat(), event_id))
                self.db.execute("DELETE FROM certificate_monitor_delivery_retry WHERE event_id=?", (event_id,))
            accepted += 1
        return {"acceptedByServer": accepted, "failed": failed,
                "pending": self.db.execute("SELECT count(*) FROM certificate_monitor_outbox WHERE delivered_at IS NULL").fetchone()[0],
                "humanReceiptVerified": False}
