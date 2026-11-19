"""Validate operator-owned run profiles and expiring caller grants.

The policy is the only place that decides which image may run, which
Kubernetes Secret keys it receives, and which local user may ask for it.
Parsing is strict so that a typo cannot silently widen access: every object
has a fixed key set, identifiers are pattern-checked and limits are enforced
before anything touches the cluster or the container runtime.
"""

import json
import os
import re
import stat
import time

# Identifiers. Kubernetes already enforces these grammar rules; repeating
# them here keeps a malformed operator file from reaching the API server.
PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,127}\Z")
RESOURCE_NAME = re.compile(r"[a-z0-9]([-a-z0-9]{0,251}[a-z0-9])?\Z")
SECRET_KEY = re.compile(r"[-._a-zA-Z0-9]{1,253}\Z")
DIGEST = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*@sha256:[0-9a-f]{64}\Z")

# Bounds. These are contract limits from 02_DOMAIN_AND_PRODUCT_CONTRACTS.md;
# changing them requires a policy revision, not a caller argument.
MAX_BINDINGS = 16
MAX_SELECTED_BYTES = 64 * 1024
MAX_FILE_BYTES = 64 * 1024
MAX_POLICY_BYTES = 32 * 1024
MIN_TIMEOUT_SECONDS = 5
MAX_TIMEOUT_SECONDS = 120
MIN_GRANT_SECONDS = 60
MAX_GRANT_SECONDS = 24 * 3600

PROFILE_FIELDS = {"id", "description", "image_digest", "bindings", "probe",
                  "network", "timeout_seconds", "runtime_mode", "live_approved",
                  "command"}
BINDING_FIELDS = {"namespace", "secret", "key", "delivery", "destination"}
PROBE_FIELDS = {"kind", "port", "path", "status", "seconds"}

# Fixed result vocabulary. The agent sees these values, never free text
# assembled from policy or cluster data.
RESULTS = ("passed", "invalid_request", "not_authorized", "busy",
           "credential_unavailable", "runtime_unavailable", "check_failed",
           "timed_out", "cleanup_required")


class PolicyError(Exception):
    """The operator policy file is unreadable or does not match the schema."""


def read_private(path, limit):
    """Read a small file that only this user may modify.

    Refuses symlinks, group/world-accessible files and files owned by
    somebody else, so a caller cannot influence the runner by editing a
    shared path.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise PolicyError("policy files must be private and owned by the runner")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise PolicyError("policy file is too large")
    return data


def _text(value, pattern, what):
    """Return a validated identifier or raise a fixed policy error."""
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise PolicyError(f"invalid {what}")
    return value


def _integer(value, low, high, what):
    if type(value) is not int or not low <= value <= high:
        raise PolicyError(f"invalid {what}")
    return value


def _exact_keys(item, allowed, what):
    if not isinstance(item, dict) or not set(item) <= allowed:
        raise PolicyError(f"unknown {what} field")


def _binding(item):
    """Validate one Secret-to-destination mapping."""
    _exact_keys(item, BINDING_FIELDS, "binding")
    if set(item) != BINDING_FIELDS:
        raise PolicyError("every binding needs namespace, secret, key, delivery, destination")
    binding = {
        "namespace": _text(item["namespace"], RESOURCE_NAME, "namespace"),
        "secret": _text(item["secret"], RESOURCE_NAME, "secret"),
        "key": _text(item["key"], SECRET_KEY, "secret key"),
        "delivery": item["delivery"],
        "destination": item["destination"],
    }
    if binding["delivery"] == "file":
        # Files land in a runner-owned directory and are mounted read-only,
        # so only a plain file name is acceptable.
        _text(binding["destination"], re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z"),
              "file destination")
    elif binding["delivery"] == "env":
        binding["destination"] = _text(binding["destination"], ENV_NAME, "environment name")
    else:
        raise PolicyError("delivery must be file or env")
    return binding


def _probe(item):
    """Validate the fixed readiness check the runner performs."""
    _exact_keys(item, PROBE_FIELDS, "probe")
    kind = item.get("kind")
    if kind == "running":
        # Used with an isolated network: the check is that the approved
        # process stays up for a short, fixed period without exiting.
        if set(item) != {"kind", "seconds"}:
            raise PolicyError("running probes take only seconds")
        return {"kind": "running",
                "seconds": _integer(item["seconds"], 1, 30, "probe seconds")}
    if kind == "tcp":
        if set(item) != {"kind", "port"}:
            raise PolicyError("tcp probes take only a port")
        return {"kind": "tcp", "port": _integer(item["port"], 1, 65535, "probe port")}
    if kind == "http":
        allowed = {"kind", "port", "path", "status"}
        if not {"kind", "port", "path"} <= set(item) <= allowed:
            raise PolicyError("http probes need a port and path")
        path = item["path"]
        if not isinstance(path, str) or not path.startswith("/") or len(path) > 256:
            raise PolicyError("invalid probe path")
        status = item.get("status", [200])
        if (not isinstance(status, list) or not status or len(status) > 8
                or any(type(code) is not int or not 200 <= code <= 299 for code in status)):
            raise PolicyError("http probe status must be 2xx codes")
        return {"kind": "http", "port": _integer(item["port"], 1, 65535, "probe port"),
                "path": path, "status": status}
    raise PolicyError("probe kind must be running, tcp or http")


def _profile(item):
    """Validate one run profile."""
    _exact_keys(item, PROFILE_FIELDS, "profile")
    required = {"id", "image_digest", "bindings", "probe"}
    if not required <= set(item):
        raise PolicyError("a profile needs id, image_digest, bindings and probe")
    profile = {
        "id": _text(item["id"], PROFILE_ID, "profile id"),
        "description": item.get("description", ""),
        "image_digest": _text(item["image_digest"], DIGEST, "image digest"),
        "bindings": item["bindings"],
        "probe": _probe(item["probe"]),
        "network": item.get("network", "none"),
        "timeout_seconds": _integer(item.get("timeout_seconds", 60),
                                    MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS, "timeout"),
        "runtime_mode": item.get("runtime_mode", "test"),
        "live_approved": item.get("live_approved", False),
        "command": item.get("command"),
    }
    if not isinstance(profile["description"], str) or len(profile["description"]) > 200:
        raise PolicyError("invalid description")
    if profile["network"] not in ("none", "bridge"):
        raise PolicyError("network must be none or bridge")
    if profile["runtime_mode"] not in ("test", "live"):
        raise PolicyError("runtime_mode must be test or live")
    if type(profile["live_approved"]) is not bool:
        raise PolicyError("live_approved must be a boolean")
    command = profile["command"]
    if command is not None:
        # An operator may pin a short command for an image without its own
        # long-running entrypoint. It is part of the reviewed policy and is
        # never supplied by a caller.
        if (not isinstance(command, list) or not 1 <= len(command) <= 8
                or not all(isinstance(part, str) and 1 <= len(part) <= 512
                           and "\x00" not in part for part in command)
                or sum(map(len, command)) > 4096):
            raise PolicyError("command must be 1-8 strings of at most 512 characters")
    if not isinstance(profile["bindings"], list) or not 1 <= len(profile["bindings"]) <= MAX_BINDINGS:
        raise PolicyError("a profile needs 1-16 bindings")
    profile["bindings"] = [_binding(binding) for binding in profile["bindings"]]
    # Network probes reach the container's private address, which only
    # exists on a bridge network; an isolated run uses the running check.
    if profile["probe"]["kind"] in ("tcp", "http") and profile["network"] != "bridge":
        raise PolicyError("tcp/http probes need network bridge")
    # One destination may be written once. Two bindings aiming at the same
    # file or variable would make the delivered value depend on order.
    seen = {(b["delivery"], b["destination"]) for b in profile["bindings"]}
    if len(seen) != len(profile["bindings"]):
        raise PolicyError("duplicate delivery destination")
    return profile


def load_profiles(data):
    """Parse the profile document into id -> validated profile."""
    try:
        document = json.loads(data)
    except ValueError:
        raise PolicyError("policy is not valid JSON") from None
    if not isinstance(document, dict) or set(document) != {"version", "profiles"}:
        raise PolicyError("policy must contain version and profiles only")
    if document["version"] != 1 or not isinstance(document["profiles"], list):
        raise PolicyError("unsupported policy version")
    profiles = {}
    for item in document["profiles"]:
        profile = _profile(item)
        if profile["id"] in profiles:
            raise PolicyError("duplicate profile id")
        profiles[profile["id"]] = profile
    return profiles


def load_grants(data, now=None):
    """Parse the grant document into validated (uid, profile, expiry) rows."""
    now = time.time() if now is None else now
    try:
        document = json.loads(data)
    except ValueError:
        raise PolicyError("grants are not valid JSON") from None
    if not isinstance(document, dict) or set(document) != {"version", "grants"}:
        raise PolicyError("grants must contain version and grants only")
    if document["version"] != 1 or not isinstance(document["grants"], list):
        raise PolicyError("unsupported grants version")
    grants = []
    for item in document["grants"]:
        if not isinstance(item, dict) or set(item) != {"uid", "profile", "expires_at"}:
            raise PolicyError("each grant needs uid, profile and expires_at only")
        uid = _integer(item["uid"], 1, 2 ** 31 - 1, "grant uid")
        profile = _text(item["profile"], PROFILE_ID, "grant profile")
        expires_at = item["expires_at"]
        if type(expires_at) not in (int, float) or not now + MIN_GRANT_SECONDS <= expires_at <= now + MAX_GRANT_SECONDS:
            raise PolicyError("grant expiry must be 1 minute to 24 hours from now")
        if any(row[0] == uid and row[1] == profile for row in grants):
            raise PolicyError("duplicate grant")
        grants.append((uid, profile, float(expires_at)))
    return grants


def has_grant(grants, uid, profile_id, now=None):
    """Return True when this uid holds a live grant for this profile."""
    now = time.time() if now is None else now
    return any(grant_uid == uid and granted == profile_id and now < expires_at
               for grant_uid, granted, expires_at in grants)


def authorize(profiles, grants, uid, profile_id, now=None):
    """Resolve a request to (profile, None) or (None, fixed reason).

    An unknown profile, a missing/expired grant and an unapproved live
    profile all return the same reason so the caller cannot use this tool
    to enumerate profiles.
    """
    now = time.time() if now is None else now
    profile = profiles.get(profile_id) if isinstance(profile_id, str) else None
    if profile is None or not has_grant(grants, uid, profile_id, now):
        return None, "not_authorized"
    if profile["runtime_mode"] == "live" and not profile["live_approved"]:
        return None, "not_authorized"
    return profile, None
