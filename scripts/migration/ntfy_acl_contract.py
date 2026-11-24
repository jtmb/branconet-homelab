"""Check externally supplied ntfy provisioning material without emitting it.

No generation, Kubernetes write or ntfy invocation. Syntactic checks are not
effective ACL tests. The private candidate supplies the fixed grants separately.
"""
import json
import re
import sys

USERS = ("bortus-monitor-publisher", "bortus-watchdog-publisher", "bortus-subscriber")
GRANTS = (
    ("bortus-monitor-publisher", "bortus-certificates", "write-only"),
    ("bortus-watchdog-publisher", "bortus-monitor-health", "write-only"),
    ("bortus-subscriber", "bortus-certificates", "read-only"),
    ("bortus-subscriber", "bortus-monitor-health", "read-only"),
)


def validate_material(value):
    try:
        if not isinstance(value, dict) or set(value) != {"users", "tokens"}:
            raise ValueError()
        users, tokens, hashes, values = {}, {}, set(), set()
        for item in value["users"].split(","):
            name, hashed, role = item.split(":")
            if (name not in USERS or name in users or role != "user" or hashed in hashes or
                    not re.fullmatch(r"\$2[aby]\$(?:10|11|12|13|14)\$[./A-Za-z0-9]{53}", hashed)):
                raise ValueError()
            users[name] = True
            hashes.add(hashed)
        for item in value["tokens"].split(","):
            name, token = item.split(":")
            if (name not in USERS or name in tokens or token in values or
                    not re.fullmatch(r"tk_[-_A-Za-z0-9]{29}", token)):
                raise ValueError()
            tokens[name] = True
            values.add(token)
        if set(users) != set(USERS) or set(tokens) != set(USERS):
            raise ValueError()
    except (ValueError, TypeError, AttributeError, KeyError):
        raise ValueError("ntfy_provisioning_invalid") from None
    return {"validSyntax": True, "ordinaryUsers": 3, "fixedGrants": len(GRANTS),
            "effectiveACLVerified": False}


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise ValueError()
        print(json.dumps(validate_material(json.loads(raw))), flush=True)
    except Exception:
        print(json.dumps({"validSyntax": False, "reason": "ntfy_provisioning_invalid"}), flush=True)
        raise SystemExit(1)
