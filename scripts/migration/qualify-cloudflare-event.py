"""Correlate a single Cloudflare Security Event to an independently observed edge request."""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import http.client
import ipaddress
import json
import os
import re
import sys

SCHEMA = """query {
  __type(name: "FirewallEventsAdaptiveFilter_InputObject") {
    inputFields { name }
  }
}"""
EVENTS = """query FindEdgeEvent($zone: string, $filter: FirewallEventsAdaptiveFilter_InputObject) {
  viewer {
    zones(filter: { zoneTag: $zone }) {
      firewallEventsAdaptive(filter: $filter, limit: 10, orderBy: [datetime_DESC]) {
        rayName
        clientIP
        clientRequestHTTPHost
        clientRequestPath
        datetime
        action
        source
      }
    }
  }
}"""
LIMIT = 128 * 1024


def graphql(token, query, variables=None):
    request = json.dumps({"query": query, "variables": variables or {}})
    with closing(http.client.HTTPSConnection("api.cloudflare.com", timeout=10)) as connection:
        connection.request("POST", "/client/v4/graphql", request, {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Cloudflare Analytics returned HTTP {response.status}.")
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("The response exceeded the correlation size limit.")
    document = json.loads(raw)
    if document.get("errors") or not isinstance(document.get("data"), dict):
        raise ValueError("Cloudflare rejected the Analytics query or this dataset is unavailable.")
    return document["data"]


def parse_time(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("Supply a timestamp with an explicit UTC offset.")
    return result.astimezone(timezone.utc)


def utc(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def correlate(query, zone, ray, observed, address, host, path):
    # Never downgrade to matching by time or address alone if Ray filtering is unavailable.
    input_type = query(SCHEMA).get("__type")
    if not input_type or "rayName" not in {field["name"] for field in input_type["inputFields"]}:
        raise ValueError("The zone's Analytics schema does not expose exact Ray filtering. Use Security Events.")
    start, end = observed - timedelta(seconds=30), observed + timedelta(seconds=30)
    data = query(EVENTS, {"zone": zone, "filter": {
        "rayName": ray, "datetime_geq": utc(start), "datetime_leq": utc(end),
    }})
    zones = data["viewer"]["zones"]
    if len(zones) != 1:
        raise ValueError("The token could not read the exact requested Cloudflare zone.")
    matches = []
    for event in zones[0]["firewallEventsAdaptive"]:
        if event["rayName"].lower() != ray:
            raise ValueError("Cloudflare returned an event for a different Ray ID.")
        if (event["clientRequestHTTPHost"].lower() != host or event["clientRequestPath"] != path
                or not start <= parse_time(event["datetime"]) <= end):
            raise ValueError("An event's host, path or time did not match the probe.")
        if ipaddress.ip_address(event["clientIP"]) != address:
            raise ValueError("The Ray matched, but Cloudflare recorded a different client IP.")
        matches.append({"action": event["action"], "source": event["source"], "time": event["datetime"]})
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", required=True, help="Cloudflare zone ID")
    parser.add_argument("--ray", required=True, help="CF-Ray response header")
    parser.add_argument("--observed-at", required=True, type=parse_time)
    parser.add_argument("--client-ip", required=True, type=ipaddress.ip_address)
    parser.add_argument("--host", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    token = os.environ.get("BRANCONET_CF_ANALYTICS_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,256}", token):
        raise ValueError("Supply the dedicated Cloudflare Analytics token through the private environment.")
    zone, host = args.zone.lower(), args.host.lower()
    ray, _, _ = args.ray.lower().partition("-")
    if not re.fullmatch(r"[a-f0-9]{32}", zone) or not re.fullmatch(r"[a-f0-9]{16}", ray):
        raise ValueError("Invalid zone ID or Ray ID.")
    if (not re.fullmatch(r"[a-z0-9.-]{1,253}", host) or not args.path.startswith("/")
            or "?" in args.path or "#" in args.path or len(args.path) > 1024):
        raise ValueError("Supply a hostname and path without query or fragment.")

    def query(document, variables=None):
        return graphql(token, document, variables)

    matches = correlate(query, zone, ray, args.observed_at, args.client_ip, host, args.path)
    if not matches:
        raise ValueError("No matching Security Event was returned. Sampling or ingestion delay can hide an event.")
    print(json.dumps({"correlated": True, "events": matches}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, http.client.HTTPException) as error:
        print(str(error) if type(error) is ValueError else "Cloudflare event verification could not complete.",
              file=sys.stderr)
        sys.exit(1)
