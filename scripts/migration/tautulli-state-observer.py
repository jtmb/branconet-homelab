#!/usr/bin/env python3
"""Tautulli 2.16.1 -> 2.18.2 preservation projection; no app imports/writes."""
import base64
import configparser
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import time

MAX_SQLITE = 128 * 1024 ** 2  # Combined RAM snapshots, not each connection.
MAX_VALUE = 1024 ** 2
MAX_ENCODED = 32 * 1024 ** 2
MAX_ROWS = 250000
OLD_VERSION, NEW_VERSION = 'v2.16.1', 'v2.18.2'
NEW_COMMIT = '9484667bc1f2d159368a999320b8f495bbfbd00a'
DATABASE_FILES = {'tautulli.db', 'tautulli.db-wal', 'tautulli.db-shm'}
NEW_COLUMNS = {'mobile_devices': [('push_token', 'TEXT', None)],
               'exports': [('squareArt_level', 'INTEGER', '0'), ('theme_level', 'INTEGER', '0')]}
NEW_CONFIG = {('Advanced', 'allow_mounted_folders'): '0',
              ('Advanced', 'remote_app_push_url'): 'https://relay.tautulliremote.com',
              ('Advanced', 'x_frame_options'): 'SAMEORIGIN'}
NEW_INDEX_COLUMNS = {
    'idx_session_history_started': ('session_history', 'started'),
    'idx_session_history_stopped': ('session_history', 'stopped'),
    'idx_session_history_user_id_started': ('session_history', 'user_id, started ASC'),
    'idx_session_history_user_id_rating_key': ('session_history', 'user_id, rating_key'),
    'idx_session_history_section_id_started': ('session_history', 'section_id, started ASC'),
    'idx_session_history_metadata_parent_rating_key': ('session_history_metadata', 'parent_rating_key'),
    'idx_session_history_metadata_grandparent_rating_key': ('session_history_metadata', 'grandparent_rating_key'),
    'idx_notify_log_session': ('notify_log', 'session_key, rating_key, user_id'),
    'idx_notify_log_timestamp': ('notify_log', 'timestamp'),
    'idx_notify_log_action_tag': ('notify_log', 'notify_action, tag'),
    'idx_notify_log_notifier_id': ('notify_log', 'notifier_id, timestamp'),
    'idx_user_login_jwt_token': ('user_login', 'jwt_token'),
    'idx_user_login_ip_address': ('user_login', 'ip_address, timestamp'),
    'idx_recently_added_rating_key': ('recently_added', 'rating_key'),
}
REMOVED_INDICES = {'idx_session_history_media_type', 'idx_session_history_user_id', 'idx_session_history_section_id'}
ORIGINAL_TABLE_SQL_SHA256 = {'cloudinary_lookup': '67bc14cd73ed3532b91d0ef546f6ccbff7247a7c6dc84fec5ef2b38dd08be14a',
 'exports': '02f7a7d17da377d3db050f25c81540162cdfbcaadbdd78c40c97b277582b1991',
 'image_hash_lookup': 'e5edb7e5ed2366ee72e828425fedfc62194ab3b3a04fcd249dcc2643ddc916a6',
 'imgur_lookup': '157fb34a3a00f963d0c675b47090fccd49557c41a86d21d61245139473bdf5d0',
 'library_sections': '437ff790be6fc0e0eecf8bba010d954cc0370481a3b57a5f4c3f14031a869018',
 'mobile_devices': '56b13112fb0e9310723eed05d61b01cad993df9cd11367164633391c1b5a985a',
 'musicbrainz_lookup': '6b3225f1be010579c5177d5e4ca1408c961e2d96db59e99a3e94406283bd0669',
 'newsletter_log': '02ae9aef8d54cdebb144b88882f6703e4eae75aef0c8b2b1bfdd22b5f02c552f',
 'newsletters': 'cc58c3e438db1bacd4d4eec24edcf104be4597f61a10a4568f86b61ffc94bb68',
 'notifiers': '200c2cef47dae86deabf5f0f0cdf6c9978cb7fdc30214efee93fb27a09bec5c4',
 'notify_log': '3f78e768504ba9fbeb08bdf82ae5e7a35eba7e4b04d578881e3d1af736674f7a',
 'recently_added': '1660a72c155b723c0b013189dfd1ca2a26e0c1a264cdac928a68a9f16c0b013f',
 'session_history': 'd242462de3bfc5a9c9685fb5f8c061b84f3f4976ed61239e267ca320ab58a7b9',
 'session_history_media_info': '28c148643dbc9aba22518f0de15c5b0d6ea9b877eb16302c1e2814b55c6f4663',
 'session_history_metadata': '78518fb8d143272dee17da6819343471bbf02506246f29f241d270e49f926555',
 'sessions': 'af36abda3e6ee278138c09d0f5fd36de475e157cd49d08f12b48a3557167986e',
 'sessions_continued': '6b7c2c8daab59238f17611414d55cf191b40ce1a087b84222b89309e03248215',
 'sqlite_sequence': '4cb1eaf14467f226196148cb5688569660cb290d414bae4c1c450b149b62befd',
 'sqlite_stat1': 'f3e5b16b86f359c3f77fe5635c1ed86b1b60e7d6dbe6211c13063787c94f6777',
 'themoviedb_lookup': '7a31454e3224f3a3d3c69c5a2c9c451c38d305c3dffd2f8929fdfbaedd7c7d0d',
 'tvmaze_lookup': 'f1e2cc9be01e8bb17712af5ab3cf7b1b3422a51a979c6518f383bcee0f03de10',
 'user_login': 'd3eb0ffe862f0295855a8c69f4db6371c883d27d4ca89e7ad846cddfb27fc8ca',
 'users': '5c07bd2fa01b152541747cff376eac069c8d2ce2e45acff5cf2661b6ac48797b',
 'version_info': '28a824b366579423d118387c4c019b9e918d0d2e4e78a59fc95cd703af71523a'}
ORIGINAL_TABLE_INFO_SHA256 = {'cloudinary_lookup': 'c283838211c93c37b8b7fb87f5691e5e4a029ba877ae4fa3c980c42472c496da',
 'exports': '0836bf851b5d025f1df34974449248e93ae3a323110f7a21188d94680a47546c',
 'image_hash_lookup': '613887a4d32868c73d6a8163b38781d3211d4dd6a31281faed7bb4a100f0d0b3',
 'imgur_lookup': 'd609aa2a0efe824d713e1a4ccbdba12312c559f90a0a266087d15d92f9560849',
 'library_sections': '34916aa8ef5f4068ea0368141890f52aa34644dd10008c55733aac53aed6886f',
 'mobile_devices': '530e34b2d0f3c66830057324fb747d3d6038204bf9761329ef5dd4beb213035c',
 'musicbrainz_lookup': '14ef19684b7d8fa53d86700b125601187872f2880ea177bc6eaa6b687aaf9040',
 'newsletter_log': '9ae2b05c16c50273a1c4905dfec054b763eacf89dffe6673119b144e0d57de1a',
 'newsletters': 'a87e05075cb4ee5e42ed42ede732490251216992e64a967108a65462c6c0edf5',
 'notifiers': '9c5b4627e7971964534965b7f54fd5fa9df6ea258f5f250d7caf163a84eb1795',
 'notify_log': '8359934e539f08958a25d33411bb284ccab07ab3dc64b6f8d91d68dc0d6a6f30',
 'recently_added': 'af0a4831fa842367a66528e54add87f219ea09d03727e1a3b04162b1aed273ce',
 'session_history': '45eb58d6db93b0931c9569c585951c1fdce16bb848c33151b8df1e600aa865b3',
 'session_history_media_info': 'be68d10bd0d6c45bfbe7030277d36818772b4db47fab09b32cba8fae30d6dd95',
 'session_history_metadata': '88753f803f69f144820ac31b055b386fdce00b7c8a733e222c48f60ee840111b',
 'sessions': '7aaba55cc7d4dc0e50c96fb62e1383177dbc09a713db9862de2c27108e57ae58',
 'sessions_continued': 'e61784d6c3c7d6aa713f59a10a0512b4e32e266c86f9c9b6d2a077b5a208e45a',
 'sqlite_sequence': '07626ce031aaaee84a3366dbb14fbb34175d32b21fd996c1cfc9b66aa936d279',
 'sqlite_stat1': '5f02e18fc38f783257cc1f6cbdf164971aecc5422955b082e37901ba70344753',
 'themoviedb_lookup': 'f5986781c7dcda0d7b093a8987a45edd0195a4684cf6663470e41510c6a93740',
 'tvmaze_lookup': '56c1e319e3eb222cff7fa16e17aa81f6a88be66ca9774ddc910761cd4f694e76',
 'user_login': '27fee97be6e7cfb62c2b89536735bf8e995bccf15bd1013940da2e9b9cabeb3d',
 'users': 'dbb13ca631c7be7ae1ad9ec10d5a66b6fd754b13693653907e5adbd6ec9a6f57',
 'version_info': '70e4b75c7bf65018d15b60331a03ae48cec32a3d9608f240862f519530ab5b64'}
LOG_FILES = {'logs/tautulli.log', 'logs/tautulli_api.log', 'logs/plex_websocket.log', 'logs/plexapi.log'}
ROTATION_FAMILY = ['logs/plex_websocket.log' + ('.' + str(i) if i else '') for i in range(6)]
LOGGER_SOURCE_SHA256 = 'd021055900d76a04c8855760f7e741c2f4f9fafab3af46a754624d3fbbaa3555'


def check(ok):
    if not ok:
        raise ValueError('tautulli_state_refused')


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def mac(key, domain, value):
    return hmac.new(key, compact(['tautulli-state-v1', domain, value]), hashlib.sha256).hexdigest()


def quoted(value):
    return '"' + value.replace('"', '""') + '"'


def cell(value):
    if value is None: return ['null']
    if isinstance(value, int): return ['int', str(value)]
    if isinstance(value, float): return ['float', value.hex()]
    if isinstance(value, str):
        check(len(value.encode()) <= MAX_VALUE); return ['text', value]
    if isinstance(value, bytes):
        check(len(value) <= MAX_VALUE); return ['blob', base64.b64encode(value).decode()]
    raise ValueError('tautulli_value_type')


def normal_sql(sql):
    return ' '.join(sql.replace(' IF NOT EXISTS ', ' ').split()) if sql else None


def cold_user_avatars(path):
    """Private RAM-only inverse values; never serialize these into a receipt."""
    with sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        rows = c.execute('SELECT id,user_id,thumb,custom_avatar_url FROM users ORDER BY id').fetchall()
    check(0 < len(rows) <= 1000 and len({r[0] for r in rows}) == len(rows))
    check(all(type(r[0]) is int and all(v is None or isinstance(v, (str, int)) for v in r)
              and all(not isinstance(v, str) or len(v.encode()) <= 8192 for v in r) for r in rows))
    return rows


def plex_avatar_evidence(key, domain):
    """Run only in the existing writer: two verified HTTPS GETs, no app imports."""
    import urllib.request
    import xml.etree.ElementTree as ET
    check(hashlib.sha256(Path('/app/plexpy/users.py').read_bytes()).hexdigest() ==
          '3477e714d83e366220a095c27f90ed3f818bf06949bb702cb5172baf3e67dbf3')
    c = configparser.ConfigParser(interpolation=None, strict=True)
    c.read('/config/config.ini', encoding='utf-8-sig')
    token = c.get('PMS', 'pms_token').strip().strip('"\'')
    check(token and '\n' not in token and '\r' not in token)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    avatars = {}; observations = []
    for endpoint, tag in [('/users/account', 'user'), ('/api/users', 'User')]:
        request = urllib.request.Request('https://plex.tv' + endpoint,
                                         headers={'X-Plex-Token': token}, method='GET')
        with opener.open(request, timeout=20) as response:
            raw = response.read(4 * 1024 ** 2 + 1)
            check(response.status == 200 and len(raw) <= 4 * 1024 ** 2)
        root = ET.fromstring(raw)
        elements = [root] if root.tag == tag else list(root.iter(tag))
        check(len(elements) <= 1000)
        for user in elements:
            uid = user.get('id', ''); thumb = user.get('thumb', '')
            check(uid.isdigit() and 0 < int(uid) < 2 ** 63 and len(thumb.encode()) <= 8192)
            value = mac(key, domain, ['plex-avatar', int(uid), thumb])
            check(uid not in avatars or avatars[uid] == value)
            avatars[uid] = value
        observations.append({'endpoint': endpoint, 'status': 200, 'tls_verified': True,
                             'account_elements': len(elements)})
    check(avatars)
    return {'avatars_hmac': avatars, 'observations': observations,
            'users_source_sha256': '3477e714d83e366220a095c27f90ed3f818bf06949bb702cb5172baf3e67dbf3'}


def fingerprint(path, key, domain, selected=None, live=False, avatar_projection=None, avatar_evidence=None):
    """Every table/old cell; exact source transformations are separate evidence."""
    check(selected is None or live)
    deadline = time.monotonic() + 90
    path = Path(path)
    private_copy = None
    closed_wal_copy = False
    # A closed WAL database can have no -wal/-shm files. SQLite cannot create
    # its required shared-memory file on the read-only PVC. Copy only that
    # closed, stable case into private RAM; never use immutable=1 or write the PVC.
    if live and not any(Path(str(path) + suffix).exists() for suffix in ['-wal', '-shm']):
        check(any(line.split()[1:3] == ['/dev/shm', 'tmpfs']
                  for line in Path('/proc/mounts').read_text().splitlines()))
        info = path.lstat()
        check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
              and 2 * info.st_size + 1024 ** 2 <= MAX_SQLITE)
        private_copy = tempfile.TemporaryDirectory(prefix='tautulli-read-', dir='/dev/shm')
        target = Path(private_copy.name) / 'tautulli.db'
        def identity(s):
            return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
        try:
            copied = 0
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as old, target.open('xb') as new:
                check(identity(os.fstat(old.fileno())) == identity(info))
                for block in iter(lambda: old.read(1024 ** 2), b''):
                    copied += len(block)
                    check(copied <= info.st_size and time.monotonic() < deadline)
                    new.write(block)
                check(copied == info.st_size and identity(os.fstat(old.fileno())) == identity(info))
            target.chmod(0o600)
            check(identity(path.lstat()) == identity(info)
                  and not any(Path(str(path) + suffix).exists() for suffix in ['-wal', '-shm']))
            closed_wal_copy = True
            path = target
        except BaseException:
            private_copy.cleanup()
            raise
    source = None
    memory = expected = None
    try:
        source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5, isolation_level=None)
        source.execute('PRAGMA query_only=ON'); source.execute('PRAGMA busy_timeout=5000')
        source.execute('PRAGMA temp_store=MEMORY'); source.execute('BEGIN')
        pages = source.execute('PRAGMA page_count').fetchone()[0]
        page_size = source.execute('PRAGMA page_size').fetchone()[0]
        # The live statistics verifier needs two snapshots at once.
        check(pages * page_size * (2 if live else 1) <= MAX_SQLITE)
        connection = source
        if live:
            memory = sqlite3.connect(':memory:', isolation_level=None)
            def progress(status, remaining, total):
                check(time.monotonic() < deadline and total * page_size * 2 <= MAX_SQLITE)
            source.backup(memory, pages=64, progress=progress, sleep=0.05)
            source.rollback(); source.close(); source = None; connection = memory
            if private_copy is not None:
                private_copy.cleanup(); private_copy = None
            connection.execute('PRAGMA temp_store=MEMORY')
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
        check(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
        master = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('index','trigger','view') ORDER BY type,name").fetchall()
        structure = [[t, n, table, normal_sql(sql)] for t, n, table, sql in master]
        names = sorted(r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        check(set(names) == set(ORIGINAL_TABLE_INFO_SHA256))
        if selected is None:
            check(not set(NEW_INDEX_COLUMNS) & {r[1] for r in structure})
            check(REMOVED_INDICES <= {r[1] for r in structure})
        else:
            check(names == sorted(selected['tables']))
            wanted = [r for r in selected['structure'] if not (r[0] == 'index' and r[1] in REMOVED_INDICES)]
            wanted += [['index', name, table, 'CREATE INDEX ' + name + ' ON ' + table + ' (' + cols + ')']
                       for name, (table, cols) in NEW_INDEX_COLUMNS.items()]
            check(sorted(structure) == sorted(wanted))
        stats = connection.execute('SELECT tbl,idx,stat FROM sqlite_stat1 ORDER BY tbl,idx,stat').fetchall()
        if selected is not None:
            # Source dbcheck executes these exact SQL statements. Recompute on a
            # separate RAM copy, never the read-only source or the observed copy.
            expected = sqlite3.connect(':memory:', isolation_level=None)
            connection.backup(expected, pages=64, progress=progress, sleep=0.05)
            expected.execute('PRAGMA temp_store=MEMORY')
            expected.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
            expected.execute('PRAGMA analysis_limit=400'); expected.execute('ANALYZE')
            check(stats == expected.execute('SELECT tbl,idx,stat FROM sqlite_stat1 ORDER BY tbl,idx,stat').fetchall())
            expected.close(); expected = None
        connection.execute('PRAGMA query_only=ON')
        if live: connection.execute('BEGIN')
        tables = {}; encoded = total_rows = 0; avatar_changes = []
        for name in names:
            check(time.monotonic() < deadline)
            info = [list(r) for r in connection.execute('PRAGMA table_xinfo(' + quoted(name) + ')')]
            columns = [r[1] for r in info]
            check(0 < len(columns) <= 256 and len(columns) == len(set(columns)))
            additions = NEW_COLUMNS.get(name, [])
            if selected is None:
                check(not {r[0] for r in additions} & set(columns))
                check(hashlib.sha256(compact(info)).hexdigest() == ORIGINAL_TABLE_INFO_SHA256[name])
                original_info = info; original_columns = columns
                ddl = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
                check(hashlib.sha256(ddl.encode()).hexdigest() == ORIGINAL_TABLE_SQL_SHA256[name])
                expected_ddl = ddl
                if additions:
                    schema = sqlite3.connect(':memory:')
                    try:
                        schema.execute(ddl)
                        for col, typ, default in additions:
                            schema.execute('ALTER TABLE ' + quoted(name) + ' ADD COLUMN ' + col + ' ' + typ + (' DEFAULT ' + default if default is not None else ''))
                        expected_ddl = schema.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0]
                    finally: schema.close()
                expected_schema_sha256 = hashlib.sha256(expected_ddl.encode()).hexdigest()
                if name in {'mobile_devices', 'exports', 'image_hash_lookup'}:
                    check(connection.execute('SELECT count(*) FROM ' + quoted(name)).fetchone()[0] == 0)
            else:
                original_info = selected['tables'][name]['table_info']; original_columns = selected['tables'][name]['columns']
                expected_schema_sha256 = selected['tables'][name]['expected_live_schema_sha256']
                ddl = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
                check(hashlib.sha256(ddl.encode()).hexdigest() == expected_schema_sha256)
                check(info == original_info + [[len(original_info) + i, col, typ, 0, default, 0, 0]
                                               for i, (col, typ, default) in enumerate(additions)])
                for col, typ, default in additions:
                    predicate = quoted(col) + (' IS NOT NULL' if default is None else ' IS NOT 0')
                    check(connection.execute('SELECT count(*) FROM ' + quoted(name) + ' WHERE ' + predicate).fetchone()[0] == 0)
            version = connection.execute("SELECT value FROM version_info WHERE key='version'").fetchall()
            check(version == [(NEW_VERSION if selected is not None else OLD_VERSION,)])
            projections = [quoted(c) for c in original_columns]
            if selected is not None and name == 'version_info':
                projections[original_columns.index('value')] = "CASE WHEN key='version' THEN 'v2.16.1' ELSE value END"
            sql = 'SELECT ' + ','.join(projections) + ' FROM ' + quoted(name) + ' ORDER BY ' + ','.join(str(i+1) for i in range(len(projections)))
            rows_mac = hmac.new(key, compact(['table', domain, name, original_columns]), hashlib.sha256)
            field_macs = {c: hmac.new(key, compact(['column', domain, name, c]), hashlib.sha256) for c in original_columns}
            count = 0
            for row in connection.execute(sql):
                if selected is not None and name == 'users' and avatar_projection is not None:
                    # refresh_users() changes Plex-derived thumbs and only a
                    # missing/default custom avatar. Preserve actual custom choices.
                    positions = {col: original_columns.index(col) for col in ['id','user_id','thumb','custom_avatar_url']}
                    old = {r[0]: r for r in avatar_projection}.get(row[positions['id']])
                    check(old is not None and str(old[1]) == str(row[positions['user_id']]))
                    current_thumb, current_custom = row[positions['thumb']], row[positions['custom_avatar_url']]
                    if (current_thumb, current_custom) != (old[2], old[3]):
                        uid = int(old[1])
                        check(avatar_evidence is not None and avatar_evidence['avatars_hmac'].get(str(uid)) ==
                              mac(key, domain, ['plex-avatar', uid, current_thumb]))
                        check(current_custom == (current_thumb if not old[3] or old[3] == old[2] else old[3]))
                        avatar_changes.append({'user_id': uid, 'source_derived_plex_avatar_verified': True,
                                               'custom_choice_preserved': bool(old[3] and old[3] != old[2]),
                                               'old_thumb_hmac': mac(key, domain, ['avatar-value', old[2]]),
                                               'current_thumb_hmac': mac(key, domain, ['avatar-value', current_thumb])})
                        row = list(row)
                        row[positions['thumb']], row[positions['custom_avatar_url']] = old[2], old[3]
                values = [cell(v) for v in row]; raw = compact(values)
                encoded += len(raw); count += 1; total_rows += 1
                check(encoded <= MAX_ENCODED and total_rows <= MAX_ROWS and time.monotonic() < deadline)
                rows_mac.update(len(raw).to_bytes(8, 'big') + raw)
                for col, value in zip(original_columns, values):
                    b = compact(value); field_macs[col].update(len(b).to_bytes(8, 'big') + b)
            table = {'expected_live_schema_sha256': expected_schema_sha256, 'columns': original_columns, 'table_info': original_info, 'count': count,
                     'all_rows_hmac': rows_mac.hexdigest(), 'per_column_hmac': {c: m.hexdigest() for c, m in field_macs.items()}}
            tables[name] = table
            if selected is not None and name != 'sqlite_stat1': check(table == selected['tables'][name])
        return {'quick_check': 'ok', 'tables': tables, 'structure': structure,
                'key_binding': mac(key, domain, 'key-binding'), 'sqlite_version': sqlite3.sqlite_version,
                'snapshot_bytes': pages * page_size, 'live_backup_to_memory': live,
                'closed_wal_stable_private_ram_copy_used': closed_wal_copy,
                'source_verified_plex_avatar_changes': avatar_changes,
                'statistics_recomputed_in_independent_ram_copy': selected is not None,
                'version_transition_verified': selected is not None,
                'encoded_cell_bytes': encoded, 'total_rows': total_rows}
    finally:
        for c in [source, memory, expected]:
            if c is not None: c.close()
        if private_copy is not None: private_copy.cleanup()


def configuration(path, key, domain, selected=None):
    """Canonical INI section/key/string values; no app imports or config writes."""
    p = Path(path); before = p.stat(); raw = p.read_bytes(); after = p.stat()
    check(len(raw) <= 8 * 1024 ** 2 and (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns))
    c = configparser.ConfigParser(interpolation=None, strict=True, empty_lines_in_values=False)
    c.optionxform = str; c.read_string(raw.decode('utf-8-sig')); check(not c.defaults())
    values = {(s, k): v for s in c.sections() for k, v in c.items(s)}
    # Authenticated original config and pinned candidate both use version22.
    # Do not waive historical upgrades or
    # newly generated API/JWT/Plex UUID credentials as migration differences.
    check(values.get(('Advanced', 'config_version')) == '22')
    for k in ['api_key', 'jwt_secret', 'pms_uuid']:
        section = 'PMS' if k.startswith('pms_') else 'General' if k == 'api_key' else 'Advanced'
        check(values.get((section, k), '').strip('"\' '))
    check(values.get(('Advanced', 'jwt_update_secret'), '0') == '0')
    check(values.get(('General', 'log_dir')) == '/config/logs')
    entries = {mac(key, domain, ['config-key', s, k]): mac(key, domain, ['config-value', s, k, v]) for (s, k), v in values.items()}
    permitted = {mac(key, domain, ['config-key', s, k]): mac(key, domain, ['config-value', s, k, v]) for (s, k), v in NEW_CONFIG.items()}
    if selected is None:
        check(not set(permitted) & set(entries))
    else:
        # CONFIG.write preserves unknown/retired settings as well as known ones.
        # initialize() sets this single UI flag to1 on a release transition.
        flag = mac(key, domain, ['config-key', 'General', 'update_show_changelog'])
        check(flag in selected['entries_hmac'])
        permitted[flag] = mac(key, domain, ['config-value', 'General', 'update_show_changelog', '1'])
        check(entries == selected['entries_hmac'] | permitted)
    return {'entries_hmac': entries, 'key_count': len(entries), 'canonical_hmac': mac(key, domain, sorted(entries.items())),
            'file_sha256_hmac': mac(key, domain, ['config-bytes', hashlib.sha256(raw).hexdigest()]),
            'original_values_preserved_except_source_changelog_flag': selected is not None,
            'three_exact_default_additions': selected is not None}


def files_from_manifest(manifest, key, domain):
    check(manifest['schema_version'] == 1 and not manifest['excluded_new_paths'])
    entries = {}
    for name, row in manifest['entries'].items():
        check(name == 'data-0' or name.startswith('data-0/'))
        relative = name.removeprefix('data-0').lstrip('/')
        if relative in DATABASE_FILES: check(row['kind'] == 'file'); continue
        fields = ['kind', 'mode', 'uid', 'gid']
        if row['kind'] == 'file': fields += ['bytes', 'sha256']
        elif row['kind'] == 'symlink': fields += ['link']
        else: check(row['kind'] == 'directory')
        digest = {k: row[k] for k in fields}
        entries[mac(key, domain, ['path', relative])] = {
            'entry_hmac': mac(key, domain, ['entry', relative, digest]),
            'metadata_hmac': mac(key, domain, ['metadata', relative, {k: row[k] for k in ['kind','mode','uid','gid']}]),
            'content_sha256_hmac': mac(key, domain, ['content', row['sha256']]) if row['kind'] == 'file' else None,
            'bytes': row.get('bytes'),
            'class': 'config' if relative == 'config.ini' else 'lock' if relative in ['release.lock','version.lock'] else 'version-cache' if relative == 'cache/github_version.json' else 'rotating-log' if relative in ROTATION_FAMILY else 'append-log' if relative in LOG_FILES else 'exact'}
    return {'entries_hmac': entries, 'all_files_equivalent_claimed': False}


def version_cache(path, key, domain, selected=None):
    """Pinned versioncheck.github_cache metadata; every GitHub data field stays."""
    p = Path(path); before = p.stat(); raw = p.read_bytes(); after = p.stat()
    check(len(raw) <= 65536 and (before.st_ino,before.st_size,before.st_mtime_ns) ==
          (after.st_ino,after.st_size,after.st_mtime_ns))
    data = json.loads(raw)
    check(set(data) == {'github_data','_cache_time','_release_version'}
          and type(data['_cache_time']) is int and 0 <= data['_cache_time'] <= time.time() + 5
          and data['_release_version'] == (NEW_VERSION if selected else OLD_VERSION))
    result = {'github_data_hmac': mac(key, domain, ['github-version-data', data['github_data']]),
              'cache_time': data['_cache_time'], 'release_version': data['_release_version'],
              'file_content_hmac': mac(key, domain, ['content', hashlib.sha256(raw).hexdigest()])}
    if selected is not None:
        check(result['github_data_hmac'] == selected['github_data_hmac']
              and result['cache_time'] >= selected['cache_time'])
    return result


def live_files(root, key, domain, baseline, cache_baseline=None):
    """No broad runtime exclusions: only exact startup locks and same-log append."""
    root = Path(root); check(root.resolve() == root and root.is_dir())
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    device = os.fstat(root_fd).st_dev
    entries = {}; prefixes = {}; total = 0; deadline = time.monotonic() + 120
    def identity(s): return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    def visit(parent_fd, leaf, name, depth):
        nonlocal total
        check(time.monotonic() < deadline and len(entries) < 4096 and depth <= 64)
        info = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False); check(info.st_dev == device)
        relative = name.removeprefix('data-0').lstrip('/')
        if relative in DATABASE_FILES: check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1); return
        row = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
        if stat.S_ISDIR(info.st_mode):
            row['kind'] = 'directory'
            fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                check(identity(os.fstat(fd)) == identity(info))
                children = []
                with os.scandir(fd) as listing:
                    for child in listing:
                        check(time.monotonic() < deadline and len(children) + len(entries) < 4096)
                        children.append(child.name)
                for child in sorted(children): visit(fd, child, name + '/' + child, depth + 1)
                check(identity(os.fstat(fd)) == identity(os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)) == identity(info))
            finally: os.close(fd)
        elif stat.S_ISLNK(info.st_mode): row.update(kind='symlink', link=os.readlink(leaf, dir_fd=parent_fd))
        else:
            check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
            total += info.st_size; check(total <= 4 * 1024 ** 3)
            old = baseline['entries_hmac'].get(mac(key, domain, ['path', relative]))
            rotating = relative in ROTATION_FAMILY
            base_log = baseline['entries_hmac'].get(mac(key, domain, ['path', ROTATION_FAMILY[0]]))
            prefix_limit = base_log['bytes'] if rotating else old['bytes'] if old and relative in LOG_FILES else 0
            digest = hashlib.sha256(); prefix = hashlib.sha256(); consumed = 0
            with os.fdopen(os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd), 'rb') as stream:
                check(identity(os.fstat(stream.fileno())) == identity(info))
                remaining = info.st_size
                while remaining:
                    block = stream.read(min(1024 ** 2, remaining))
                    check(block); remaining -= len(block)
                    check(time.monotonic() < deadline); digest.update(block)
                    if consumed < prefix_limit: prefix.update(block[:prefix_limit-consumed])
                    consumed += len(block)
                after = os.fstat(stream.fileno()); named = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
                if relative in LOG_FILES:
                    # Capture the initial-length prefix while the known logger
                    # appends. Rename/truncate/owner/mode changes still refuse.
                    check(after.st_dev == named.st_dev == info.st_dev and
                          after.st_ino == named.st_ino == info.st_ino and
                          after.st_size == named.st_size and after.st_size >= info.st_size and
                          (after.st_mode, after.st_uid, after.st_gid) == (info.st_mode, info.st_uid, info.st_gid))
                else:
                    check(identity(after) == identity(named) == identity(info))
            row.update(kind='file', bytes=info.st_size, sha256=digest.hexdigest())
            if rotating or old and relative in LOG_FILES:
                if not rotating: check(consumed >= prefix_limit)
                prefixes[mac(key, domain, ['path', relative])] = mac(key, domain, ['content', prefix.hexdigest()]) if consumed >= prefix_limit else None
            if relative in ['release.lock', 'version.lock']:
                expected = (NEW_VERSION if relative == 'release.lock' else NEW_COMMIT).encode()
                check(row['bytes'] == len(expected) and row['sha256'] == hashlib.sha256(expected).hexdigest())
        entries[name] = row
    try: visit(root_fd, '.', 'data-0', 0)
    finally: os.close(root_fd)
    check(len(entries) <= 4096)
    current = files_from_manifest({'schema_version': 1, 'entries': entries, 'excluded_new_paths': []}, key, domain)
    old = baseline['entries_hmac']; new = current['entries_hmac']; check(set(old) == set(new))
    cache_key = mac(key, domain, ['path','cache/github_version.json'])
    check(cache_baseline is not None and hashlib.sha256(Path('/app/plexpy/versioncheck.py').read_bytes()).hexdigest() ==
          '292e800a55d705c03a5b9f724e7776d9fa5a337e93d6f79a9debf17e0cc9058a')
    cache = version_cache(root/'cache/github_version.json', key, domain, cache_baseline)
    check(cache['file_content_hmac'] == new[cache_key]['content_sha256_hmac'])
    family = [mac(key, domain, ['path', p]) for p in ROTATION_FAMILY]
    check(all(p in old and p in new for p in family))
    rotations = None
    for number in range(6):
        if prefixes.get(family[number]) != old[family[0]]['content_sha256_hmac']: continue
        if any(new[family[i+number]]['content_sha256_hmac'] != old[family[i]]['content_sha256_hmac']
               or new[family[i+number]]['bytes'] != old[family[i]]['bytes'] for i in range(1,6-number)): continue
        if any(new[family[i]]['bytes'] > 5000000 for i in range(number)): continue
        rotations = number; break
    check(rotations is not None)
    check(hashlib.sha256(Path('/app/plexpy/logger.py').read_bytes()).hexdigest() == LOGGER_SOURCE_SHA256)
    changed = []
    for path, original in old.items():
        now = new[path]; check(original['class'] == now['class'] and original['metadata_hmac'] == now['metadata_hmac'])
        if original['entry_hmac'] == now['entry_hmac']: continue
        check(original['class'] in ['config', 'lock', 'append-log', 'rotating-log', 'version-cache'])
        if original['class'] == 'append-log': check(prefixes[path] == original['content_sha256_hmac'])
        changed.append({'path_hmac': path, 'class': original['class'], 'original_entry_hmac': original['entry_hmac'], 'current_entry_hmac': now['entry_hmac']})
    current.update(changes=changed, all_other_entries_identical=True, original_log_prefixes_retained=True,
                   github_version_cache=cache,
                   websocket_rotation={'rotations': rotations, 'logger_source_sha256': LOGGER_SOURCE_SHA256,
                                       'original_backups_replaced_in_live_retention': rotations,
                                       'all_original_logs_retained_in_authenticated_cold_archive': True})
    return current
