#!/usr/bin/env python3
"""Read WordPress files/accounts/content without loading application code or exposing values."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'wordpress:latest@sha256:ee74dc0ebbe7ec43b7f473c0fb4f1dfb6b211d7785f0a95bcdfa10e628c2e67f'
NEW = 'docker.io/library/wordpress-security-20261023@sha256:fe0f66b827b865026a5ffcf0ee28b34f8e2d2cc9fb6c85bd3faace75987a9bf0'

PHP = r'''
ini_set('display_errors','0'); set_time_limit(120);
function need($ok) { if (!$ok) throw new Exception('observation_refused'); }
$key=hex2bin(trim(stream_get_contents(STDIN,129))); need(strlen($key)===32);
$start=microtime(true); $entries=[]; $bytes=0; $count=0;
$root='/var/www/html';
$iter=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::SELF_FIRST);
foreach($iter as $file) {
 need(++$count<=8192 && microtime(true)-$start<100);
 $path=$file->getPathname(); $rel=substr($path,strlen($root)+1); $s=lstat($path);
 $kind=is_link($path)?'link':(is_dir($path)?'dir':'file');
 need(in_array($s['mode'] & 0170000,[0100000,0040000,0120000],true));
 $row=[$kind,$s['mode'] & 07777,$s['uid'],$s['gid']];
 if($kind==='file') {
  $bytes+=$s['size']; need($bytes<=1024*1024*1024 && $s['size']<=128*1024*1024);
  $row[]= $s['size']; $row[]=hash_hmac_file('sha256',$path,$key); clearstatcache(true,$path); $after=lstat($path);
  need($s['ino']===$after['ino'] && $s['size']===$after['size'] && $s['mtime']===$after['mtime']);
 } elseif($kind==='link') { $row[]=readlink($path); }
 $entries[$rel]=$row;
}
ksort($entries,SORT_STRING); $fileHash=hash_hmac('sha256',serialize($entries),$key);
$host=getenv('WORDPRESS_DB_HOST'); need(is_string($host) && $host!=='');
$parts=explode(':',$host,2); $port=isset($parts[1])?(int)$parts[1]:3306;
mysqli_report(MYSQLI_REPORT_ERROR|MYSQLI_REPORT_STRICT);
$db=new mysqli($parts[0],getenv('WORDPRESS_DB_USER'),getenv('WORDPRESS_DB_PASSWORD'),getenv('WORDPRESS_DB_NAME'),$port);
$db->set_charset('utf8mb4'); $db->begin_transaction(MYSQLI_TRANS_START_READ_ONLY|MYSQLI_TRANS_START_WITH_CONSISTENT_SNAPSHOT);
$names=[]; $r=$db->query('SHOW TABLES'); while($row=$r->fetch_row())$names[]=$row[0]; sort($names,SORT_STRING); need(count($names)===12);
$tables=[]; $total=0; $totalBytes=0;
foreach($names as $name) {
 need(preg_match('/^[A-Za-z0-9_]+$/D',$name)); $q='`'.$name.'`';
 $schema=$db->query('SHOW CREATE TABLE '.$q)->fetch_row()[1];
 // AUTO_INCREMENT is allocator state; rows and all other schema fields stay exact.
 $schema=preg_replace('/ AUTO_INCREMENT=\d+/','',$schema);
 $pk=[]; $r=$db->query('SHOW KEYS FROM '.$q." WHERE Key_name='PRIMARY'"); while($row=$r->fetch_assoc())$pk[(int)$row['Seq_in_index']]=$row['Column_name']; ksort($pk);
 need(count($pk)>0); foreach($pk as $col) need(preg_match('/^[A-Za-z0-9_]+$/D',$col));
 $sql='SELECT * FROM '.$q.' ORDER BY '.implode(',',array_map(fn($s)=>'`'.$s.'`',$pk));
 $ctx=hash_init('sha256',HASH_HMAC,$key); hash_update($ctx,$schema); $rows=0; $derived=0;
 $r=$db->query($sql,MYSQLI_USE_RESULT);
 while($row=$r->fetch_assoc()) {
  need(++$total<=100000 && microtime(true)-$start<115);
  $raw=serialize($row); $totalBytes+=strlen($raw); need(strlen($raw)<=4*1024*1024 && $totalBytes<=256*1024*1024);
  // These standard scheduling/cache rows can change during normal PHP requests.
  // The complete logical backup retains them too; they are excluded only from equality.
  if(str_ends_with($name,'_options') && (in_array($row['option_name'],['cron','rewrite_rules','auto_updater.lock','core_updater.lock'],true)
       || str_starts_with($row['option_name'],'_transient_') || str_starts_with($row['option_name'],'_site_transient_'))) { $derived++; continue; }
  hash_update($ctx,pack('N',strlen($raw)).$raw); $rows++;
 }
 $r->free(); $tables[$name]=['rows'=>$rows,'hmac'=>hash_final($ctx),'derivedRowsExcluded'=>$derived];
}
$db->rollback(); $db->close();
$version=file_get_contents($root.'/wp-includes/version.php'); preg_match('/\$wp_version\s*=\s*[\x27\x22]([^\x27\x22]+)/',$version,$m); need(isset($m[1]));
$plugins=[]; foreach(glob($root.'/wp-content/plugins/*/*.php') as $path) {
 $header=file_get_contents($path,false,null,0,8192);
 if(preg_match('/^[ \t\/*#@]*Plugin Name:\s*(.+)$/mi',$header,$n)) {
  preg_match('/^[ \t\/*#@]*Version:\s*(.+)$/mi',$header,$v);
  $plugins[]=['slug'=>basename(dirname($path)),'name'=>trim($n[1]),'version'=>isset($v[1])?trim($v[1]):'unknown'];
 }
}
echo json_encode(['filesHMAC'=>$fileHash,'fileEntries'=>$count,'fileBytes'=>$bytes,'tables'=>$tables,'wordpressVersion'=>$m[1],
 'phpVersion'=>PHP_VERSION,'plugins'=>$plugins,'credentialsLeavePod'=>false,'applicationCodeExecuted'=>false],JSON_THROW_ON_ERROR);
'''


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, body=None, timeout=40):
    r = subprocess.run(SSH + [shlex.join(args)], input=body, capture_output=True, timeout=timeout)
    need(r.returncode == 0 and len(r.stdout) <= 1024 ** 2, 'bounded_cluster_observation')
    return r.stdout


def get(kind, name, ns='wordpress'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', ns, 'get', kind, name, '-o', 'json']))


def fence(expected):
    d = get('deployment', 'wordpress')
    h = get('helmrelease', 'wordpress', 'flux-system')
    pvc = get('pvc', 'wordpress-data-0')
    need(d['metadata']['uid'] == 'c5b60268-c0d4-43f8-8014-4c04e427a122' and h['metadata']['uid'] == '65ca0d62-fc47-4063-81a5-4ed59767e907'
         and pvc['metadata']['uid'] == '90b7695b-3cbf-41d9-b6d1-1f9ee3fd5e2f' and pvc['status']['phase'] == 'Bound', 'original_workload_and_claim')
    need(d['spec']['replicas'] == 1 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas'])
         and h['status'].get('observedGeneration') == h['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status'].get('conditions', [])), 'ready_observed_flux_writer')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'same_longhorn_binding')
    pods = json.loads(call(['kubectl', '-n', 'wordpress', 'get', 'pods', '-l', 'app=wordpress', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_writer')
    p = pods[0]
    c = p['spec']['containers'][0]
    cs = p['status']['containerStatuses'][0]
    need(not p['metadata'].get('deletionTimestamp') and cs['ready'] and c['image'] == expected
         and c['envFrom'] == [{'secretRef': {'name': 'wordpress-runtime'}}]
         and any(v.get('persistentVolumeClaim', {}).get('claimName') == 'wordpress-data-0' for v in p['spec']['volumes'])
         and any(v['mountPath'] == '/var/www/html' and not v.get('subPath') for v in c['volumeMounts']), 'original_launch_and_mount')
    if expected == NEW:
        need(cs['imageID'].rsplit('@', 1)[-1] == NEW.rsplit('@', 1)[-1], 'exact_patched_runtime')
    secret = call(['kubectl', '-n', 'wordpress', 'get', 'secret', 'wordpress-runtime',
                   '-o', 'jsonpath={.metadata.uid}{" "}{.metadata.resourceVersion}']).decode().split()
    need(len(secret) == 2, 'native_secret_metadata_only')
    return {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'pvcUID': pvc['metadata']['uid'],
            'pvUID': pv['metadata']['uid'], 'pod': p['metadata']['name'], 'podUID': p['metadata']['uid'],
            'image': c['image'], 'imageID': cs['imageID'], 'secretUID': secret[0], 'secretRV': secret[1]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--baseline', type=Path)
    a = p.parse_args()
    os.umask(0o077)
    need(os.name == 'posix' and a.output_dir.is_absolute() and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(not a.output_dir.stat().st_mode & 0o077, 'private_output_mode')
    record = {'passed': False, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        keyfile = a.output_dir / 'observation.key'
        if a.baseline:
            need(a.baseline.parent == a.output_dir and not a.baseline.is_symlink(), 'same_private_baseline_scope')
            prior = json.loads(a.baseline.read_bytes())
            need(prior['passed'], 'accepted_baseline')
            key = keyfile.read_bytes()
        else:
            key = os.urandom(32)
            with keyfile.open('xb') as f:
                f.write(key)
        need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
        before = fence(NEW if a.baseline else OLD)
        data = json.loads(call(['kubectl', '-n', 'wordpress', 'exec', '-i', before['pod'], '--', 'php', '-d', 'memory_limit=128M', '-r', PHP], key.hex().encode(), timeout=150))
        need(fence(NEW if a.baseline else OLD) == before, 'stable_writer')
        need(data['wordpressVersion'] == '7.1.3', 'same_wordpress_version')
        if a.baseline:
            old = prior['observation']
            need(all(before[k] == prior['writer'][k] for k in ['deploymentUID', 'releaseUID', 'pvcUID', 'pvUID', 'secretUID', 'secretRV']), 'same_original_data_and_native_secret')
            need(before['podUID'] != prior['writer']['podUID'] and data['phpVersion'] == '8.3.36', 'new_patched_php_writer')
            need(all(data[k] == old[k] for k in ['filesHMAC', 'fileEntries', 'fileBytes', 'plugins']), 'complete_original_file_tree')
            need(set(data['tables']) == set(old['tables']) and all(all(data['tables'][t][k] == old['tables'][t][k] for k in ['rows', 'hmac']) for t in old['tables']), 'all_original_accounts_content_and_settings')
        record.update(passed=True, writer=before, observation=data, baseline=str(a.baseline) if a.baseline else None)
    except Exception as error:
        record['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    record['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / ('wordpress-functional-' + uuid.uuid4().hex + '.json')
    out.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': record['passed'], 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': record.get('failure')}))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
