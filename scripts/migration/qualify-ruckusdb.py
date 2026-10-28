#!/usr/bin/env python3
"""Master-only Ruckus MySQL observer and explicitly gated disposable-copy actions.

No operation runs by default. Keys arrive on stdin; credentials, SQL identifiers,
rows and grant hashes never enter argv, receipts or terminal output. Run only on
the master with its existing kubectl context. See qualify-ruckusdb.md.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import traceback

OLD = 'docker.io/library/mysql:5.7.41@sha256:bf18020f32cc5d8f5e2add516d52fbf3afc3de431457076340e938596c528171'
NEW = 'docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349'
READER = 'ghcr.io/alexta69/metube@sha256:afd3fa2b229e3e6d4c8750618fe148af33a1f70b32af4441ecbd2d08f29d8221'
IDS = {'deployment': 'cf0b7d3c-6d8f-48cb-a55f-0ccd39f610d2',
       'bot': 'dfd27794-a610-445e-b279-6e0933cf1153',
       'bot_release': '790c3088-67d8-47cf-ac00-9d2e1f8c6937',
       'release': 'ea951a7f-02cf-47ba-afb9-44e915c6b8f0',
       'pvc': '2f604004-b45f-4061-bdc4-43f5ca2f7fd8',
       'secret': '9e06e671-28f3-46ae-9e92-ce1c3abdadbc'}
LABEL = 'branconet.net/ruckusdb-copy'
CLIENT = r'''set -eu
IFS= read -r -d '' config
exec 3< <(printf '%s\n' "$config")
unset config
exec mysql --defaults-file=/proc/self/fd/3 --batch --raw --skip-column-names --binary-mode --default-character-set=utf8mb4
'''


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def call(args, data=None, timeout=60):
    p = subprocess.run(['kubectl', '--request-timeout=30s'] + args, input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    # Never expose raw stderr: SQL errors can contain private identifiers/values.
    need(p.returncode == 0, 'kubectl_or_sql_failed')
    need(len(p.stdout) <= 64 * 1024 * 1024, 'bounded_response_exceeded')
    return p.stdout


def get(kind, name=None, ns='ruckus'):
    return json.loads(call((['-n', ns] if ns else []) + ['get', kind] + ([name] if name else []) + ['-o', 'json']))


def mac(key, domain, value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hmac.new(key, domain.encode() + b'\0' + value, hashlib.sha256).hexdigest()


def native(key):
    s = get('secret', 'ruckus-db-runtime')
    need(s['metadata']['uid'] == IDS['secret'], 'native_secret_uid')
    values = {k: base64.b64decode(v, validate=True).decode() for k, v in s['data'].items()}
    need(all(values.get(k) for k in ('MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE')), 'native_app_credential_keys')
    need('MYSQL_ROOT_PASSWORD' not in values, 'unexpected_root_credential_key')
    identity = {'uid': s['metadata']['uid'], 'resourceVersion': s['metadata']['resourceVersion'],
                'data_hmac': mac(key, 'native-secret', s['data'])}
    return values, identity


def live_guard(expected_image, cold=False):
    d, bot = get('deployment', 'ruckus-db'), get('deployment', 'ruckus-bot')
    hr, bhr = get('helmrelease', 'ruckus-db', 'flux-system'), get('helmrelease', 'ruckus-bot', 'flux-system')
    pvc = get('pvc', 'ruckus-db-data-0'); pv = get('pv', pvc['spec']['volumeName'], None)
    for obj, key in [(d, 'deployment'), (bot, 'bot'), (hr, 'release'), (bhr, 'bot_release'), (pvc, 'pvc')]:
        need(obj['metadata']['uid'] == IDS[key] and not obj['metadata'].get('deletionTimestamp'), 'original_identity_' + key)
    need(bot['spec'].get('replicas', 1) == 0 and all(bot['status'].get(k, 0) == 0 for k in ('replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas')), 'writer_not_quiesced')
    need(bhr['spec'].get('values', {}).get('replicaCount') == 0 and not bhr['spec'].get('suspend', False), 'writer_flux_not_zero')
    need(d['spec'].get('replicas', 1) == (0 if cold else 1), 'database_replica_state')
    need(hr['spec'].get('values', {}).get('replicaCount') == (0 if cold else 1) and not hr['spec'].get('suspend', False), 'database_flux_replica_state')
    for obj in (d, bot, hr, bhr):
        need(obj['status'].get('observedGeneration', 0) >= obj['metadata']['generation'], 'unobserved_generation')
    for obj in (hr, bhr):
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in obj['status'].get('conditions', [])), 'flux_not_ready')
    need(pv['spec']['claimRef']['uid'] == IDS['pvc'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_pv_binding')
    template = d['spec']['template']['spec']; need(len(template['containers']) == 1, 'database_container_count')
    c = template['containers'][0]
    need(c['image'] == expected_image and not c.get('command') and not c.get('args'), 'database_launch_or_image_changed')
    need(c.get('envFrom') == [{'secretRef': {'name': 'ruckus-db-runtime'}}], 'native_secret_reference')
    volumes = template['volumes']
    data = [v for v in volumes if v.get('persistentVolumeClaim', {}).get('claimName') == 'ruckus-db-data-0']
    need(len(data) == 1 and any(v['name'] == data[0]['name'] and v['mountPath'] == '/var/lib/mysql' and not v.get('subPath') and not v.get('subPathExpr') for v in c['volumeMounts']), 'original_data_mount')
    pods = get('pods')['items']; live = []
    for p in pods:
        labels = p['metadata'].get('labels', {})
        if all(labels.get(k) == v for k, v in bot['spec']['selector']['matchLabels'].items()):
            need(p['status'].get('phase') in ('Failed', 'Succeeded'), 'writer_pod_remains')
        if any(v.get('persistentVolumeClaim', {}).get('claimName') == 'ruckus-db-data-0' for v in p['spec'].get('volumes', [])):
            if p['status'].get('phase') not in ('Failed', 'Succeeded'):
                live.append(p)
    need(len(live) == (0 if cold else 1), 'database_claim_users')
    identity = {'deployment_uid': d['metadata']['uid'], 'release_uid': hr['metadata']['uid'],
                'writer_uid': bot['metadata']['uid'], 'writer_release_uid': bhr['metadata']['uid'],
                'pvc_uid': pvc['metadata']['uid'], 'pv_uid': pv['metadata']['uid'],
                'resources': c.get('resources', {}), 'image': expected_image}
    if cold:
        return identity, None
    p = live[0]; need(p['status']['containerStatuses'][0]['ready'] and not p['metadata'].get('deletionTimestamp'), 'database_ready')
    need(len(p['spec']['containers']) == 1 and not p['spec'].get('initContainers') and not p['spec'].get('ephemeralContainers'), 'live_pod_execution_surface')
    actual_container = p['spec']['containers'][0]
    need(actual_container['image'] == expected_image and not actual_container.get('command') and not actual_container.get('args'), 'pod_image_or_launch')
    need(actual_container.get('envFrom') == c.get('envFrom') and actual_container.get('resources', {}) == c.get('resources', {}), 'live_pod_native_contract')
    actual_mounts = actual_container.get('volumeMounts', [])
    need(all(m in actual_mounts for m in c.get('volumeMounts', [])), 'live_template_mounts')
    extras = [m for m in actual_mounts if m not in c.get('volumeMounts', [])]
    need(all(m.get('mountPath') == '/var/run/secrets/kubernetes.io/serviceaccount' and m.get('readOnly') is True and not m.get('subPath') for m in extras), 'unexpected_live_mount')
    identity['mount_metadata'] = [{k: v for k, v in m.items() if k != 'name'} for m in actual_mounts]
    owner = next(o for o in p['metadata']['ownerReferences'] if o.get('controller'))
    rs = get('replicaset', owner['name'])
    need(rs['metadata']['uid'] == owner['uid'] and any(o.get('controller') and o['uid'] == IDS['deployment'] for o in rs['metadata']['ownerReferences']), 'database_owner_chain')
    identity.update(pod_uid=p['metadata']['uid'], image_id=p['status']['containerStatuses'][0]['imageID'])
    service = get('service', 'ruckus-db')
    need(service['spec'].get('clusterIP') not in (None, '', 'None'), 'database_service_ip')
    return identity, (p['metadata']['name'], p['spec']['containers'][0]['name'], service['spec']['clusterIP'])


def manifests(run):
    need(re.fullmatch('[a-f0-9]{12}', run), 'run_id')
    ns = 'ruckusdb-copy-' + run; labels = {LABEL: run}
    containers = []
    for name, image in [('old', OLD), ('new', NEW), ('reader', READER)]:
        reader = name == 'reader'
        mounts = ([{'name': v, 'mountPath': '/copies/' + v} for v in ('old', 'new')] if reader else
                  [{'name': name, 'mountPath': '/copy'}, {'name': name + '-run', 'mountPath': '/run/qual'}])
        containers.append({'name': name, 'image': image, 'imagePullPolicy': 'Never',
            'command': ['python3', '-B', '-c', 'import time;time.sleep(3600)'] if reader else ['/bin/sh', '-c', 'exec sleep 3600'],
            'securityContext': {'runAsUser': 0 if reader else 999, 'runAsGroup': 65534,
                'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                'capabilities': {'drop': ['ALL'], **({'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']} if reader else {})}},
            'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'},
                          'limits': {'cpu': '500m', 'memory': '1536Mi' if reader else '512Mi'}},
            'volumeMounts': mounts})
    return [
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns, 'labels': labels}},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {'name': 'deny-all', 'namespace': ns, 'labels': labels},
         'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}},
        {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'qualifier', 'namespace': ns, 'labels': labels},
         'spec': {'nodeSelector': {'kubernetes.io/hostname': 'workernode2'}, 'restartPolicy': 'Never', 'activeDeadlineSeconds': 3600,
             'automountServiceAccountToken': False, 'enableServiceLinks': False, 'hostNetwork': False, 'hostPID': False, 'hostIPC': False,
             'terminationGracePeriodSeconds': 90, 'securityContext': {'fsGroup': 65534, 'supplementalGroupsPolicy': 'Strict',
             'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': containers,
             'volumes': [{'name': x, 'emptyDir': {'medium': 'Memory', 'sizeLimit': '512Mi'}} for x in ('old', 'new')] +
                        [{'name': x + '-run', 'emptyDir': {'medium': 'Memory', 'sizeLimit': '64Mi'}} for x in ('old', 'new')]}}]


def copy_guard(args):
    need(re.fullmatch('ruckusdb-copy-[a-f0-9]{12}', args.namespace or '') and args.pod_uid, 'copy_identity_required')
    run = args.namespace.rsplit('-', 1)[1]
    p = get('pod', 'qualifier', args.namespace)
    need(p['metadata']['uid'] == args.pod_uid and p['metadata'].get('labels', {}).get(LABEL) == run and not p['metadata'].get('deletionTimestamp'), 'copy_pod_uid')
    wanted = manifests(run)[2]['spec']; s = p['spec']
    need(s.get('nodeName') == 'workernode2' and not s.get('initContainers') and not s.get('ephemeralContainers'), 'copy_placement')
    for k in ('volumes', 'containers', 'automountServiceAccountToken', 'enableServiceLinks', 'hostNetwork', 'hostPID', 'hostIPC', 'securityContext'):
        if k == 'containers':
            need(len(s[k]) == 3, 'copy_containers')
            for a, b in zip(s[k], wanted[k]):
                for field in b:
                    need(a.get(field) == b[field], 'copy_container_contract')
                need(not a.get('env') and not a.get('envFrom'), 'copy_no_credentials')
        else:
            need(s.get(k, False) == wanted[k] if k in ('hostNetwork', 'hostPID', 'hostIPC') else s.get(k) == wanted[k], 'copy_contract_' + k)
    policies = get('networkpolicies', ns=args.namespace)['items']
    need(len(policies) == 1 and policies[0]['spec'].get('podSelector') == {} and
         set(policies[0]['spec'].get('policyTypes', [])) == {'Ingress', 'Egress'} and
         not policies[0]['spec'].get('ingress') and not policies[0]['spec'].get('egress'), 'copy_deny_network')
    need(not get('services', ns=args.namespace)['items'], 'copy_no_services')
    return {'pod_uid': p['metadata']['uid'], 'namespace_uid': get('namespace', args.namespace, None)['metadata']['uid'],
            'policy_uid': policies[0]['metadata']['uid'], 'image_ids': {c['name']: c['imageID'] for c in p['status']['containerStatuses']}}


def option(value):
    need('\0' not in value, 'nul_in_client_option')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'


def copy_server_flags(args):
    # MySQL5.7 exposes skip_networking but NOT a skip_grant_tables SQL variable.
    # Read the guarded launch PID's exact public argv, without credentials.
    script = 'set -eu; p=$(cat /run/qual/launch.pid); case "$p" in ""|*[!0-9]*) exit 1;; esac; test "$(basename "$(readlink /proc/$p/exe)")" = mysqld; cat /proc/$p/cmdline'
    raw = call(['-n', args.namespace, 'exec', 'qualifier', '-c', args.container, '--', '/bin/sh', '-c', script])
    expected = [b'mysqld', b'--datadir=/copy/data-0', b'--socket=/run/qual/mysql.sock', b'--pid-file=/run/qual/mysqld.pid', b'--tmpdir=/run/qual', b'--log-error=/run/qual/mysqld-error.log', b'--skip-networking', b'--event-scheduler=OFF']
    if not args.normal_auth: expected.append(b'--skip-grant-tables')
    need(raw.split(b'\0') == expected + [b''], 'exact_private_socket_server_flags')


class SQL:
    def __init__(self, ns, pod, container, values=None, host=None):
        self.ns, self.pod, self.container = ns, pod, container
        self.expected_schema = values['MYSQL_DATABASE'] if values else None
        config = '[client]\nuser=' + option(values['MYSQL_USER'] if values else 'root') + '\n'
        if values:
            config += 'password=' + option(values['MYSQL_PASSWORD']) + '\n'
        config += ('protocol=TCP\nhost=' + option(host) + '\nport=3306\n') if host else 'protocol=SOCKET\nsocket=/run/qual/mysql.sock\n'
        self.config = config.encode()

    def query(self, statement):
        script = "SET SESSION time_zone='+00:00'; SET SESSION TRANSACTION READ ONLY;\n" + statement + ';\n'
        return call(['-n', self.ns, 'exec', '-i', self.pod, '-c', self.container, '--', '/bin/bash', '-c', CLIENT],
                    self.config + b'\0' + script.encode(), timeout=120)


def ident(name):
    return '`' + name.replace('`', '``') + '`'


def literal(name):
    return "CONVERT(X'" + name.encode().hex() + "' USING utf8mb4)"


def snapshot(sql, key, administrative=False):
    version = sql.query('SELECT VERSION()').decode().strip()
    need(version in ('5.7.41', '5.7.44'), 'unexpected_server_version')
    config = sql.query('SELECT @@sql_mode,@@character_set_server,@@collation_server,@@lower_case_table_names,@@innodb_page_size,@@innodb_log_file_size,@@innodb_log_files_in_group,@@innodb_file_per_table,@@log_bin,@@gtid_mode,@@event_scheduler')
    schemas = [bytes.fromhex(x.decode()).decode() for x in sql.query("SELECT HEX(SCHEMA_NAME) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('information_schema','performance_schema') ORDER BY SCHEMA_NAME").splitlines()]
    if sql.expected_schema:
        need(sql.expected_schema in schemas, 'native_application_schema_not_visible')
    if administrative:
        need('mysql' in schemas, 'full_system_schema_not_visible')
    result = {'server_version': version, 'settings_hmac': mac(key, 'server-settings', config),
              'authenticated_account_hmac': mac(key, 'current-user', sql.query('SELECT CURRENT_USER()')),
              'schemas': {}, 'administrative': administrative, 'grant_tables': {}}
    grants = {'user', 'db', 'tables_priv', 'columns_priv', 'procs_priv', 'proxies_priv'}
    for schema in schemas:
        skey = mac(key, 'schema-name', schema.encode())
        tables = {}
        raw = sql.query('SELECT HEX(TABLE_NAME),TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=' + literal(schema) + ' ORDER BY TABLE_NAME')
        for line in raw.splitlines():
            namehex, kind = line.decode().split('\t'); name = bytes.fromhex(namehex).decode()
            target = ident(schema) + '.' + ident(name); tkey = mac(key, 'table-name', (schema + '\0' + name).encode())
            entry = {'kind': kind, 'ddl_hmac': mac(key, 'ddl', sql.query('SHOW CREATE TABLE ' + target))}
            if kind == 'BASE TABLE':
                columns = [bytes.fromhex(x.decode()).decode() for x in sql.query('SELECT HEX(COLUMN_NAME) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=' + literal(schema) + ' AND TABLE_NAME=' + literal(name) + ' ORDER BY ORDINAL_POSITION').splitlines()]
                need(columns, 'no_visible_columns')
                # The preserved bundled tzdata table has119,560 rows. Keep the
                # app bound unchanged and a finite200k bound on that table only.
                cap = 200000 if (schema, name) == ('mysql', 'time_zone_transition') else 100000
                count = int(sql.query('SELECT COUNT(*) FROM ' + target).strip()); need(count <= cap, 'table_row_bound')
                expressions = ["IF(" + ident(c) + " IS NULL,'N',CONCAT('V',HEX(CAST(" + ident(c) + ' AS BINARY))))' for c in columns]
                data = sql.query('START TRANSACTION WITH CONSISTENT SNAPSHOT; SELECT ' + ','.join(expressions) + ' FROM ' + target + '; COMMIT')
                rows = data.splitlines(); need(len(rows) == count == int(sql.query('SELECT COUNT(*) FROM ' + target).strip()), 'row_count_changed_during_observation')
                row_macs = sorted(bytes.fromhex(mac(key, 'row', row)) for row in rows)
                entry.update(rows=count, columns_hmac=mac(key, 'columns', columns),
                             rows_hmac=mac(key, 'row-multiset', b''.join(row_macs)))
                if schema == 'mysql' and name in grants:
                    result['grant_tables'][mac(key, 'grant-table-name', name.encode())] = entry
            tables[tkey] = entry
        objects = {}
        for category, query in {
            'routines': 'SELECT HEX(ROUTINE_NAME),ROUTINE_TYPE,HEX(ROUTINE_DEFINITION),HEX(DEFINER),SQL_MODE,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=' + literal(schema) + ' ORDER BY ROUTINE_NAME,ROUTINE_TYPE',
            'triggers': 'SELECT HEX(TRIGGER_NAME),HEX(ACTION_STATEMENT),HEX(DEFINER),ACTION_TIMING,EVENT_MANIPULATION,HEX(EVENT_OBJECT_TABLE) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=' + literal(schema) + ' ORDER BY TRIGGER_NAME',
            'events': 'SELECT HEX(EVENT_NAME),HEX(EVENT_DEFINITION),HEX(DEFINER),EVENT_TYPE,HEX(EXECUTE_AT),HEX(INTERVAL_VALUE),INTERVAL_FIELD,STATUS,ON_COMPLETION FROM information_schema.EVENTS WHERE EVENT_SCHEMA=' + literal(schema) + ' ORDER BY EVENT_NAME'
        }.items():
            data = sql.query(query); need(b'\tNULL' not in data if category == 'routines' else True, 'routine_definition_not_visible')
            definitions = []
            for line in data.splitlines():
                fields = line.decode().split('\t')
                object_name = bytes.fromhex(fields[0]).decode()
                object_type = fields[1] if category == 'routines' else {'triggers': 'TRIGGER', 'events': 'EVENT'}[category]
                need(object_type in ('PROCEDURE', 'FUNCTION', 'TRIGGER', 'EVENT'), 'unexpected_schema_object_type')
                definitions.append(mac(key, category + '-full-ddl', sql.query('SHOW CREATE ' + object_type + ' ' + ident(schema) + '.' + ident(object_name))))
            objects[category] = {'count': len(data.splitlines()), 'hmac': mac(key, category, data), 'ddl_hmac': mac(key, category + '-definitions', definitions)}
        result['schemas'][skey] = {'ddl_hmac': mac(key, 'database-ddl', sql.query('SHOW CREATE DATABASE ' + ident(schema))), 'tables': tables, 'objects': objects}
    if administrative:
        need(len(result['grant_tables']) == len(grants), 'all_six_grant_tables_required')
    return result


PHYSICAL = r'''import sys,json,hashlib,hmac,os,stat
from pathlib import Path
key=bytes.fromhex(sys.stdin.readline().strip());assert len(key)==32
result={}
for side in ['old','new']:
 root=Path('/copies')/side/'data-0';assert root.is_dir() and not root.is_symlink()
 assert (root/'mysql/user.frm').is_file() and (root/'ibdata1').is_file()
 rows=[];total=0
 for p in [root,*sorted(root.rglob('*'))]:
  s=p.lstat();rel=str(p.relative_to(root));row=[rel,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_mtime_ns]
  if p.is_symlink():
   link=os.readlink(p)
   # Exact original cold-manifest socket link is metadata only. Never follow it;
   # cloned servers use the explicit /run/qual/mysql.sock socket instead.
   assert (rel=='mysql.sock' and link=='/var/run/mysqld/mysqld.sock') or p.resolve().is_relative_to(root.resolve())
   row+=['link',link]
  elif p.is_file():
   with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
   total+=s.st_size;assert total<=384*1024*1024;row+=['file',s.st_size,digest]
  else: assert p.is_dir();row+=['directory']
  rows.append(row)
 result[side]={'objects':len(rows),'bytes':total,'hmac':hmac.new(key,json.dumps(rows,separators=(',',':')).encode(),hashlib.sha256).hexdigest()}
print(json.dumps(result))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['plan', 'observe-live', 'physical-copy', 'observe-copy', 'start-copy', 'stop-copy', 'upgrade-copy', 'compare'])
    ap.add_argument('--run-id'); ap.add_argument('--namespace'); ap.add_argument('--pod-uid')
    ap.add_argument('--container', choices=['old', 'new']); ap.add_argument('--normal-auth', action='store_true')
    ap.add_argument('--expected-image'); ap.add_argument('--receipt', type=Path); ap.add_argument('--baseline', type=Path)
    ap.add_argument('--restore-proof', type=Path)
    args = ap.parse_args()
    if args.action == 'plan':
        print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': manifests(args.run_id)}, indent=2)); return
    need(os.name == 'posix' and args.receipt, 'master_receipt_required')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077)
    need(not args.receipt.exists(), 'receipt_must_be_new')
    key = bytes.fromhex(sys.stdin.readline().strip()); need(len(key) == 32, 'stdin_hmac_key')
    receipt = {'action': args.action, 'status': 'failed', 'key_id': mac(key, 'key-id', b'ruckusdb'),
               'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        if args.action == 'observe-live':
            need(args.expected_image and '@sha256:' in args.expected_image, 'expected_live_image_required')
            before, target = live_guard(args.expected_image); values, secret = native(key)
            sql = SQL('ruckus', target[0], target[1], values, target[2])
            state = snapshot(sql, key); again = snapshot(sql, key)
            need(state == again, 'live_sql_not_stable')
            after, _ = live_guard(args.expected_image); _, secret_after = native(key)
            need(before == after and secret == secret_after, 'identity_changed_during_capture')
            receipt.update(identity=before, native_secret=secret, state=state)
        elif args.action == 'compare':
            need(args.baseline and args.restore_proof, 'compare_requires_two_receipts')
            a, b = json.loads(args.baseline.read_text()), json.loads(args.restore_proof.read_text())
            need(a['key_id'] == b['key_id'] == receipt['key_id'] and a['status'] == b['status'] == 'passed', 'matching_successful_keyed_receipts')
            x, y = a['state'], b['state']
            receipt['comparison'] = {'schemas_equal': x['schemas'] == y['schemas'], 'grants_equal': x['grant_tables'] == y['grant_tables'],
                'settings_equal': x['settings_hmac'] == y['settings_hmac'], 'same_scope': x['administrative'] == y['administrative'],
                'same_authenticated_account': x['authenticated_account_hmac'] == y['authenticated_account_hmac']}
            if 'native_secret' in a or 'native_secret' in b:
                need(a.get('native_secret', {}).get('uid') == b.get('native_secret', {}).get('uid') and a.get('native_secret', {}).get('data_hmac') == b.get('native_secret', {}).get('data_hmac'), 'native_secret_preservation')
            if 'identity' in a and 'identity' in b:
                need(all(a['identity'].get(k) == b['identity'].get(k) for k in ['deployment_uid','release_uid','writer_uid','writer_release_uid','pvc_uid','pv_uid','resources','mount_metadata']), 'live_identity_and_budget_preservation')
            need(all(receipt['comparison'].values()), 'data_schema_grant_or_settings_changed')
        else:
            identity = copy_guard(args); receipt['copy_identity'] = identity
            if args.action == 'physical-copy':
                live_guard(args.expected_image or OLD.replace('docker.io/library/', ''), cold=True)
                raw = call(['-n', args.namespace, 'exec', '-i', 'qualifier', '-c', 'reader', '--', 'python3', '-B', '-c', PHYSICAL], key.hex().encode()+b'\n', timeout=180)
                receipt['physical'] = json.loads(raw); need(receipt['physical']['old'] == receipt['physical']['new'], 'full_cold_copies_not_equal')
            else:
                need(args.container, 'copy_container_required')
                prefix = ['-n', args.namespace, 'exec', '-i', 'qualifier', '-c', args.container, '--']
                if args.action == 'observe-copy':
                    values, secret = native(key) if args.normal_auth else (None, None)
                    sql = SQL(args.namespace, 'qualifier', args.container, values)
                    copy_server_flags(args)
                    need(sql.query('SELECT @@skip_networking').strip() == b'1', 'copy_no_network')
                    receipt['state'] = snapshot(sql, key, administrative=not args.normal_auth)
                    if secret: receipt['native_secret'] = secret
                elif args.action == 'start-copy':
                    need(args.restore_proof, 'verified_full_restore_proof_required')
                    proof = json.loads(args.restore_proof.read_text())
                    need(proof['status'] == 'passed' and proof['action'] == 'physical-copy' and proof['copy_identity']['pod_uid'] == args.pod_uid and proof['key_id'] == receipt['key_id'], 'restore_proof_identity')
                    flags = '' if args.normal_auth else ' --skip-grant-tables'
                    script = 'set -eu; test -s /copy/data-0/mysql/user.frm; test -s /copy/data-0/ibdata1; test ! -e /run/qual/launch.pid; test ! -e /run/qual/mysqld.pid; nohup mysqld --datadir=/copy/data-0 --socket=/run/qual/mysql.sock --pid-file=/run/qual/mysqld.pid --tmpdir=/run/qual --log-error=/run/qual/mysqld-error.log --skip-networking --event-scheduler=OFF' + flags + ' >/run/qual/server.log 2>&1 </dev/null & echo $! >/run/qual/launch.pid'
                    call(prefix + ['/bin/sh', '-c', script]); receipt['startup_is_not_readiness'] = True
                elif args.action == 'stop-copy':
                    script = 'set -eu; p=$(cat /run/qual/launch.pid); case "$p" in ""|*[!0-9]*) exit 1;; esac; test "$(basename "$(readlink /proc/$p/exe)")" = mysqld; kill -TERM "$p"; i=0; while test -e /proc/$p/exe; do i=$((i+1)); test "$i" -lt 90; sleep 1; done; test ! -e /run/qual/mysqld.pid; rm /run/qual/launch.pid'
                    call(prefix + ['/bin/sh', '-c', script], timeout=100)
                else:
                    need(args.container == 'new' and not args.normal_auth, 'upgrade_only_new_disposable_bypass_copy')
                    sql = SQL(args.namespace, 'qualifier', 'new')
                    copy_server_flags(args)
                    need(sql.query('SELECT VERSION(),@@skip_networking').strip() == b'5.7.44\t1', 'upgrade_copy_server_guard')
                    output = call(prefix + ['mysql_upgrade', '--defaults-file=/dev/null', '--protocol=SOCKET', '--socket=/run/qual/mysql.sock', '--user=root'], timeout=300)
                    receipt['upgrade_output_hmac'] = mac(key, 'upgrade-output', output)
                    receipt['restart_and_grant_comparison_required'] = True
            need(copy_guard(args) == identity, 'copy_identity_changed')
        receipt['status'] = 'passed'
    except Exception as e:
        receipt['error'] = str(e) if isinstance(e, RuntimeError) else type(e).__name__
        receipt['error_source_lines'] = [f.lineno for f in traceback.extract_tb(e.__traceback__) if f.filename == __file__]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': receipt['status'], 'receipt': str(args.receipt)}))
    if receipt['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
