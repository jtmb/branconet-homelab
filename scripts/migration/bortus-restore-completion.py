"""Pure Longhorn 1.12.1 Volume transition evaluator; no API, I/O or data proof.

The caller must durably prove a bounded, continuous watch began before creation,
validate its installed schema/source, and produce the closed metadata projection
documented in docs/BORTUS-RESTORE-COMPLETION.md. A boolean cannot prove a watch.
"""

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit


LONGHORN_VERSION = "1.12.1"
API_VERSION = "longhorn.io/v1beta2"
SOURCE_COMMIT = "8320238242e8c804325d9588ec1db10feb9f36b8"
MAX_EVENTS = 256
MAX_CONDITIONS = 32
SIZE_BYTES = "1073741824"
NAS_HOST = "192.168.0.8"
NAS_PATH = "/container_backups/k8s-migration-20261009/longhorn"


class RestoreTransitionRefused(RuntimeError):
    """Only fixed codes and a bounded event index; never include input payloads."""

    def __init__(self, code, event_index=None):
        self.code = code
        self.event_index = event_index
        super().__init__(code)


@dataclass(frozen=True)
class BackupIdentity:
    name: str
    namespace: str
    uid: str
    resource_version: str


@dataclass(frozen=True)
class RestoreExpectation:
    volume_name: str
    volume_uid: str
    namespace: str
    backup_url: str
    backup: BackupIdentity
    original_volume_uid: str
    original_volume_handle: str
    source_size_bytes: str


@dataclass(frozen=True)
class RestoreTransition:
    """Metadata eligibility only; current health, consumers and data are pending."""

    volume_name: str
    volume_uid: str
    namespace: str
    backup: BackupIdentity
    original_volume_uid: str
    original_volume_handle: str
    initialized_resource_version: str
    completed_resource_version: str
    last_volume_resource_version: str
    observed_events: int
    metadata_transition_eligible: bool = True
    data_acceptance: bool = False


def _require(ok, code, index=None):
    if not ok:
        raise RestoreTransitionRefused(code, index)


def _text(value, cap):
    return type(value) is str and 0 < len(value) <= cap and value.isascii() and all(
        32 < ord(char) < 127 for char in value)


def _name(value):
    return _text(value, 253) and re.fullmatch(
        r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value) is not None


def _uid(value):
    return _text(value, 36) and re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value) is not None


def _mapping(value, required, optional, code, index=None):
    # Exact built-in containers avoid user-defined accessors/iterators in this ABI.
    _require(type(value) is dict, code, index)
    _require(len(value) <= len(required) + len(optional), code, index)
    _require(all(type(key) is str and key in required | optional for key in value)
             and required <= value.keys(), code, index)
    return value


def _expected(expected):
    _require(type(expected) is RestoreExpectation, "expected_identity")
    backup = expected.backup
    _require(type(backup) is BackupIdentity, "expected_identity")
    _require(_name(expected.volume_name) and _uid(expected.volume_uid)
             and expected.namespace == "longhorn-system"
             and _name(expected.original_volume_handle) and _uid(expected.original_volume_uid)
             and expected.volume_name != expected.original_volume_handle
             and expected.volume_uid != expected.original_volume_uid
             and _name(backup.name) and backup.namespace == expected.namespace
             and _uid(backup.uid) and _text(backup.resource_version, 256)
             and expected.source_size_bytes == SIZE_BYTES, "expected_identity")
    _require(_text(expected.backup_url, 1024), "source_url")
    try:
        parts = urlsplit(expected.backup_url)
        query = parse_qs(parts.query, strict_parsing=True, keep_blank_values=True,
                         max_num_fields=2)
    except ValueError:
        raise RestoreTransitionRefused("source_url") from None
    _require(expected.backup_url.startswith("cifs://") and parts.scheme == "cifs"
             and parts.netloc == NAS_HOST and parts.path == NAS_PATH
             and not parts.fragment and "#" not in expected.backup_url
             and query == {"backup": [backup.name], "volume": [expected.original_volume_handle]},
             "source_url")


def _status(status, index):
    status = _mapping(status, set(), {"restoreInitiated", "restoreRequired", "conditions",
                                    "state", "robustness", "isStandby"}, "status_shape", index)
    if "state" in status:
        _require(status["state"] in ("", "creating", "attached", "detached", "attaching",
                                      "detaching", "deleting"), "volume_state", index)
        _require(status["state"] != "deleting", "volume_state", index)
    if "robustness" in status:
        _require(status["robustness"] in ("", "unknown", "healthy", "degraded"),
                 "volume_robustness", index)
    if "isStandby" in status:
        _require(status["isStandby"] is False, "volume_standby", index)
    conditions = status.get("conditions", [])
    # The installed nullable array may be null before controller initialization.
    if conditions is None:
        conditions = []
    _require(type(conditions) is list and len(conditions) <= MAX_CONDITIONS,
             "conditions_shape", index)
    seen = set()
    for condition in conditions:
        _mapping(condition, {"type", "status"},
                 {"reason", "message", "lastProbeTime", "lastTransitionTime"},
                 "conditions_shape", index)
        kind = condition["type"]
        _require(_text(kind, 128) and kind not in seen
                 and condition["status"] in ("True", "False", "Unknown"),
                 "conditions_shape", index)
        seen.add(kind)
        for key in ("reason", "message", "lastProbeTime", "lastTransitionTime"):
            if key in condition:
                _require(type(condition[key]) is str and len(condition[key]) <= 4096,
                         "conditions_shape", index)
        # Do not return or copy reason/message. Other controller/data gates are pending.
        _require(not (kind == "Restore" and condition.get("reason") == "RestoreFailure"),
                 "restore_failure", index)
    first, second = "restoreInitiated" in status, "restoreRequired" in status
    _require(first == second, "restore_flags", index)
    if not first:
        return None
    _require(type(status["restoreInitiated"]) is bool
             and type(status["restoreRequired"]) is bool, "restore_flags", index)
    return (status["restoreInitiated"], status["restoreRequired"])


def evaluate_restore_transition(expected, events, *, watch_started_before_create,
                                longhorn_version, api_version):
    """Evaluate ordered, closed projections; no replay, mutation or persistence.

    A true prerequisite flag is caller-supplied, not proof of durable watch startup
    or continuity. Never use this return value alone to authorize a holder or deploy.
    """
    _require(watch_started_before_create is True, "watch_prerequisite")
    _require(longhorn_version == LONGHORN_VERSION and api_version == API_VERSION,
             "schema_scope")
    _expected(expected)
    _require(type(events) in (list, tuple) and 1 <= len(events) <= MAX_EVENTS, "event_bound")
    initialized = completed = last = None
    seen_rvs = set()
    for index, event in enumerate(events):
        _mapping(event, {"type", "object"}, set(), "event_shape", index)
        event_type = event["type"]
        _require(event_type in ("ADDED", "MODIFIED", "BOOKMARK"), "watch_discontinuity", index)
        obj = _mapping(event["object"], {"apiVersion", "kind", "metadata"},
                       set() if event_type == "BOOKMARK" else {"spec", "status"},
                       "object_shape", index)
        _require(obj["apiVersion"] == API_VERSION and obj["kind"] == "Volume", "schema_scope", index)
        if event_type == "BOOKMARK":
            meta = _mapping(obj["metadata"], {"resourceVersion"}, set(), "bookmark_shape", index)
            _require(_text(meta["resourceVersion"], 256), "resource_version", index)
            # Bookmarks are continuity metadata, never a Volume transition witness.
            continue
        meta = _mapping(obj["metadata"], {"name", "namespace", "uid", "resourceVersion"},
                        {"deletionTimestamp"}, "identity_shape", index)
        _require(meta["name"] == expected.volume_name and meta["namespace"] == expected.namespace
                 and meta["uid"] == expected.volume_uid, "identity_drift", index)
        _require(meta.get("deletionTimestamp") is None, "volume_deleted", index)
        rv = meta["resourceVersion"]
        _require(_text(rv, 256) and rv not in seen_rvs, "resource_version", index)
        seen_rvs.add(rv)
        last = rv
        spec = _mapping(obj.get("spec"), {"fromBackup", "encrypted", "numberOfReplicas",
                                            "size", "dataEngine", "Standby"}, set(), "spec_shape", index)
        _require(spec["fromBackup"] == expected.backup_url and spec["encrypted"] is True
                 and type(spec["numberOfReplicas"]) is int and spec["numberOfReplicas"] == 2
                 and spec["size"] == SIZE_BYTES and spec["dataEngine"] == "v1"
                 and spec["Standby"] is False, "spec_drift", index)
        flags = _status(obj.get("status", {}), index)
        if initialized is None:
            if flags is None or flags == (False, False):
                continue
            _require(flags == (True, True), "restore_transition", index)
            initialized = rv
        elif completed is None:
            _require(flags in ((True, True), (True, False)), "restore_regression", index)
            if flags == (True, False):
                completed = rv
        else:
            _require(flags == (True, False), "restore_regression", index)
    _require(initialized is not None and completed is not None, "completion_unobserved")
    return RestoreTransition(expected.volume_name, expected.volume_uid, expected.namespace,
                             expected.backup, expected.original_volume_uid,
                             expected.original_volume_handle, initialized, completed, last, len(events))
