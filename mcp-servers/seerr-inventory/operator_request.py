"""Operator-only submission of an exact pending Seerr request."""
import argparse
import base64
from contextlib import closing, contextmanager
import getpass
import hmac
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time

from server import ENDPOINT, TARGET
from read_only_media import FixedHTTPS, LIMIT, MediaError
from request_plan import arguments, digest, LIFETIME, media_snapshot

REQUEST = 32
REQUEST_MOVIE = 262144
REQUEST_TV = 524288


class SeerrStatus(MediaError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Seerr returned HTTP {status}.")


def transport(method, path, *, body=None, cookie=None, expected=200):
    headers = {"Accept": "application/json", "Origin": TARGET}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    with closing(FixedHTTPS(*ENDPOINT)) as connection:
        connection.request(method, "/api/v1" + path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        if response.status != expected:
            raise SeerrStatus(response.status)
        data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise MediaError("Seerr response exceeded the size limit.")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise MediaError("Seerr returned an unexpected result.")
        return result, [value for name, value in response.getheaders() if name.lower() == "set-cookie"]


@contextmanager
def session(email, password):
    _, headers = transport("POST", "/auth/local", body={"email": email, "password": password})
    cookies = SimpleCookie()
    for header in headers:
        cookies.load(header)
    morsel = cookies.get("connect.sid")
    if morsel is None or not re.fullmatch(r"[A-Za-z0-9%+_.:/=-]{1,512}", morsel.coded_value):
        raise MediaError("Seerr did not return a valid session cookie.")
    cookie = "connect.sid=" + morsel.coded_value
    try:
        yield cookie
    finally:
        try:
            transport("POST", "/auth/logout", body={}, cookie=cookie)
        except (MediaError, OSError, ValueError, http.client.HTTPException):
            print("Could not confirm cleanup of the short-lived Seerr session.", file=sys.stderr)


def validate(proposal, approved):
    if not isinstance(proposal, dict) or set(proposal) != {
        "target", "operation", "request", "media", "request_id", "issued_at", "expires_at",
    }:
        raise MediaError("Unexpected request proposal fields.")
    if (not re.fullmatch(r"[a-f0-9]{64}", approved) or
            not hmac.compare_digest(digest(proposal), approved)):
        raise MediaError("The proposal differs from the approved digest.")
    if proposal["target"] != TARGET or proposal["operation"] != "submit_pending_request":
        raise MediaError("The proposal targets a different Seerr operation.")
    if not isinstance(proposal["request_id"], str) or not re.fullmatch(r"[a-f0-9]{32}", proposal["request_id"]):
        raise MediaError("Invalid proposal identifier.")
    start, end = proposal["issued_at"], proposal["expires_at"]
    if type(start) is not int or type(end) is not int or end - start != LIFETIME or not start <= int(time.time()) < end:
        raise MediaError("The proposal is outside its five-minute approval window.")
    request = proposal["request"]
    if not isinstance(request, dict):
        raise MediaError("Invalid approved request.")
    choices = {"media_type": request.get("mediaType"), "tmdb_id": request.get("mediaId")}
    if "seasons" in request:
        choices["seasons"] = request["seasons"]
    validated = arguments(choices)
    if validated != request or request.get("is4k") is not False:
        raise MediaError("Only standard requests without overrides are supported.")
    return validated


def submit(ledger, proposal, approved, cookie, send=transport):
    request = validate(proposal, approved)
    def read(path):
        return send("GET", path, cookie=cookie)[0]
    who = read("/auth/me")
    requester, permissions = who.get("id"), who.get("permissions")
    allowed = REQUEST | REQUEST_MOVIE | REQUEST_TV
    required = REQUEST | (REQUEST_MOVIE if request["mediaType"] == "movie" else REQUEST_TV)
    if (type(requester) is not int or requester <= 0 or type(permissions) is not int
            or permissions & ~allowed or not permissions & required):
        raise MediaError("Use a dedicated Seerr account with request-only permissions and no auto-approval.")
    if media_snapshot(read, request) != proposal["media"]:
        raise MediaError("The title or availability changed. Prepare a new proposal.")
    ticket = proposal["request_id"]
    scope = f"{TARGET}/{request['mediaType']}/{request['mediaId']}"
    try:
        with ledger:
            ledger.execute("BEGIN IMMEDIATE")
            ledger.execute("CREATE TABLE IF NOT EXISTS submissions "
                           "(ticket TEXT PRIMARY KEY, scope TEXT NOT NULL, status TEXT NOT NULL, request_id INTEGER)")
            if ledger.execute("SELECT 1 FROM submissions WHERE scope=? AND status='unconfirmed'", (scope,)).fetchone():
                raise MediaError("An earlier submission for this title is unconfirmed. Reconcile it in Seerr before retrying.")
            validate(proposal, approved)
            ledger.execute("INSERT INTO submissions VALUES (?, ?, 'unconfirmed', NULL)", (ticket, scope))
    except sqlite3.IntegrityError as error:
        raise MediaError("This approval has already been consumed.") from error

    try:
        created, _ = send("POST", "/request", body=request, cookie=cookie, expected=201)
        request_id = created.get("id")
        if type(request_id) is not int or request_id <= 0:
            raise MediaError("The created request ID is missing.")
        saved = read(f"/request/{request_id}")
        media = saved["media"]
        exact = (saved["id"] == request_id and saved["status"] == 1 and saved["is4k"] is False
                 and saved["type"] == request["mediaType"] and media["tmdbId"] == request["mediaId"]
                 and saved["requestedBy"]["id"] == requester
                 and sorted(row["seasonNumber"] for row in saved["seasons"]) == request.get("seasons", []))
        if not exact:
            raise MediaError("The saved request did not match the approved pending request.")
    except SeerrStatus as error:
        if error.status in (400, 401, 403, 409, 422) and "created" not in locals():
            with ledger:
                ledger.execute("UPDATE submissions SET status='rejected' WHERE ticket=?", (ticket,))
            raise
        raise MediaError("Seerr submission is unconfirmed. Check the request queue before retrying.") from None
    except (MediaError, OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
        raise MediaError("Seerr submission is unconfirmed. Check the request queue before retrying.") from None

    with ledger:
        ledger.execute("UPDATE submissions SET status='verified', request_id=? WHERE ticket=?", (request_id, ticket))
    return {"request_id": request_id, "status": "pending", "media_type": request["mediaType"],
            "tmdb_id": request["mediaId"], "seasons": request.get("seasons", [])}


def private_ledger(path):
    info = path.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise MediaError("The ledger directory must be private and owned by the operator.")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise MediaError("The submission ledger must be a private regular file.")
    finally:
        os.close(fd)
    return sqlite3.connect(path)


def native_requester(fd):
    if fd < 3 or not stat.S_ISFIFO(os.fstat(fd).st_mode):
        raise MediaError("Use a separate pipe for the native Seerr credential.")
    with os.fdopen(fd, "rb", closefd=False) as stream:
        raw = stream.read(4097)
    try:
        if len(raw) > 4096:
            raise ValueError()
        source = json.loads(raw)
        metadata = source["metadata"]
        data = source["data"]
        if (source["kind"] != "Secret" or source["type"] != "Opaque"
                or metadata["namespace"] != "plex" or metadata["name"] != "seerr-mcp-requester"
                or metadata["labels"]["app.kubernetes.io/part-of"] != "seerr"
                or set(data) != {"email", "password"}):
            raise ValueError()
        email, password = (base64.b64decode(data[key], validate=True).decode()
                           for key in ("email", "password"))
        if email != "seerr-mcp-requester@branconet.invalid" or not 40 <= len(password) <= 256:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as error:
        raise MediaError("The pipe did not contain the dedicated Seerr credential.") from error
    return email, password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--credential-fd", type=int, help="Separate pipe containing the native requester Secret")
    opts = parser.parse_args()
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise MediaError("Proposal input is too large.")
    proposal = json.loads(raw)
    validate(proposal, opts.approval_sha256)
    if opts.credential_fd is None:
        with open("/dev/tty", "r+") as tty:
            email = getpass.getpass("Seerr requester email: ", stream=tty)
            password = getpass.getpass("Seerr requester password: ", stream=tty)
    else:
        email, password = native_requester(opts.credential_fd)
    with closing(private_ledger(opts.ledger)) as ledger, session(email, password) as cookie:
        result = submit(ledger, proposal, opts.approval_sha256, cookie)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (MediaError, OSError, ValueError, sqlite3.Error, http.client.HTTPException) as error:
        raise SystemExit(str(error) if isinstance(error, MediaError) else "Operator submission could not be confirmed.") from None
