"""Bind a Netgear DHCP proposal to separate, single-use operator approval."""
import hashlib
import hmac
import ipaddress
import json
import secrets
import sqlite3
import time

SETTING = "dhcp_pool_end"
LIFETIME = 300


class ApprovalError(ValueError):
    """The request failed an approval boundary."""


def fingerprint(document):
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def prepare(target, current, new_end):
    issued_at = int(time.time())
    return {
        "request_id": secrets.token_hex(16),
        "target": target,
        "setting": SETTING,
        "before": dict(current),
        "after": {"start": current["start"], "end": new_end},
        "issued_at": issued_at,
        "expires_at": issued_at + LIFETIME,
    }


def consume(ledger, proposal, approved_digest, target, read_pool):
    """Admit the exact operator-approved request once. This does not write to a router."""
    if not isinstance(proposal, dict) or set(proposal) != {
        "request_id", "target", "setting", "before", "after", "issued_at", "expires_at",
    }:
        raise ApprovalError("Unexpected proposal fields.")
    if not isinstance(approved_digest, str) or not hmac.compare_digest(
        fingerprint(proposal).encode("ascii"), approved_digest.encode("utf-8")
    ):
        raise ApprovalError("The proposal does not match the separately approved digest.")
    request_id = proposal["request_id"]
    if not isinstance(request_id, str) or len(request_id) != 32 or not all(
        char in "0123456789abcdef" for char in request_id
    ):
        raise ApprovalError("Invalid proposal identifier.")
    if proposal["setting"] != SETTING or proposal["target"] != target:
        raise ApprovalError("The proposal does not match the pinned router and setting.")
    issued_at, expires_at = proposal["issued_at"], proposal["expires_at"]
    if (type(issued_at) is not int or type(expires_at) is not int
            or expires_at - issued_at != LIFETIME or not issued_at <= int(time.time()) < expires_at):
        raise ApprovalError("The approval is outside its five-minute window.")
    before, after = proposal["before"], proposal["after"]
    if any(not isinstance(pool, dict) or set(pool) != {"start", "end"} for pool in (before, after)):
        raise ApprovalError("Unexpected DHCP pool fields.")
    try:
        start, previous_end, next_end = (
            ipaddress.IPv4Address(value) for value in (before["start"], before["end"], after["end"])
        )
    except (ValueError, TypeError) as error:
        raise ApprovalError("Invalid DHCP pool bounds.") from error
    if (before["start"] != str(start) or before["end"] != str(previous_end)
            or after["start"] != str(start) or after["end"] != str(next_end)
            or not start <= next_end < previous_end):
        raise ApprovalError("Only the approved DHCP pool end can be reduced.")
    try:
        with ledger:
            ledger.execute("BEGIN IMMEDIATE")
            ledger.execute(
                "CREATE TABLE IF NOT EXISTS consumed (request_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)"
            )
            ledger.execute("INSERT INTO consumed VALUES (?, ?)", (request_id, expires_at))
            if read_pool() != before:
                raise ApprovalError("The router's current DHCP bounds differ from the approved proposal.")
            if not issued_at <= int(time.time()) < expires_at:
                raise ApprovalError("The approval expired before the router read completed.")
    except sqlite3.IntegrityError as error:
        raise ApprovalError("This approval has already been consumed.") from error
    return dict(after)
