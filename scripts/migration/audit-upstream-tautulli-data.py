#!/usr/bin/env python3
"""Compare complete cold/current SQL, including normal playback completion."""
import argparse
import collections
import datetime
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-tautulli-20261026'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()


def quote(name):return '"' + name.replace('"', '""') + '"'


def connect(path):
    assert path.resolve() == path and path.is_file() and path.stat().st_size <= 64 * 1024**2
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON');connection.execute('BEGIN')
    assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    assert connection.execute('PRAGMA foreign_key_check').fetchone() is None
    return connection


def rows(connection, name):
    columns = [r[1] for r in connection.execute('PRAGMA table_xinfo(' + quote(name) + ')')]
    return columns, connection.execute('SELECT * FROM ' + quote(name)).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['after', 'restart'], required=True)
    args = parser.parse_args();target = OUT / (args.phase + '-data-audit.json');assert not target.exists()
    original, current = OUT / 'cold-sql/tautulli.db', OUT / (args.phase + '-current.db')
    optimizer_source = original if args.phase == 'after' else OUT / 'after-current.db'
    paths = {original, current, optimizer_source};before = {str(p): digest(p) for p in paths}
    source = json.loads((OUT / (args.phase + '-database-source.json')).read_text())
    assert source['snapshotSHA256'] == before[str(current)] and len(source['avatarHTTPS']) == 2
    assert all(r['tlsVerified'] for r in source['avatarHTTPS']) and source['productionDatabaseModified'] is False
    key = (OUT / 'observation.key').read_bytes();assert len(key) == 32
    old, new, stats_source = connect(original), connect(current), connect(optimizer_source)
    try:
        schema = lambda db: db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        assert schema(old) == schema(new), 'complete-schema'
        names = [r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        assert len(names) == 24
        preserved = {};avatar_mappings = [];added = {}
        for name in names:
            columns, expected = rows(old, name);actual_columns, actual = rows(new, name);assert columns == actual_columns
            if name in ['sessions', 'sessions_continued', 'sqlite_sequence', 'sqlite_stat1']:continue
            if name == 'users':
                assert len(expected) == len(actual) == 16
                originals = {r[columns.index('id')]: dict(zip(columns, r)) for r in expected};projected = []
                for record in actual:
                    row = dict(zip(columns, record));prior = originals[row['id']]
                    assert row['user_id'] == prior['user_id']
                    if (row['thumb'], row['custom_avatar_url']) != (prior['thumb'], prior['custom_avatar_url']):
                        avatar = hmac.new(key, json.dumps(['plex-avatar', int(row['user_id']), row['thumb']], separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
                        assert source['avatars'].get(str(row['user_id'])) == avatar, 'actual-plex-avatar'
                        expected_custom = row['thumb'] if not prior['custom_avatar_url'] or prior['custom_avatar_url'] == prior['thumb'] else prior['custom_avatar_url']
                        assert row['custom_avatar_url'] == expected_custom, 'original-custom-avatar-choice'
                        row['thumb'], row['custom_avatar_url'] = prior['thumb'], prior['custom_avatar_url']
                        avatar_mappings.append({'rowIdentityHMAC': hmac.new(key, str(row['id']).encode(), hashlib.sha256).hexdigest(), 'plexTLSVerified': True, 'customChoicePreserved': True})
                    projected.append(tuple(row[c] for c in columns))
                actual = projected
            missing = collections.Counter(expected) - collections.Counter(actual)
            assert not missing, 'original-row-or-cell:' + name
            preserved[name] = len(expected);added[name] = len(actual) - len(expected)

        # Every original history/media/metadata row is exact. A live session may
        # finish normally while migration runs; bind its complete shared fields
        # to the newly recorded history, rather than requiring a frozen monitor.
        session_columns, sessions = rows(old, 'sessions');live_columns, live_rows = rows(new, 'sessions')
        assert live_columns == session_columns
        live = {r[session_columns.index('id')]: dict(zip(session_columns, r)) for r in live_rows}
        original_history_ids = {r[0] for r in old.execute('SELECT id FROM session_history')}
        history_columns, history = rows(new, 'session_history')
        appended_history = [dict(zip(history_columns, r)) for r in history if r[history_columns.index('id')] not in original_history_ids]
        completed = [];cache_paths = []
        for values in sessions:
            session = dict(zip(session_columns, values))
            assert session['id'] not in live, 'active-session-needs-live-projection-verification'
            matches = [r for r in appended_history if all(r[k] == session[k] for k in ['started', 'rating_key', 'user_id', 'machine_id'])]
            assert len(matches) == 1, 'completed-session-history'
            history_row = matches[0];assert session['stopped'] <= history_row['stopped'] <= datetime.datetime.now(datetime.timezone.utc).timestamp() + 5
            assert 0 <= history_row['view_offset'] <= session['duration']
            raw = json.loads(session['raw_stream_info']);checked = 0
            for table in ['session_history', 'session_history_media_info', 'session_history_metadata']:
                columns, _ = rows(new, table)
                value = new.execute('SELECT * FROM ' + quote(table) + ' WHERE id=?', (history_row['id'],)).fetchone();assert value is not None
                record = dict(zip(columns, value))
                for field in (set(record) & set(session)) - {'id', 'stopped', 'view_offset'}:
                    wanted = raw[field] if table == 'session_history_media_info' and field in ['transcode_width', 'transcode_height'] else session[field]
                    assert record[field] == wanted, 'completed-session-field:' + table + '/' + field
                    checked += 1
            completed.append({'sharedFieldsChecked': checked, 'sourceRawDimensionProjectionVerified': True, 'historyAndMediaRowsPresent': True})
            assert str(session['session_key']).isdigit()
            cache_paths.append('cache/session_metadata/metadata-sessionKey-' + str(session['session_key']) + '.json')

        columns, expected = rows(old, 'sessions_continued');_, actual = rows(new, 'sessions_continued')
        actual_by_id = {r[columns.index('id')]: dict(zip(columns, r)) for r in actual};continued = 0
        for value in expected:
            row = dict(zip(columns, value));now = actual_by_id[row['id']]
            assert all(now[k] == row[k] for k in columns if k != 'stopped')
            if now['stopped'] != row['stopped']:
                assert now['stopped'] >= row['stopped'] and any(all(h[k] == row[k] for k in ['user_id', 'machine_id', 'media_type']) and h['stopped'] == now['stopped'] for h in appended_history)
                continued += 1
        assert len(actual) >= len(expected)
        sequence_old = dict(old.execute('SELECT name,seq FROM sqlite_sequence'));sequence_new = dict(new.execute('SELECT name,seq FROM sqlite_sequence'))
        assert all(type(sequence_new.get(name)) is int and sequence_new[name] >= value for name, value in sequence_old.items())

        # Reproduce the pinned startup dbcheck statements on a RAM copy only.
        memory = sqlite3.connect(':memory:');stats_source.backup(memory)
        try:
            memory.execute('PRAGMA analysis_limit=400');memory.execute('ANALYZE')
            assert new.execute('SELECT tbl,idx,stat FROM sqlite_stat1 ORDER BY tbl,idx,stat').fetchall() == memory.execute('SELECT tbl,idx,stat FROM sqlite_stat1 ORDER BY tbl,idx,stat').fetchall(), 'source-exact-native-analyze'
        finally:memory.close()
        assert before == {str(p): digest(p) for p in paths}
        result = {'passed': True, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'phase': args.phase,
                  'revision': source['revision'], 'writer': source['writer'], 'sourceSHA256': digest(Path(__file__)),
                  'databaseCopiesUnchanged': True, 'databaseSHA256': before, 'completeSchemaEqual': True,
                  'originalRowsAllCellsPreservedByTable': preserved, 'newRowsByTable': added,
                  'avatarMappings': avatar_mappings, 'completedSessions': completed, 'completedSessionCachePaths': cache_paths,
                  'continuedRowsPreserved': len(expected), 'sourceMatchedContinuedStopUpdates': continued,
                  'sequencesMonotonic': True, 'optimizerStatsMatchSourceAnalyze': True,
                  'personalLoginVerified': False, 'productionModifiedByAudit': False}
        with target.open('x') as stream:json.dump(result, stream, indent=2);stream.write('\n')
        print(json.dumps({'passed': True, 'phase': args.phase, 'preservedOriginalUsers': preserved['users'], 'preservedOriginalHistoryRows': preserved['session_history'],
                          'currentHistoryRows': preserved['session_history'] + added['session_history'], 'completedSessions': len(completed), 'avatarMappings': len(avatar_mappings)}))
    finally:old.close();new.close();stats_source.close()


if __name__ == '__main__':main()
