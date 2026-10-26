#!/usr/bin/env python3
"""Read-only frontend/SQL preservation and one own transient phpMyAdmin login.

Run in native WSL. Credentials, cookies, response bodies and SQL rows remain in
memory. Uses existing native application credentials, never the random MySQL
root password. Does not change app, database, accounts, grants or storage.
"""
import argparse
import base64
import datetime
import hashlib
import hmac
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import urllib.parse
import urllib.request

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OLD = 'docker.io/library/phpmyadmin-security-20261023@sha256:f52ba34cdf0d98b6b25cf4654fa6da3d69371651dbaab092a92129e6824403f2'
NEW = 'docker.io/library/phpmyadmin:5.2.3-apache@sha256:62a50b1419fe55b9b4c3cd6f5aed03a18f8f5b4a236f24735d76400bea75a5ff'
CHILD = 'sha256:832ef7f6f9ab07f92e82441673a14ef48af672d0a4666620e014dc22e0419e53'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
PHP = r'''
function need($v) { if (!$v) throw new RuntimeException('bounded_observation_refused'); }
$r=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
$key=hex2bin($r['key']); need(strlen($key)===32); $start=microtime(true);
mysqli_report(MYSQLI_REPORT_ERROR|MYSQLI_REPORT_STRICT);
$host=getenv('PMA_HOST'); need(is_string($host)&&$host!==''&&strpos($host,',')===false);
$db=mysqli_init();$db->options(MYSQLI_OPT_CONNECT_TIMEOUT,8);
$db->real_connect($host,$r['username'],$r['password'],$r['database'],(int)(getenv('PMA_PORT')?:3306));
$db->set_charset('utf8mb4');
$grants=[];$q=$db->query('SHOW GRANTS FOR CURRENT_USER()');while($row=$q->fetch_row())$grants[]=$row[0];sort($grants,SORT_STRING);
$account=$db->query('SELECT CURRENT_USER()')->fetch_row()[0];
$db->begin_transaction(MYSQLI_TRANS_START_READ_ONLY|MYSQLI_TRANS_START_WITH_CONSISTENT_SNAPSHOT);
$names=[];$q=$db->query('SHOW TABLES');while($row=$q->fetch_row())$names[]=$row[0];sort($names,SORT_STRING);need(count($names)===12);
$tables=[];$total=0;$totalBytes=0;$excluded=[];
foreach($names as $name){
 need(preg_match('/^[A-Za-z0-9_]+$/D',$name));$qt='`'.$name.'`';
 $schema=$db->query('SHOW CREATE TABLE '.$qt)->fetch_row()[1];$schema=preg_replace('/ AUTO_INCREMENT=\d+/','',$schema);
 $pk=[];$q=$db->query('SHOW KEYS FROM '.$qt." WHERE Key_name='PRIMARY'");while($row=$q->fetch_assoc())$pk[(int)$row['Seq_in_index']]=$row['Column_name'];ksort($pk);need(count($pk)>0);
 foreach($pk as $col)need(preg_match('/^[A-Za-z0-9_]+$/D',$col));
 $sql='SELECT * FROM '.$qt.' ORDER BY '.implode(',',array_map(fn($s)=>'`'.$s.'`',$pk));
 $ctx=hash_init('sha256',HASH_HMAC,$key);hash_update($ctx,$schema);$rows=0;$derived=0;$q=$db->query($sql,MYSQLI_USE_RESULT);
 while($row=$q->fetch_assoc()){
  need(++$total<=100000&&microtime(true)-$start<90);$raw=serialize($row);$totalBytes+=strlen($raw);need(strlen($raw)<=4*1024*1024&&$totalBytes<=256*1024*1024);
  // Same explicit volatile WordPress option exclusions as qualify-wordpress.py.
  if(str_ends_with($name,'_options')&&(in_array($row['option_name'],['cron','rewrite_rules','auto_updater.lock','core_updater.lock'],true)||str_starts_with($row['option_name'],'_transient_')||str_starts_with($row['option_name'],'_site_transient_'))){$derived++;continue;}
  hash_update($ctx,pack('N',strlen($raw)).$raw);$rows++;
 }
 $q->free();$tables[$name]=['rows'=>$rows,'hmac'=>hash_final($ctx)];$excluded[$name]=$derived;
}
$db->rollback();$db->close();
$env=[];foreach(['PMA_HOST','PMA_PORT','PMA_ARBITRARY','SESSION_SAVE_PATH','UPLOAD_LIMIT','MEMORY_LIMIT','MAX_EXECUTION_TIME']as $name)$env[$name]=getenv($name);
$versionSource=file_get_contents('/var/www/html/libraries/classes/Version.php');
need(preg_match('/public const VERSION\s*=\s*[\x27\x22]([0-9.]+)[\x27\x22]/',$versionSource,$version)===1);
// Read the public base version without bootstrapping application globals/code.
echo json_encode(['tables'=>$tables,'derivedRowsExcluded'=>$excluded,'accountHMAC'=>hash_hmac('sha256',$account,$key),'grantsHMAC'=>hash_hmac('sha256',serialize($grants),$key),'environmentHMAC'=>hash_hmac('sha256',serialize($env),$key),'baseAppVersion'=>$version[1],'phpVersion'=>PHP_VERSION,'credentialsLeavePod'=>false,'readOnlyTransaction'=>true],JSON_THROW_ON_ERROR);
'''


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, body=None):
    p = subprocess.run(SSH + [shlex.join(args)], input=body, capture_output=True, timeout=150)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_cluster_read')
    return p.stdout


def get(kind, name, ns='wordpress'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', ns, 'get', kind, name, '-o', 'json']))


class Page(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.inputs = {}
        self.links = []
        self.forms = []
        self.feed(body.decode('utf-8'))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('name'):
            self.inputs[a['name']] = a.get('value', '')
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        if tag == 'form':
            self.forms.append(a)


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def __init__(self, base):
        self.origin = urllib.parse.urlsplit(base)[:2]

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        need(urllib.parse.urlsplit(newurl)[:2] == self.origin, 'off_origin_redirect_refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def web_login(credentials):
    base = 'http://192.168.0.4:8086/'
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), SameOrigin(base), urllib.request.HTTPCookieProcessor(jar))
    def request(url, data=None):
        url = urllib.parse.urljoin(base, url)
        need(urllib.parse.urlsplit(url)[:2] == urllib.parse.urlsplit(base)[:2], 'fixed_http_origin')
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        with client.open(urllib.request.Request(url, data=body), timeout=20) as r:
            raw = r.read(2 * 1024**2 + 1)
            need(r.status == 200 and len(raw) <= 2 * 1024**2, 'bounded_login_response')
            return Page(raw)
    logout = None
    logout_fields = None
    result = {'loginPassed': False, 'ownSessionLogoutPassed': False, 'credentialsInURL': False}
    try:
        page = request(base)
        need({'pma_username', 'pma_password', 'token'} <= set(page.inputs), 'native_login_form')
        forms = [f for f in page.forms if f.get('id') == 'login_form']
        need(len(forms) == 1, 'one_native_login_form')
        fields = dict(page.inputs)
        fields.update(pma_username=credentials['username'], pma_password=credentials['password'])
        fields.setdefault('server', '1')
        if 'pma_servername' in fields:
            fields['pma_servername'] = credentials['host']
        page = request(forms[0].get('action', 'index.php'), fields)
        fields.clear()
        logouts = [link for link in page.links if urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get('route') == ['/logout']]
        need(logouts and 'pma_username' not in page.inputs, 'native_authenticated_page')
        logout = logouts[0]
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(logout).query)
        token = page.inputs.get('token') or query.get('token', [None])[0]
        need(isinstance(token, str) and 0 < len(token) <= 4096, 'current_native_csrf_token')
        logout_fields = {'token': token, 'server': query.get('server', ['1'])[0]}
        result['loginPassed'] = True
    finally:
        try:
            if logout and logout_fields:
                # LogoutController rejects GET and token-mismatched requests.
                request(logout, logout_fields)
                page = request('index.php?route=/server/databases&server=1')
                need('pma_username' in page.inputs, 'own_session_logged_out')
                result['ownSessionLogoutPassed'] = True
        finally:
            jar.clear()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['baseline', 'after', 'restart'], required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--expected-revision', required=True)
    a = p.parse_args()
    os.umask(0o077)
    need(ROOT.is_mount() and ROOT in a.output_dir.parents and a.output_dir.resolve() == a.output_dir
         and re.fullmatch('[0-9a-f]{40}', a.expected_revision), 'canonical_private_scope')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(a.output_dir.stat().st_uid == os.getuid() and not a.output_dir.stat().st_mode & 0o077, 'private_output_owner')
    target = a.output_dir / (a.mode + '.json')
    need(not target.exists(), 'immutable_observation')
    keyfile = a.output_dir / 'observation.key'
    if a.mode == 'baseline' and not keyfile.exists():
        with keyfile.open('xb') as f:
            f.write(os.urandom(32))
    key = keyfile.read_bytes()
    need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
    mac = lambda v: hmac.new(key, json.dumps(v, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    dep = get('deployment', 'phpmyadmin')
    hr = get('helmrelease', 'phpmyadmin', 'flux-system')
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    need(dep['metadata']['uid'] == '25154bdc-ceb0-4210-a42f-3cf53c1c136d'
         and hr['metadata']['uid'] == '4a16e98d-f473-4cfd-ac34-934aee36588e', 'original_frontend_ownership')
    need(source['status']['artifact']['revision'] == 'validated@sha1:' + a.expected_revision
         and hr['status'].get('lastAttemptedRevision', '').endswith('+' + a.expected_revision[:12])
         and hr['status'].get('observedGeneration') == hr['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'exact_flux_revision')
    need(dep['spec']['replicas'] == 1 and dep['status'].get('observedGeneration') == dep['metadata']['generation']
         and all(dep['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'ready_frontend')
    spec = dep['spec']['template']['spec']
    image = OLD if a.mode == 'baseline' else NEW
    need(len(spec['containers']) == 1 and spec['containers'][0]['image'] == image
         and not any('persistentVolumeClaim' in v for v in spec.get('volumes', [])), 'stateless_frontend')
    pods = json.loads(call(['kubectl', '-n', 'wordpress', 'get', 'pods', '-l', 'app=phpmyadmin', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_frontend_pod')
    pod = pods[0]
    cs = pod['status']['containerStatuses'][0]
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running' and cs['ready']
         and cs['imageID'].rsplit('@', 1)[-1] in ({OLD.rsplit('@', 1)[1]} if a.mode == 'baseline' else {NEW.rsplit('@', 1)[1], CHILD}), 'exact_ready_image')
    normalized = json.loads(json.dumps(dep['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<reviewed-image>'
    annotations = normalized['template']['metadata'].get('annotations', {})
    annotations.pop('branconet.lan/security-restart', None)
    if not annotations:
        normalized['template']['metadata'].pop('annotations', None)
    stable = {'deploymentUID': dep['metadata']['uid'], 'releaseUID': hr['metadata']['uid'], 'frontendSpecHMAC': mac(normalized), 'services': {}, 'secrets': {}}
    for name in ['phpmyadmin', 'phpmyadmin-published']:
        s = get('service', name)
        stable['services'][name] = {'uid': s['metadata']['uid'], 'specHMAC': mac(s['spec'])}
    secrets = {}
    for name, uid in [('phpmyadmin-runtime', '352bc710-8530-415d-b0ae-24d034e122d9'), ('wordpress-db-runtime', 'b142ef8e-702f-4c99-b2dc-09f030499f35')]:
        s = get('secret', name)
        need(s['metadata']['uid'] == uid, 'original_native_secret')
        stable['secrets'][name] = {'uid': uid, 'rv': s['metadata']['resourceVersion'], 'type': s.get('type', 'Opaque'), 'contentHMAC': mac(s.get('data', {}))}
        secrets[name] = s.get('data', {})
    decode = lambda name, field: base64.b64decode(secrets[name][field], validate=True).decode()
    credentials = {'username': decode('wordpress-db-runtime', 'MYSQL_USER'), 'password': decode('wordpress-db-runtime', 'MYSQL_PASSWORD'),
                   'database': decode('wordpress-db-runtime', 'MYSQL_DATABASE'), 'host': decode('phpmyadmin-runtime', 'PMA_HOST')}
    backend = get('deployment', 'wordpress-db')
    pvc = get('pvc', 'wordpress-db-data-0')
    bp = json.loads(call(['kubectl', '-n', 'wordpress', 'get', 'pods', '-l', 'app=wordpress-db', '-o', 'json']))['items']
    need(backend['metadata']['uid'] == 'e505c048-f9c5-4c28-b226-ee12c224bf7d' and pvc['metadata']['uid'] == 'b3f53180-5bce-4d84-ab9c-47460a1e3ad9'
         and pvc['status']['phase'] == 'Bound' and len(bp) == 1 and bp[0]['status']['containerStatuses'][0]['ready'], 'original_ready_database_and_data')
    stable['backend'] = {'deploymentUID': backend['metadata']['uid'], 'specHMAC': mac(backend['spec']), 'podUID': bp[0]['metadata']['uid'], 'pvcUID': pvc['metadata']['uid'], 'pvcSpecHMAC': mac(pvc['spec'])}
    payload = {k: credentials[k] for k in ['username', 'password', 'database']}
    payload['key'] = key.hex()
    sql = json.loads(call(['kubectl', '-n', 'wordpress', 'exec', '-i', pod['metadata']['name'], '--', 'php', '-d', 'memory_limit=128M', '-r', PHP], json.dumps(payload).encode()))
    payload.clear()
    need(sql['baseAppVersion'] == '5.2.3' and sql['readOnlyTransaction'] and len(sql['tables']) == 12, 'native_php_database_observation')
    stable['database'] = {k: sql[k] for k in ['tables', 'accountHMAC', 'grantsHMAC', 'environmentHMAC', 'baseAppVersion']}
    login = web_login(credentials)
    credentials.clear()
    secrets.clear()
    routes = []
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for ip in ['192.168.0.4', '192.168.0.5', '192.168.0.6']:
        with client.open('http://' + ip + ':8086/', timeout=15) as r:
            raw = r.read(2 * 1024**2 + 1)
            need(r.status == 200 and len(raw) <= 2 * 1024**2 and 'pma_username' in Page(raw).inputs, 'normal_published_login_route')
            routes.append({'node': ip, 'status': r.status, 'nativeLoginForm': True})
    failures = []
    if a.mode != 'baseline':
        baseline = json.loads((a.output_dir / 'baseline.json').read_bytes())
        need(baseline['passed'] and baseline['keyBinding'] == mac('phpmyadmin-upstream-v1'), 'original_baseline')
        failures = [k for k, v in baseline['stable'].items() if stable.get(k) != v]
        need(pod['metadata']['uid'] != baseline['podUID'], 'different_adoption_pod')
        if a.mode == 'restart':
            prior = json.loads((a.output_dir / 'after.json').read_bytes())
            need(prior['passed'] and pod['metadata']['uid'] != prior['podUID'], 'different_restart_pod')
    result = {'mode': a.mode, 'passed': not failures, 'mismatches': failures, 'stable': stable, 'keyBinding': mac('phpmyadmin-upstream-v1'),
              'podUID': pod['metadata']['uid'], 'image': image, 'imageID': cs['imageID'], 'restarts': cs['restartCount'],
              'phpVersion': sql['phpVersion'], 'derivedRowsExcluded': sql['derivedRowsExcluded'], 'http': routes, 'login': login,
              'fluxRevision': source['status']['artifact']['revision'], 'observedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'browserAccepted': False,
              'limitations': ['Account proof covers configured SQL account/grants and all 12 WordPress tables; administrative mysql.* privilege tables are not claimed.', 'Existing WordPress volatile option exclusions are explicit in source; no application rows are changed.']}
    with target.open('xb') as f:
        f.write((json.dumps(result, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({'mode': a.mode, 'passed': result['passed'], 'mismatches': failures, 'tables': len(sql['tables']), 'phpVersion': sql['phpVersion'], 'login': login, 'podUID': result['podUID']}))
    return int(bool(failures))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'errorCategory': str(error) if type(error) is ValueError else type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
