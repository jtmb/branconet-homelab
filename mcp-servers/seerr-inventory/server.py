"""Seerr media search and request inventory through the private LAN ingress."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_shared"))
from read_only_media import credential, describe, get, select, serve
from request_plan import arguments, prepare

ENDPOINT = ("overseerr.branconet.lan", "192.168.0.252", 443, str(HERE / "lan-root-ca.pem"))


TARGET = "https://" + ENDPOINT[0]


def propose(request):
    return prepare(api, TARGET, request)


def api(path, *, query=None, authenticated=True):
    headers = {"X-Api-Key": credential(HERE / ".env", "SEERR_API_KEY")} if authenticated else {}
    return get(ENDPOINT, "/api/v1" + path, headers=headers, query=query)


def health():
    return select(api("/status", authenticated=False), "version", "updateAvailable")


def search(query):
    result = api("/search", query={"query": query})
    matches = []
    for item in result.get("results", []):
        if item.get("mediaType") not in ("movie", "tv"):
            continue
        summary = select(item, "id", "mediaType", "title", "name", "releaseDate", "firstAirDate")
        if isinstance(item.get("mediaInfo"), dict):
            summary.update(select(item["mediaInfo"], "status"))
        matches.append(summary)
        if len(matches) == 10:
            break
    return matches


def requests():
    result = api("/request", query={"take": 10, "sort": "added", "sortDirection": "desc"})
    items = []
    for item in result.get("results", [])[:10]:
        summary = select(item, "id", "type", "status", "is4k", "createdAt")
        if isinstance(item.get("media"), dict):
            summary["media"] = select(item["media"], "tmdbId", "mediaType", "status", "status4k")
        items.append(summary)
    return items


if __name__ == "__main__":
    serve("seerr-inventory", [
        (describe("seerr_health", "Read the LAN Seerr service version."), health),
        (describe("seerr_search", "Find up to 10 movies and shows without returning account data.", search=True), search),
        (describe("seerr_requests", "Read the latest 10 request statuses without requester information."), requests),
        ({"name": "seerr_propose_request",
          "description": "Review a standard movie request or explicit TV seasons without submitting anything.",
          "inputSchema": {"type": "object", "additionalProperties": False,
                          "properties": {"media_type": {"enum": ["movie", "tv"]},
                                         "tmdb_id": {"type": "integer"},
                                         "seasons": {"type": "array", "items": {"type": "integer"}}},
                          "required": ["media_type", "tmdb_id"]},
          "annotations": {"readOnlyHint": True, "openWorldHint": False}}, propose, arguments),
    ], "Read-only Seerr tools on the private LAN ingress: service health, title search, "
       "recent request status and an expiring request proposal. Nothing is submitted.")
