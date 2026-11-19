"""Plex library and health tools on the floating Plex HTTPS endpoint."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_shared"))
from read_only_media import credential, describe, get, select, serve

ENDPOINT = ("192-168-0-254.d1828a6e2c3d4b5ea3f4f0488e4ea297.plex.direct", "192.168.0.254", 32400, None)


def media(path, *, query=None, authenticated=True):
    headers = {}
    if authenticated:
        headers = {"X-Plex-Token": credential(HERE / ".env", "PLEX_TOKEN"),
                   "X-Plex-Client-Identifier": "branconet-plex-mcp"}
    return get(ENDPOINT, path, headers=headers, query=query)["MediaContainer"]


def health():
    return select(media("/identity", authenticated=False), "claimed", "version", "apiVersion")


def libraries():
    return [select(item, "key", "type", "title") for item in media("/library/sections").get("Directory", [])[:40]]


def search(query):
    result = media("/hubs/search", query={"query": query, "limit": 10})
    matches = []
    for hub in result.get("Hub", [])[:20]:
        for item in hub.get("Metadata", [])[:10]:
            summary = select(item, "ratingKey", "type", "title", "year", "grandparentTitle")
            if summary and summary not in matches:
                matches.append(summary)
    return matches[:10]


if __name__ == "__main__":
    serve("plex-inventory", [
        (describe("plex_health", "Read the floating Plex server version and claim status."), health),
        (describe("plex_libraries", "List up to 40 Plex libraries without paths or account data."), libraries),
        (describe("plex_search", "Find up to 10 Plex library items by title.", search=True), search),
    ], "Read-only Plex tools on the floating HTTPS endpoint: server health, library list "
       "and title search. No paths, account data or changes.")
