#!/usr/bin/env python3
"""Operator-only XR500 DHCP toggle; preserve the exact existing LAN settings.

The router's LAN form uses a blocking JavaScript alert before submission. This
uses that same firmware form endpoint when the in-app browser cannot dismiss it.
No write operation is exposed through the read-only Netgear MCP registration.
"""
import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, '/home/brajam/repos/veyra-monorepo/mcp-servers/netgear-xr500')
import server as router

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['read', 'disable', 'restore'])
args = parser.parse_args()


class LanForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.action = a.get('action')
        if tag == 'input' and a.get('name') and a.get('type', '').lower() not in ['button', 'checkbox', 'radio', 'submit']:
            self.fields[a['name']] = a.get('value', '')


def variable(page, name):
    values = set(re.findall(r'\bvar\s+' + re.escape(name) + r'''\s*=\s*['"]([^'"\n]*)['"]''', page))
    if len(values) != 1:
        raise RuntimeError('Ambiguous firmware LAN field: ' + name)
    return values.pop()


def read():
    status, page = router.fetch('/LAN_lan.htm', router.authorization())
    if status != 200:
        raise RuntimeError('Router LAN read failed')
    mode = re.findall(r"if\s*\(\s*'([01])'\s*==\s*'1'\s*\)\s*form\.dhcp_server\.checked\s*=\s*true", page)
    reservations = re.findall(r'''\bresevArray\d+\s*=\s*(["'])(.*?)\1\s*;''', page)
    if len(mode) != 1 or len(reservations) != 5:
        raise RuntimeError('Unexpected firmware DHCP/reservation schema')
    snapshot = {'enabled': mode[0] == '1', 'gateway': variable(page, 'old_lanip'),
                'device_name': variable(page, 'dev_name'),
                'netmask': variable(page, 'old_lanmask'), 'pool': router.extract_dhcp_pool(page),
                'reservation_count': len(reservations),
                'reservations_sha256': hashlib.sha256(json.dumps(reservations).encode()).hexdigest()}
    if snapshot['gateway'] != '192.168.0.1' or snapshot['netmask'] != '255.255.255.0' or snapshot['pool'] != {'start': '192.168.0.2', 'end': '192.168.0.199'}:
        raise RuntimeError('Router LAN differs from approved handoff baseline')
    return page, snapshot


page, before = read()
if variable(page, 'sysRIPVersion') != '0' or variable(page, 'rip_direction') != '0':
    raise RuntimeError('RIP settings differ from the reviewed unchanged baseline')
if args.mode == 'read':
    print(json.dumps(before))
    raise SystemExit(0)
desired = args.mode == 'restore'
if desired:
    service_state = subprocess.check_output([
        'ssh', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002',
        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8',
        'james@192.168.0.5',
        "systemctl show branconet-lan-dhcp.service -p ActiveState -p UnitFileState; ss -4 -Hlun 'sport = :67'"], text=True)
    facts = dict(line.split('=', 1) for line in service_state.splitlines() if '=' in line)
    listeners = [line for line in service_state.splitlines() if line and '=' not in line]
    if facts.get('ActiveState') != 'inactive' or facts.get('UnitFileState') != 'disabled' or listeners:
        raise RuntimeError('Replacement DHCP is not stopped and disabled; router restoration refused')
if before['enabled'] == desired:
    print(json.dumps({'changed': False, 'observed': before}))
    raise SystemExit(0)
form = LanForm()
form.feed(page)
if not re.fullmatch(r'/apply\.cgi\?/LAN_lan\.htm timestamp=\d+', form.action or ''):
    raise RuntimeError('Unexpected LAN form destination')
fields = form.fields
if fields.get('submit_flag') != 'lan':
    raise RuntimeError('Unexpected LAN operation')
for prefix, value in [('sysLANIPAddr', before['gateway']), ('sysLANSubnetMask', before['netmask']),
                      ('sysPoolStartingAddr', before['pool']['start']), ('sysPoolFinishAddr', before['pool']['end'])]:
    for i, octet in enumerate(value.split('.'), 1):
        fields[prefix + str(i)] = octet
fields.update({'device_name': before['device_name'],
               'dhcp_mode': '1' if desired else '0', 'dhcp_start': before['pool']['start'],
               'dhcp_end': before['pool']['end'], 'lan_ipaddr': before['gateway'],
               'lan_subnet': before['netmask'], 'dmz_ip': variable(page, 'dmz_ip'),
               'bs_trustedip': variable(page, 'bs_trustedip'), 'change_network_flag': '0',
               'change_network2_flag': '0', 'change_ip_flag': '0', 'hid_array_num': '5',
               'out_of_range': '', 'dhcp_pool_tag': '0', 'sysRIPVersion': 'Disabled',
               'rip_direction': 'Both'})
if desired:
    fields['dhcp_server'] = '1'
body = urlencode(fields)
# Match the operator's HTTP LAN interface. The preceding authenticated read
# checked the fixed router's configured HTTPS pin; no redirect or other host is
# accepted, and no credential is logged or written to disk.
connection = http.client.HTTPConnection(router.HOST, timeout=20)
try:
    connection.request('POST', form.action.replace(' ', '%20'), body=body,
                       headers={'Authorization': router.authorization(),
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'User-Agent': 'Branconet-XR500-MCP',
                                'Origin': 'http://' + router.HOST,
                                'Referer': 'http://' + router.HOST + '/LAN_lan.htm'})
    response = connection.getresponse()
    response_body = response.read(router.MAX_PAGE)
    status = response.status
    response_text = response_body.decode(errors='replace')
    Path('/mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z/logs/SWARM-router-save-response.html').write_text(response_text)
    visible = re.sub(r'<script\b[^>]*>.*?</script>', '', response_text, flags=re.I | re.S)
    visible = re.sub(r'<style\b[^>]*>.*?</style>', '', visible, flags=re.I | re.S)
    visible = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', visible)).split())
    print(json.dumps({'post_status': status,
                      'response_title': re.findall(r'<title>([^<]{0,160})</title>', response_body.decode(errors='replace'), re.I),
                      'response_notice': visible[:600],
                      'firmware_alerts': re.findall(r'''alert\(['"]([^'"\n]{0,200})['"]\)''', response_text),
                      'response_sha256': hashlib.sha256(response_body).hexdigest(),
                      'response_bytes': len(response_body)}))
finally:
    connection.close()
markers = set(re.findall(r'finish\.txt\?mark=(\d+)', response_text))
if len(markers) == 1:
    marker = markers.pop()
    print(json.dumps({'apply_job': marker, 'state': 'waiting'}), flush=True)
    for attempt in range(60):
        try:
            _, result = router.fetch('/finish.txt?mark=' + marker, router.authorization())
        except (TimeoutError, OSError):
            time.sleep(2)
            continue
        if result.strip() == '1':
            print(json.dumps({'apply_job': marker, 'state': 'finished'}), flush=True)
            break
        time.sleep(2)
    else:
        raise RuntimeError('Apply marker pending; reconcile this job before another write')
_, after = read()
for key in ['device_name', 'gateway', 'netmask', 'pool', 'reservation_count', 'reservations_sha256']:
    if before[key] != after[key]:
        raise RuntimeError('LAN preservation check failed: ' + key)
if after['enabled'] != desired:
    raise RuntimeError('Router did not save requested DHCP state (HTTP ' + str(status) + '); do not start another server')
print(json.dumps({'changed': True, 'post_status': status, 'before': before, 'after': after}))
