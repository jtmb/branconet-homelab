"""Render a loopback-only DNS fallback from chart-managed Pi-hole records."""
import argparse
from collections import defaultdict
import ipaddress
import json
import re
import sys

LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_BYTES = 64 * 1024


def name(value):
    if len(value) > 253 or not all(LABEL.fullmatch(label) for label in value.split(".")):
        raise ValueError("The record set contains an invalid DNS name.")
    return value


def records(data):
    addresses = defaultdict(set)
    aliases = {}
    for line in data["FTLCONF_dns_hosts"].splitlines():
        ip, host = line.split()
        addresses[name(host)].add(str(ipaddress.IPv4Address(ip)))
    for line in data["FTLCONF_dns_cnameRecords"].splitlines():
        alias, target = map(name, line.split(","))
        if alias in aliases or alias in addresses or target not in addresses:
            raise ValueError("An alias conflicts with another record or lacks a local target.")
        aliases[alias] = target
    if not addresses or not aliases:
        raise ValueError("The address and alias lists must both be present.")
    return addresses, aliases


def checked_upstreams(upstreams, port):
    if not 1024 <= port <= 65535:
        raise ValueError("Use an unprivileged loopback test port.")
    upstreams = sorted({str(ipaddress.IPv4Address(value)) for value in upstreams})
    if not upstreams or any(not ipaddress.IPv4Address(ip).is_global for ip in upstreams):
        raise ValueError("Specify direct upstreams that do not depend on LAN DNS.")
    return upstreams


def render(data, upstreams, port=10553):
    upstreams = checked_upstreams(upstreams, port)
    addresses, aliases = records(data)
    config = [
        "listen-address=127.0.0.1", "bind-interfaces", f"port={port}",
        "no-resolv", "no-hosts", "domain-needed", "bogus-priv", "stop-dns-rebind",
        "local=/local/", "local=/lan/", "cache-size=300", "log-facility=-",
    ]
    config += [f"server={ip}" for ip in upstreams]
    config += [f"host-record={host},{ip}" for host in sorted(addresses) for ip in sorted(addresses[host])]
    config += [f"cname={alias},{aliases[alias]}" for alias in sorted(aliases)]
    return "\n".join(config) + "\n"


def render_ftl(data, upstreams, port=10554):
    upstreams = checked_upstreams(upstreams, port)
    records(data)
    sections = {
        "dns": {
            "port": port, "listeningMode": "BIND", "interface": "lo", "upstreams": upstreams,
            "hosts": data["FTLCONF_dns_hosts"].splitlines(),
            "cnameRecords": data["FTLCONF_dns_cnameRecords"].splitlines(), "queryLogging": False,
        },
        "dns.blocking": {"active": True, "mode": "NULL"},
        "webserver": {"port": ""},
        "database": {"DBimport": False, "maxDBdays": 0},
        "ntp.sync": {"active": False},
        "ntp.ipv4": {"active": False},
        "ntp.ipv6": {"active": False},
    }
    return "\n".join(
        f"[{section}]\n" + "\n".join(f"{key} = {json.dumps(value)}" for key, value in values.items())
        for section, values in sections.items()
    ) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", action="append", required=True, help="Direct IPv4 DNS upstream")
    parser.add_argument("--engine", choices=("dnsmasq", "ftl"), default="dnsmasq")
    parser.add_argument("--port", type=int)
    options = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("The source DNS record set exceeds its size limit.")
    source = json.loads(raw)
    renderer = render_ftl if options.engine == "ftl" else render
    port = options.port if options.port is not None else (10554 if options.engine == "ftl" else 10553)
    sys.stdout.write(renderer(source["data"], options.upstream, port))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, TypeError, ValueError) as error:
        print(f"Unable to render the independent DNS fallback: {error}", file=sys.stderr)
        sys.exit(1)
