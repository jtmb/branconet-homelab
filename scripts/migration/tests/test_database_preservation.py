import contextlib
import importlib.util
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "compare-bortus-databases.py"
SPEC = importlib.util.spec_from_file_location("database_preservation", SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
PRIVATE = "synthetic-private-do-not-report-589176"


def database(path, session_version=False):
    with contextlib.closing(sqlite3.connect(path)) as db, db:
        extra = ",sessionVersion INTEGER NOT NULL DEFAULT 0" if session_version else ""
        db.execute('CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,passwordHash TEXT,role TEXT' + extra + ')')
        db.execute('INSERT INTO users(id,username,passwordHash,role) VALUES(?,?,?,?)',
                   ("original-user", "synthetic-user", PRIVATE, "write"))
        db.execute('CREATE TABLE secret_references(alias TEXT PRIMARY KEY,namespace TEXT,name TEXT,key TEXT)')
        db.execute('INSERT INTO secret_references VALUES(?,?,?,?)', ("original-alias", "app", "native", "key"))
        db.execute('CREATE TABLE _prisma_migrations(id TEXT PRIMARY KEY,checksum TEXT,migration_name TEXT,finished_at TEXT,rolled_back_at TEXT)')
        db.execute('INSERT INTO _prisma_migrations VALUES(?,?,?,?,?)', ("initial", "synthetic-checksum", "initial", "finished", None))
        db.execute('CREATE TABLE variables(id TEXT,value BLOB)')
        db.executemany('INSERT INTO variables VALUES(?,?)', [("duplicated", PRIVATE.encode())] * 2)


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.directory.name)
        self.source, self.target = self.root / "source.db", self.root / "target.db"
        database(self.source)
        database(self.target)

    def tearDown(self):
        self.assertEqual(self.root.resolve().parent, pathlib.Path(tempfile.gettempdir()).resolve())
        self.directory.cleanup()

    def mutate(self, sql, parameters=()):
        with contextlib.closing(sqlite3.connect(self.target)) as db, db:
            db.execute(sql, parameters)

    def test_forward_schema_additions_and_legacy_session_preserve_all_bytes(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.mutate('ALTER TABLE users ADD COLUMN sessionVersion INTEGER NOT NULL DEFAULT 0')
        self.mutate('CREATE TABLE kv_operations(id TEXT,outcome TEXT)')
        self.mutate('INSERT INTO kv_operations VALUES(?,?)', ("new-operation", "accepted"))
        target_before = self.target.read_bytes()
        report = AUDIT.compare(self.source, self.target, "forward")
        self.assertTrue(report["passed"])
        self.assertTrue(report["legacySessionVersionZero"])
        self.assertFalse(report["schemaIdentical"])
        self.assertEqual(self.source.read_bytes(), before["source.db"])
        self.assertEqual(self.target.read_bytes(), target_before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["source.db", "target.db"])
        self.assertNotIn(PRIVATE, json.dumps(report))
        self.assertFalse(AUDIT.compare(self.source, self.target, "recovery")["passed"])

    def test_password_alias_and_duplicate_row_loss_are_failures(self):
        for statement, parameters in [
            ('UPDATE users SET passwordHash=?', ("changed-secret",)),
            ('UPDATE secret_references SET name=?', ("wrong-target",)),
            ('DELETE FROM variables WHERE rowid=(SELECT min(rowid) FROM variables)', ())]:
            with self.subTest(statement=statement):
                original = self.target.read_bytes()
                self.mutate(statement, parameters)
                report = AUDIT.compare(self.source, self.target, "forward")
                self.assertFalse(report["passed"])
                self.assertNotIn(PRIVATE, json.dumps(report))
                self.target.write_bytes(original)

    def test_recovery_rejects_extra_rows_and_new_index(self):
        self.assertTrue(AUDIT.compare(self.source, self.target, "recovery")["passed"])
        self.mutate('INSERT INTO variables VALUES(?,?)', ("new", b"new-state"))
        self.assertFalse(AUDIT.compare(self.source, self.target, "recovery")["passed"])
        self.mutate('DELETE FROM variables WHERE id=?', ("new",))
        self.mutate('CREATE INDEX extra_index ON variables(id)')
        self.assertFalse(AUDIT.compare(self.source, self.target, "recovery")["passed"])

    def test_foreign_keys_and_unfinished_migration_refuse_acceptance(self):
        self.mutate('CREATE TABLE kv_fields(id TEXT,parent TEXT REFERENCES users(id))')
        self.mutate('INSERT INTO kv_fields VALUES(?,?)', ("field", "missing-parent"))
        result = AUDIT.compare(self.source, self.target, "forward")
        self.assertFalse(result["targetForeignKeysValid"])
        self.assertFalse(result["passed"])
        self.mutate('DELETE FROM kv_fields')
        self.mutate('INSERT INTO _prisma_migrations VALUES(?,?,?,?,?)', ("pending", "new-checksum", "new", None, None))
        result = AUDIT.compare(self.source, self.target, "forward")
        self.assertFalse(result["targetMigrationsTerminal"])
        self.assertFalse(result["passed"])

    def test_nonzero_legacy_session_default_and_removed_columns_fail(self):
        self.mutate('ALTER TABLE users ADD COLUMN sessionVersion INTEGER NOT NULL DEFAULT 4')
        self.assertFalse(AUDIT.compare(self.source, self.target, "forward")["passed"])
        self.mutate('ALTER TABLE variables DROP COLUMN value')
        result = AUDIT.compare(self.source, self.target, "forward")
        self.assertFalse(next(t for t in result["tables"] if t["table"] == "variables")["sourceColumnsPreserved"])

    def test_input_refusals_and_change_detection(self):
        with self.assertRaisesRegex(AUDIT.SnapshotError, "independent_snapshots_required"):
            AUDIT.compare(self.source, self.source, "forward")
        wal = pathlib.Path(str(self.source) + "-wal")
        wal.write_bytes(b"uncheckpointed")
        with self.assertRaisesRegex(AUDIT.SnapshotError, "checkpointed_snapshot_required"):
            AUDIT.compare(self.source, self.target, "forward")
        wal.unlink()
        original_fingerprint = AUDIT.fingerprint
        calls = 0
        def changed(path, deadline=None):
            nonlocal calls
            calls += 1
            state, digest = original_fingerprint(path, deadline)
            return (state, b"changed") if calls == 4 else (state, digest)
        AUDIT.fingerprint = changed
        try:
            with self.assertRaisesRegex(AUDIT.SnapshotError, "snapshot_changed_during_comparison"):
                AUDIT.compare(self.source, self.target, "forward")
        finally:
            AUDIT.fingerprint = original_fingerprint

    def test_cli_redacts_failure_and_never_overwrites_evidence(self):
        output = self.root / "evidence.json"
        command = [sys.executable, str(SOURCE), "--source", str(self.source), "--target", str(self.target),
                   "--mode", "recovery", "--output", str(output)]
        self.target.write_bytes(PRIVATE.encode())
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 1)
        artifact = output.read_bytes()
        self.assertNotIn(PRIVATE, first.stdout + first.stderr + artifact.decode())
        report = json.loads(artifact)
        self.assertEqual(report["error"], "snapshot_comparison_failed")
        self.assertFalse(report["databaseWrites"])
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output.read_bytes(), artifact)

    def test_wrong_database_and_row_limits_refuse_acceptance(self):
        self.mutate('DROP TABLE secret_references')
        with self.assertRaisesRegex(AUDIT.SnapshotError, "bortus_schema_required"):
            AUDIT.compare(self.source, self.target, "forward")
        self.mutate('CREATE TABLE secret_references(alias TEXT PRIMARY KEY,namespace TEXT,name TEXT,key TEXT)')
        previous_limit = AUDIT.MAX_ROWS
        AUDIT.MAX_ROWS = 1
        try:
            with self.assertRaisesRegex(AUDIT.SnapshotError, "table_row_limit_exceeded"):
                AUDIT.compare(self.source, self.target, "forward")
        finally:
            AUDIT.MAX_ROWS = previous_limit

    def test_target_open_failure_closes_the_already_open_source(self):
        opened = []
        original_open = AUDIT.open_snapshot
        def failed_second(path):
            if opened:
                raise sqlite3.DatabaseError(PRIVATE)
            connection = original_open(path)
            opened.append(connection)
            return connection
        AUDIT.open_snapshot = failed_second
        try:
            with self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_failed$') as refusal:
                AUDIT.compare(self.source, self.target, "forward")
            self.assertNotIn(PRIVATE, str(refusal.exception))
        finally:
            AUDIT.open_snapshot = original_open
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute('SELECT 1')

    def test_expired_nonfinite_and_overlong_deadlines_refuse_before_read(self):
        now = time.monotonic()
        for deadline in (now - 1, now + 301, float('nan'), float('inf'), True, '300', 10 ** 1000):
            with self.subTest(kind=type(deadline).__name__), \
                    mock.patch.object(AUDIT, 'fingerprint') as fingerprint, \
                    self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_deadline$'):
                AUDIT.compare(self.source, self.target, 'recovery', deadline=deadline)
            fingerprint.assert_not_called()

    def test_shared_deadline_is_preserved_and_expiry_during_hash_refuses(self):
        deadline = time.monotonic() + 30
        with mock.patch.object(AUDIT, 'fingerprint', wraps=AUDIT.fingerprint) as fingerprint:
            self.assertTrue(AUDIT.compare(self.source, self.target, 'recovery', deadline=deadline)['passed'])
        self.assertEqual([call.args[1] for call in fingerprint.call_args_list], [deadline] * 4)
        # First check passes; the first actual file block is read when the budget expires.
        with mock.patch.object(AUDIT.time, 'monotonic', side_effect=[deadline - 1, deadline]), \
                self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_deadline$'):
            AUDIT.fingerprint(self.source, deadline)

    def test_row_iteration_and_multiset_count_checks_deadline(self):
        deadline = time.monotonic() + 30
        with contextlib.closing(AUDIT.open_snapshot(self.source)) as connection:
            iterator = AUDIT.checked_rows(connection, 'SELECT value FROM variables', deadline)
            self.assertEqual(next(iterator), (PRIVATE.encode(),))
            with mock.patch.object(AUDIT.time, 'monotonic', return_value=deadline), \
                    self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_deadline$'):
                next(iterator)
        with mock.patch.object(AUDIT.time, 'monotonic', return_value=deadline), \
                self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_deadline$'):
            AUDIT.multiset_counts({('public',): 2}, {('public',): 1}, deadline)

    def test_sqlite_vm_interrupts_before_aggregate_result_and_closes_both_connections(self):
        opened = []
        original_open = AUDIT.open_snapshot
        deadline = time.monotonic() + 30
        clock = [deadline - 1]
        def tracked(path):
            db = original_open(path)
            opened.append(db)
            return db
        def aggregate(connection, sql, budget):
            # No row is produced before ~1M recursive VM operations; only the actual
            # installed progress handler can stop this query before its aggregate.
            clock[0] = deadline
            connection.execute('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL '
                               'SELECT x+1 FROM n WHERE x<1000000) SELECT sum(x) FROM n').fetchone()
            raise AssertionError('SQLite VM deadline was not enforced')
        with mock.patch.object(AUDIT, 'open_snapshot', side_effect=tracked), \
                mock.patch.object(AUDIT.time, 'monotonic', side_effect=lambda: clock[0]), \
                mock.patch.object(AUDIT, 'checked_rows', side_effect=aggregate), \
                self.assertRaisesRegex(AUDIT.SnapshotError, '^snapshot_comparison_deadline$'):
            AUDIT.compare(self.source, self.target, 'recovery', deadline=deadline)
        self.assertEqual(len(opened), 2)
        for connection in opened:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')


if __name__ == "__main__":
    unittest.main()
