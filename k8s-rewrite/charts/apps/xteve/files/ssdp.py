"""Advertise the unchanged native xTeve descriptor to LAN SSDP clients."""
import argparse
import ipaddress
import os
import signal
import socket
import struct
import time
import urllib.request
import xml.etree.ElementTree as ET

HOST = os.environ['HOST_IP']
LOCATION = os.environ['TUNER_LOCATION']
LAN = ipaddress.ip_network(os.environ['LAN_CIDR'])
GROUP = ('239.255.255.250', 1900)
QUERY = b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 1\r\nST: upnp:rootdevice\r\n\r\n'


def descriptor_identity():
    with urllib.request.urlopen(LOCATION, timeout=3) as response:
        root = ET.fromstring(response.read())
    identities = [node.text for node in root.iter() if node.tag.rsplit('}', 1)[-1] == 'UDN']
    if len(identities) != 1 or not identities[0].startswith('uuid:'):
        raise ValueError('Native descriptor identity unavailable')
    return identities[0]


def check():
    identity = descriptor_identity()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((HOST, 0))
        probe.settimeout(2)
        probe.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(HOST))
        query = QUERY.replace(b'ST: upnp:rootdevice', b'ST: ' + identity.encode())
        probe.sendto(query, GROUP)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            response, _ = probe.recvfrom(4096)
            if LOCATION.encode() in response and identity.encode() in response:
                return
        raise RuntimeError('Discovery response does not match native descriptor')


def serve():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', 1900))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                    struct.pack('4s4s', socket.inet_aton(GROUP[0]), socket.inet_aton(HOST)))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(HOST))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(.5)
    running = True
    identity = None
    next_refresh = 0
    next_announce = 0

    def stop(*_):
        nonlocal running
        running = False

    def notify(nts):
        headers = ['NOTIFY * HTTP/1.1', 'HOST: 239.255.255.250:1900',
                   'NT: upnp:rootdevice', 'NTS: ' + nts,
                   'USN: ' + identity + '::upnp:rootdevice']
        if nts == 'ssdp:alive':
            headers += ['CACHE-CONTROL: max-age=180', 'LOCATION: ' + LOCATION,
                        'SERVER: xTeVe Kubernetes SSDP gateway/1.0']
        sock.sendto(('\r\n'.join(headers) + '\r\n\r\n').encode(), GROUP)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while running:
            now = time.monotonic()
            if now >= next_refresh:
                next_refresh = now + 10
                try:
                    identity = descriptor_identity()
                except Exception:
                    if identity:
                        notify('ssdp:byebye')
                    identity = None
            if identity and now >= next_announce:
                notify('ssdp:alive')
                next_announce = now + 120
            try:
                packet, address = sock.recvfrom(4096)
            except socket.timeout:
                continue
            if not identity or ipaddress.ip_address(address[0]) not in LAN:
                continue
            lines = packet.decode('ascii', errors='ignore').splitlines()
            if not lines or lines[0].strip().upper() != 'M-SEARCH * HTTP/1.1':
                continue
            headers = dict((key.strip().lower(), value.strip())
                           for line in lines[1:] if ':' in line
                           for key, value in [line.split(':', 1)])
            requested = headers.get('st', '')
            if headers.get('man', '').lower() != '"ssdp:discover"':
                continue
            if requested not in ('ssdp:all', 'upnp:rootdevice', identity):
                continue
            st = identity if requested == identity else 'upnp:rootdevice'
            usn = identity if st == identity else identity + '::upnp:rootdevice'
            response = ['HTTP/1.1 200 OK', 'CACHE-CONTROL: max-age=180', 'EXT:',
                        'LOCATION: ' + LOCATION, 'SERVER: xTeVe Kubernetes SSDP gateway/1.0',
                        'ST: ' + st, 'USN: ' + usn]
            sock.sendto(('\r\n'.join(response) + '\r\n\r\n').encode(), address)
    finally:
        if identity:
            notify('ssdp:byebye')
        sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    check() if args.check else serve()
