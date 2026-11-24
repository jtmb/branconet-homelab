"""Read-only Seerr request proposals with an exact, short-lived review digest."""
import hashlib
import json
import secrets
import time

from read_only_media import MediaError

MAX_ID = 2_147_483_647
LIFETIME = 300
REQUEST_KEYS = {"media_type", "tmdb_id", "seasons"}


def digest(proposal):
    encoded = json.dumps(proposal, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def arguments(value):
    if not isinstance(value, dict) or not {"media_type", "tmdb_id"} <= value.keys() <= REQUEST_KEYS:
        raise MediaError("Supply a media type, TMDB ID and, for a series, explicit seasons.")
    kind, identifier = value["media_type"], value["tmdb_id"]
    if kind not in ("movie", "tv") or type(identifier) is not int or not 1 <= identifier <= MAX_ID:
        raise MediaError("Use a movie or TV TMDB ID.")
    seasons = value.get("seasons", [])
    if (not isinstance(seasons, list) or len(seasons) > 20
            or any(type(season) is not int or not 1 <= season <= 1000 for season in seasons)
            or len(set(seasons)) != len(seasons)
            or (kind == "movie" and "seasons" in value) or (kind == "tv" and not seasons)):
        raise MediaError("For TV, select 1 to 20 distinct, positive season numbers. Movies take no seasons.")
    result = {"mediaType": kind, "mediaId": identifier, "is4k": False}
    if kind == "tv":
        result["seasons"] = sorted(seasons)
    return result


def media_snapshot(read, request):
    kind, identifier = request["mediaType"], request["mediaId"]
    details = read(f"/{kind}/{identifier}")
    if details.get("id") != identifier:
        raise MediaError("Seerr returned a different title.")
    title = details.get("title" if kind == "movie" else "name")
    date = details.get("releaseDate" if kind == "movie" else "firstAirDate") or ""
    if not isinstance(title, str) or not 1 <= len(title) <= 300 or not isinstance(date, str) or len(date) > 20:
        raise MediaError("Seerr returned invalid title details.")
    media = details.get("mediaInfo") or {}
    status = media.get("status", 1)
    if type(status) is not int or status in (5, 6) or status not in (1, 2, 3, 4, 7):
        raise MediaError("The title is already available, blocked or has an unsupported status.")
    active = [row for row in media.get("requests", [])
              if not row["is4k"] and row["status"] not in (3, 5)]
    snapshot = {"title": title, "release_date": date, "status": status}
    if kind == "movie":
        if status not in (1, 7) or active:
            raise MediaError("The movie is already requested or being processed.")
    else:
        seasons = set(request["seasons"])
        available_to_request = {row["seasonNumber"] for row in details["seasons"]
                                if type(row.get("episodeCount")) is int and row["episodeCount"] > 0}
        busy = {row["seasonNumber"] for row in media.get("seasons", []) if row["status"] not in (1, 7)}
        busy.update(row["seasonNumber"] for item in active for row in item["seasons"])
        if not seasons <= available_to_request or seasons & busy:
            raise MediaError("A selected season does not exist, is available or has an existing request.")
        snapshot["seasons"] = sorted(seasons)
    return snapshot


def prepare(read, target, request):
    snapshot = media_snapshot(read, request)
    now = int(time.time())
    plan = {"target": target, "operation": "submit_pending_request", "request": request,
            "media": snapshot, "request_id": secrets.token_hex(16), "issued_at": now,
            "expires_at": now + LIFETIME}
    return {"proposal": plan, "approval_sha256": digest(plan), "applied": False}
