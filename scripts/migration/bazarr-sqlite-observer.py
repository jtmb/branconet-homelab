#!/usr/bin/env python3
"""Standalone Bazarr SQL/API observer; no application imports or explicit writes."""
import ast
from collections import Counter
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import re
import signal
import sqlite3
import stat
import sys
import time
import urllib.error
import urllib.request

MAX_ROWS = 100000
MAX_VALUE = 8 * 1024 ** 2
MAX_BYTES = 128 * 1024 ** 2
MAX_SECONDS = 120
TABLES = {
    'table_shows': ('sonarrSeriesId', ['tvdbId', 'alternativeTitles', 'audio_language', 'created_at_timestamp', 'ended', 'fanart', 'imdbId', 'lastAired', 'monitored', 'overview', 'path', 'poster', 'profileId', 'seriesType', 'sonarrSeriesId', 'sortTitle', 'tags', 'title', 'year']),
    'table_episodes': ('sonarrEpisodeId', ['absoluteEpisode', 'audio_codec', 'audio_language', 'created_at_timestamp', 'episode', 'episode_file_id', 'file_size', 'format', 'monitored', 'path', 'resolution', 'sceneName', 'season', 'sonarrEpisodeId', 'sonarrSeriesId', 'title', 'video_codec']),
    'table_movies': ('radarrId', ['alternativeTitles', 'audio_codec', 'audio_language', 'created_at_timestamp', 'fanart', 'file_size', 'format', 'imdbId', 'monitored', 'movie_file_id', 'overview', 'path', 'poster', 'profileId', 'radarrId', 'resolution', 'sceneName', 'sortTitle', 'tags', 'title', 'tmdbId', 'video_codec', 'year']),
    'table_history': ('id', ['id', 'action', 'description', 'language', 'provider', 'score', 'sonarrEpisodeId', 'sonarrSeriesId', 'subs_id', 'subtitles_path', 'timestamp', 'video_path', 'matched', 'not_matched', 'upgradedFromId']),
    'table_history_movie': ('id', ['id', 'action', 'description', 'language', 'provider', 'radarrId', 'score', 'subs_id', 'subtitles_path', 'timestamp', 'video_path', 'matched', 'not_matched', 'upgradedFromId']),
    'table_languages_profiles': ('profileId', ['profileId', 'cutoff', 'originalFormat', 'items', 'name', 'mustContain', 'mustNotContain', 'tag']),
    'table_settings_languages': ('code3', ['code3', 'code2', 'code3b', 'enabled', 'name']),
    'table_blacklist': ('id', ['id', 'language', 'provider', 'sonarr_episode_id', 'sonarr_series_id', 'subs_id', 'timestamp']),
    'table_blacklist_movie': ('id', ['id', 'language', 'provider', 'radarr_id', 'subs_id', 'timestamp']),
    'table_settings_notifier': ('name', ['name', 'enabled', 'url']),
}


class Refused(Exception):
    pass


def need(value, reason):
    if not value:
        raise Refused(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def legacy_subtitle(value, episode_id=None, series_id=None, movie_id=None):
    need(isinstance(value, (list, tuple)) and len(value) in [2, 3], 'legacy_subtitle_tuple_shape')
    language, path = value[:2]
    size = value[2] if len(value) == 3 else None
    need(isinstance(language, str) and len(language) <= 64, 'legacy_subtitle_language_shape')
    parts = language.split(':')
    need(1 <= len(parts) <= 2 and bool(re.fullmatch(r'[A-Za-z0-9_-]{2,32}', parts[0])), 'legacy_subtitle_language_ambiguous')
    need(len(parts) == 1 or parts[1] in ['hi', 'forced'], 'legacy_subtitle_suffix_ambiguous')
    need(path is None or isinstance(path, str) and len(path) <= 8192, 'legacy_subtitle_path_shape')
    need(size is None or type(size) is int and size >= 0, 'legacy_subtitle_size_shape')
    return {'language': parts[0], 'hi': len(parts) == 2 and parts[1] == 'hi',
            'forced': len(parts) == 2 and parts[1] == 'forced', 'path': path, 'size': size,
            'episode_id': episode_id, 'series_id': series_id, 'movie_id': movie_id}


def observe(mode, key):
    path = Path('/config/db/bazarr.db')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not path.is_symlink() and info.st_size <= 256 * 1024 ** 2, 'database_path_or_size')
    deadline = time.monotonic() + MAX_SECONDS
    used, total_rows = 0, 0

    def mac(value):
        nonlocal used
        data = canonical(value)
        need(len(data) <= MAX_VALUE, 'database_value_limit')
        used += len(data)
        need(used <= MAX_BYTES, 'database_aggregate_value_limit')
        return hmac.new(key, data, hashlib.sha256).hexdigest()

    def count_row():
        nonlocal total_rows
        total_rows += 1
        need(total_rows <= MAX_ROWS and time.monotonic() < deadline, 'database_rows_or_time_limit')

    db = sqlite3.connect('file:/config/db/bazarr.db?mode=ro', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
    try:
        db.execute('BEGIN')
        need([r[0] for r in db.execute('PRAGMA quick_check')] == ['ok'], 'sqlite_quick_check_failed')
        revisions = [r[0] for r in db.execute('SELECT version_num FROM alembic_version')]
        need(revisions == (['df76a4410347'] if mode == 'baseline' else ['537e9b4d10e3']), 'migration_revision')
        fingerprints, counts = {}, {}
        for table, (pk, fields) in TABLES.items():
            columns = {r['name'] for r in db.execute('PRAGMA table_info(' + table + ')')}
            need(set(fields) <= columns, 'required_database_columns_missing')
            if mode != 'baseline' and table in ['table_shows', 'table_movies', 'table_episodes']:
                need(('tvdbId' if table == 'table_episodes' else 'originalLanguage') in columns, 'new_migration_column_missing')
            selected = list(fields)
            if mode != 'baseline' and table in ['table_history', 'table_history_movie']:
                need('score_out_of' in columns, 'score_denominator_column_missing')
                selected.append('score_out_of')
            rows = {}
            for row in db.execute('SELECT ' + ','.join('"' + f + '"' for f in selected) + ' FROM ' + table):
                count_row()
                identity = row[pk]
                need(type(identity) in [int, str], 'database_row_identity')
                rid = mac({'table': table, 'primary_key': identity})
                need(rid not in rows, 'duplicate_database_identity')
                values = {f: row[f] for f in fields}
                if table in ['table_history', 'table_history_movie']:
                    denominator = None if row['score'] is None else 360 if table == 'table_history' else 120
                    values['score_out_of'] = denominator if mode == 'baseline' else row['score_out_of']
                rows[rid] = {f: mac({'type': type(v).__name__, 'value': v}) for f, v in values.items()}
            fingerprints[table] = rows
            counts[table] = len(rows)

        subtitles = Counter()
        collision_keys = set()
        for table, parent, new_table in [('table_episodes', 'sonarrEpisodeId', 'table_episodes_subtitles'),
                                         ('table_movies', 'radarrId', 'table_movies_subtitles')]:
            columns = {r['name'] for r in db.execute('PRAGMA table_info(' + table + ')')}
            if mode == 'baseline':
                need('subtitles' in columns, 'legacy_subtitle_column_missing')
                exists = db.execute('SELECT count(*) FROM sqlite_master WHERE type=? AND name=?', ('table', new_table)).fetchone()[0]
                if exists:
                    need(db.execute('SELECT count(*) FROM ' + new_table).fetchone()[0] == 0, 'unexpected_preexisting_new_subtitles')
                fields = [parent, 'subtitles'] + (['sonarrSeriesId'] if table == 'table_episodes' else [])
                for row in db.execute('SELECT ' + ','.join('"' + f + '"' for f in fields) + ' FROM ' + table):
                    raw = row['subtitles']
                    if raw is None:
                        continue
                    need(isinstance(raw, str) and len(raw.encode()) <= MAX_VALUE, 'legacy_subtitle_column_shape')
                    try:
                        values = ast.literal_eval(raw)
                    except (ValueError, SyntaxError, TypeError, RecursionError):
                        raise Refused('legacy_subtitles_literal_malformed') from None
                    need(isinstance(values, (list, tuple)), 'legacy_subtitles_collection_shape')
                    for value in values:
                        count_row()
                        semantic = legacy_subtitle(value, row[parent] if table == 'table_episodes' else None,
                                                   row['sonarrSeriesId'] if table == 'table_episodes' else None,
                                                   row[parent] if table == 'table_movies' else None)
                        # The migration can silently skip uniqueness collisions. Refuse them first.
                        collision = mac({k: v for k, v in semantic.items() if k != 'size'})
                        need(collision not in collision_keys, 'legacy_subtitle_uniqueness_collision')
                        collision_keys.add(collision)
                        subtitles[mac(semantic)] += 1
            else:
                if 'subtitles' in columns:
                    need(db.execute('SELECT count(*) FROM ' + table + ' WHERE subtitles IS NOT NULL').fetchone()[0] == 0, 'legacy_subtitle_column_not_cleared')
                wanted = ['language', 'hi', 'forced', 'path', 'size', parent] + (['sonarrSeriesId'] if table == 'table_episodes' else [])
                new_columns = {r['name'] for r in db.execute('PRAGMA table_info(' + new_table + ')')}
                need(set(wanted) <= new_columns, 'new_subtitle_table_schema')
                for row in db.execute('SELECT ' + ','.join('"' + f + '"' for f in wanted) + ' FROM ' + new_table):
                    count_row()
                    need(row['hi'] in [0, 1] and row['forced'] in [0, 1], 'subtitle_flags_shape')
                    semantic = {'language': row['language'], 'hi': bool(row['hi']), 'forced': bool(row['forced']),
                                'path': row['path'], 'size': row['size'],
                                'episode_id': row[parent] if table == 'table_episodes' else None,
                                'series_id': row['sonarrSeriesId'] if table == 'table_episodes' else None,
                                'movie_id': row[parent] if table == 'table_movies' else None}
                    subtitles[mac(semantic)] += 1
        foreign_keys = Counter()
        for row in db.execute('PRAGMA foreign_key_check'):
            count_row()
            foreign_keys[mac(list(row))] += 1
        return {'schema_version': 1, 'mode': mode, 'quick_check_passed': True,
                'migration_revision': revisions[0], 'fingerprints': fingerprints, 'counts': counts,
                'subtitle_fingerprints': dict(subtitles), 'subtitle_count': sum(subtitles.values()),
                'foreign_key_violations': dict(foreign_keys), 'foreign_key_violation_count': sum(foreign_keys.values()),
                'key_binding': mac('bazarr-qualification-key-v1'), 'database_bytes': info.st_size,
                'rows_observed': total_rows, 'scalar_bytes_hashed': used,
                'read_only_sqlite': True, 'application_imports': False}
    finally:
        db.rollback()
        db.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused('unexpected_application_redirect')


def observe_application(mode, key, target):
    # The image's vendored YAML parser is a library, not the application's config
    # module (whose import can validate/save settings or initialize other runtime).
    original_path = list(sys.path)
    try:
        sys.path.insert(0, '/app/bin/libs')
        import yaml
    finally:
        sys.path[:] = original_path
    path = Path('/config/config/config.yaml')
    need(path.is_file() and not path.is_symlink(), 'config_path')
    with path.open('rb') as stream:
        raw = stream.read(524289)
    need(len(raw) <= 524288, 'config_size_limit')
    config = yaml.safe_load(raw)
    need(isinstance(config, dict), 'config_shape')
    auth = config.get('auth', config.get('AUTH', {}))
    general = config.get('general', config.get('GENERAL', {}))
    need(isinstance(auth, dict) and isinstance(general, dict), 'config_sections')
    apikey = auth.get('apikey')
    need(isinstance(apikey, str) and bool(re.fullmatch(r'[A-Za-z0-9]{20,128}', apikey)), 'api_key_shape')
    need(general.get('port') == 6767, 'configured_port')
    base_path = general.get('base_url', '').rstrip('/')
    need(not base_path or bool(re.fullmatch(r'/[A-Za-z0-9/_-]+', base_path)), 'configured_base_path')
    address = ipaddress.ip_address(target)
    need(address.is_private and not address.is_loopback and not address.is_link_local, 'service_address')
    host = '[' + str(address) + ']' if address.version == 6 else str(address)
    base = 'http://' + host + ':6767' + base_path
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    total = 0

    def get(endpoint):
        nonlocal total
        request = urllib.request.Request(base + endpoint,
                                         headers={'X-API-KEY': apikey, 'Host': 'bazarr.branconet.lan', 'Accept': 'application/json'},
                                         method='GET')
        try:
            with client.open(request, timeout=15) as response:
                data = response.read(1024 * 1024 + 1)
                total += len(data)
                need(response.status == 200 and len(data) <= 1024 * 1024 and total <= 2 * 1024 * 1024, 'application_response_limit_or_status')
                return json.loads(data)
        except urllib.error.HTTPError as error:
            raise Refused('application_http_' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError):
            raise Refused('application_connection_or_timeout') from None

    status = get('/api/system/status')['data']
    expected = '1.5.6' if mode == 'baseline' else '1.6.2'
    need(status.get('bazarr_version') in [expected, 'v' + expected], 'application_version')
    need(status.get('database_migration') == ('df76a4410347' if mode == 'baseline' else '537e9b4d10e3'), 'api_migration_revision')
    health = get('/api/system/health')['data']
    need(isinstance(health, list), 'health_shape')

    def mac(value):
        return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()

    leaves = {}
    def flatten(value, route):
        need(len(route) <= 32 and len(leaves) < 4096, 'config_depth_or_leaf_limit')
        if isinstance(value, dict) and value:
            for field, child in value.items():
                need(isinstance(field, str), 'config_key_shape')
                flatten(child, route + [field])
        else:
            leaves[mac({'path': route})] = mac({'type': type(value).__name__, 'value': value})
    flatten(config, [])
    with path.open('rb') as stream:
        need(stream.read(524289) == raw, 'config_changed_during_observation')
    # Version reports may be cached by Bazarr. They are not a fresh Arr test.
    reported_arr = {}
    for name in ['sonarr', 'radarr']:
        enabled = general.get('use_' + name) is True
        version = status.get(name + '_version')
        known = isinstance(version, str) and version.strip().lower() not in ['', 'unknown', 'none', 'null']
        reported_arr[name] = {'enabled': enabled, 'reported_version_known': known,
                              'version': version if known and re.fullmatch(r'[v0-9.]+', version) else None}
    return {'version': expected, 'database_migration': status['database_migration'],
            'authentication_header_accepted': True, 'config_leaf_fingerprints': leaves,
            'config_leaf_count': len(leaves), 'health_issue_count': len(health),
            'reported_arr': reported_arr, 'fresh_arr_connection_verified': False,
            'api_bytes': total, 'get_only': True}


def main():
    need(len(sys.argv) == 3 and sys.argv[1] in ['baseline', 'after', 'restart'], 'observer_mode')
    raw = sys.stdin.buffer.read(66)
    need(re.fullmatch(b'[0-9a-f]{64}\n?', raw) is not None, 'stdin_key_shape')
    def expired(_signum, _frame):
        raise Refused('database_hard_deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(MAX_SECONDS)
    try:
        key = bytes.fromhex(raw.decode().strip())
        observation = observe(sys.argv[1], key)
        observation['application'] = observe_application(sys.argv[1], key, sys.argv[2])
        print(json.dumps(observation, sort_keys=True))
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status': 'refused', 'reason': 'database_observation_failed_raw_details_suppressed'}))
        raise SystemExit(1)
