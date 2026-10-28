#!/usr/bin/env python3
"""Read-only current YTPTube users/config/history fingerprints; no app imports."""
import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('ytptube_operator', Path(__file__).with_name('qualify-ytptube.py'))
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)

SQL = r'''
import json,sys,sqlite3,pathlib,hashlib,hmac
r=json.load(sys.stdin);key=bytes.fromhex(r['key']);r.clear()
p=pathlib.Path('/config/ytptube.db')
assert p.is_file() and not p.is_symlink() and p.stat().st_size<=128*1024**2
c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
assert [tuple(x)for x in c.execute('PRAGMA quick_check')]==[('ok',)]
tables=[x[0]for x in c.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
expected={'api_keys','conditions','dl_fields','history','migration_version','notifications','presets','sessions','task_definitions','tasks','users'}
assert set(tables)==expected
def digest(value):return hmac.new(key,json.dumps(value,separators=(',',':'),ensure_ascii=False).encode(),hashlib.sha256).hexdigest()
out={'quickCheck':'ok','tables':{},'sessionsExcluded':'ephemeral login/logout sessions; users and API keys remain fully compared'}
for name in tables:
 if name=='sessions':continue
 columns=[x[1]for x in c.execute('PRAGMA table_info("'+name+'")')]
 rows=[dict(x)for x in c.execute('SELECT * FROM "'+name+'" ORDER BY '+','.join('"'+x+'"'for x in columns))]
 assert len(rows)<=50000
 out['tables'][name]={'columns':columns,'count':len(rows),'hmacSHA256':digest(rows)}
 if name=='history':
  indexed={json.dumps([x['id'],x['type']],separators=(',',':')):digest(x)for x in rows}
  assert len(indexed)==len(rows);out['tables'][name]['perRow']=indexed
c.execute('ROLLBACK');c.close();key=None;print(json.dumps(out))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['baseline', 'after', 'restart'])
    p.add_argument('--receipt', required=True, type=Path)
    p.add_argument('--baseline', type=Path)
    args = p.parse_args()
    image = operator.DERIVATIVE_IMAGE if args.phase == 'baseline' else operator.UPSTREAM_IMAGE
    before = operator.writer(image)
    if before['deployment_uid'] != 'b6f10b2b-3350-49f5-9b1c-182f80db4af5':
        raise operator.Refused('deployment_identity_changed')
    expected = {'ytdl-data-0': '5411bcf9-4331-43bd-9a8d-7d0fbf0a9324',
                'ytdl-data-1': 'dcc218b0-929e-4892-bd72-1a226157af5d',
                'ytdl-data-2': '7c3e8710-a79d-408f-b8fb-df3b87bdb0de'}
    if {v['name']: v['uid'] for v in before['claims'].values()} != expected:
        raise operator.Refused('claim_identity_changed')
    secret = operator.obj('get', 'secret', operator.SECRET)
    username, password = (base64.b64decode(secret['data'][k], validate=True) for k in ['username', 'password'])
    key = hmac.new(password, b'ytptube-state-v1\0' + username, hashlib.sha256).digest()
    secret_uid = secret['metadata']['uid']
    secret.clear(); username = password = None
    raw = operator.kubectl('exec', '-i', before['pod'], '-c', 'ytdl', '--',
                           '/opt/python/bin/python', '-B', '-c', SQL,
                           body=json.dumps({'key': key.hex()}).encode(), timeout=60)
    key = None
    if len(raw) > 8 * 1024**2:
        raise operator.Refused('state_metadata_limit')
    current = json.loads(raw)
    if before != operator.writer(image):
        raise operator.Refused('writer_changed_during_observation')
    if args.phase != 'baseline':
        if not args.baseline:
            raise operator.Refused('protected_baseline_required')
        previous = json.loads(args.baseline.read_bytes())
        if not previous.get('passed') or previous['nativeSecretUID'] != secret_uid or previous['writer']['claims'] != before['claims']:
            raise operator.Refused('baseline_identity_mismatch')
        for table, prior in previous['state']['tables'].items():
            now = current['tables'][table]
            if table == 'history':
                if prior['columns'] != now['columns'] or not all(now['perRow'].get(k) == v for k, v in prior['perRow'].items()):
                    raise operator.Refused('original_history_changed')
            elif now != prior:
                raise operator.Refused('stored_' + table + '_changed')
    result = {'passed': True, 'phase': args.phase, 'writer': before,
              'nativeSecretUID': secret_uid, 'state': current,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'baselineSHA256': hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None}
    operator.save_new(args.receipt, result)
    print(json.dumps({'passed': True, 'phase': args.phase,
                      'counts': {k: v['count'] for k, v in current['tables'].items()}}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'passed': False, 'category': str(error) if isinstance(error, operator.Refused) else type(error).__name__}))
        raise SystemExit(1)
