#!/usr/bin/env python3
"""Compare protected, checkpointed SQLite snapshots without reporting row data."""
import argparse
import collections
import datetime
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import sys
import time

MAX_BYTES = 256 * 1024 * 1024
MAX_ROWS = 250_000


class SnapshotError(Exception):
    """Only fixed, non-sensitive error codes leave the comparator."""


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise SnapshotError("snapshot_comparison_deadline")


def operation_deadline(deadline):
    now = time.monotonic()
    if deadline is None:
        return now + 300
    try:
        valid = type(deadline) in (int, float) and math.isfinite(deadline) and now < deadline <= now + 300
    except (ValueError, OverflowError):
        valid = False
    if not valid:
        raise SnapshotError("snapshot_comparison_deadline")
    return deadline


def checked_rows(connection, sql, deadline):
    check_deadline(deadline)
    for row in connection.execute(sql):
        check_deadline(deadline)
        yield row
    check_deadline(deadline)


def fingerprint(path, deadline=None):
    check_deadline(deadline)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise SnapshotError("snapshot_missing_or_too_large")
    for suffix in ("-wal", "-journal"):
        companion = pathlib.Path(str(path) + suffix)
        if companion.exists() and companion.stat().st_size:
            raise SnapshotError("checkpointed_snapshot_required")
    before = path.stat()
    hasher = hashlib.sha256()
    received = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            check_deadline(deadline)
            received += len(block)
            if received > MAX_BYTES:
                raise SnapshotError("snapshot_missing_or_too_large")
            hasher.update(block)
    digest = hasher.digest()
    after = path.stat()
    state = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if state(before) != state(after):
        raise SnapshotError("snapshot_changed_during_read")
    check_deadline(deadline)
    return state(after), digest  # Digests remain in memory; never enter reports.


def open_snapshot(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
    except BaseException:
        connection.close()
        raise
    return connection


def tables(connection, deadline=None):
    return sorted(row[0] for row in checked_rows(connection,
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_stat%'", deadline))


def columns(connection, name, deadline=None):
    return [row[1] for row in checked_rows(connection, "PRAGMA table_info(" + quote(name) + ")", deadline)]


def rows(connection, name, selected, deadline=None):
    count = next(checked_rows(connection, "SELECT count(*) FROM " + quote(name), deadline))[0]
    if count > MAX_ROWS:
        raise SnapshotError("table_row_limit_exceeded")
    return collections.Counter(checked_rows(connection,
        "SELECT " + ",".join(quote(column) for column in selected) + " FROM " + quote(name), deadline))


def schema(connection, deadline=None):
    return list(checked_rows(connection,
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_stat%' ORDER BY type,name", deadline))


def multiset_counts(original, current, deadline):
    missing = added = source_count = target_count = 0
    for row, count in original.items():
        check_deadline(deadline)
        source_count += count
        missing += max(0, count - current[row])
    for row, count in current.items():
        check_deadline(deadline)
        target_count += count
        added += max(0, count - original[row])
    return missing, added, source_count, target_count


def _compare(source_path, target_path, mode, *, deadline=None):
    deadline = operation_deadline(deadline)
    source_path, target_path = source_path.resolve(), target_path.resolve()
    if source_path == target_path or os.path.samefile(source_path, target_path):
        raise SnapshotError("independent_snapshots_required")
    initial = (fingerprint(source_path, deadline), fingerprint(target_path, deadline))
    source = target = None
    try:
        source = open_snapshot(source_path)
        source.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        check_deadline(deadline)
        target = open_snapshot(target_path)
        target.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        integrity = [list(checked_rows(db, "PRAGMA integrity_check", deadline)) == [("ok",)]
                     for db in (source, target)]
        foreign_keys = [not list(checked_rows(db, "PRAGMA foreign_key_check", deadline))
                        for db in (source, target)]
        source_tables, target_tables = tables(source, deadline), tables(target, deadline)
        required_tables = {"users", "secret_references", "_prisma_migrations"}
        if not required_tables.issubset(source_tables) or not required_tables.issubset(target_tables):
            raise SnapshotError("bortus_schema_required")
        account_columns = {"id", "username", "passwordHash", "role"}
        if not account_columns.issubset(columns(source, "users", deadline)):
            raise SnapshotError("account_schema_unrecognized")
        checks = []
        for name in source_tables:
            check_deadline(deadline)
            original_columns = columns(source, name, deadline)
            target_columns = columns(target, name, deadline) if name in target_tables else []
            present = name in target_tables
            preserved_columns = set(original_columns).issubset(target_columns)
            item = {"table": name, "present": present,
                    "sourceColumnsPreserved": preserved_columns}
            if present and preserved_columns:
                original = rows(source, name, original_columns, deadline)
                current = rows(target, name, original_columns, deadline)
                missing, added, source_count, target_count = multiset_counts(original, current, deadline)
                item.update(sourceRows=source_count, targetRows=target_count,
                            missingOrChangedRows=missing, additionalRows=added,
                            passed=missing == 0 and (mode == "forward" or added == 0))
            else:
                item["passed"] = False
            checks.append(item)
        # Legacy users acquire sessionVersion=0; existing versions must never reset.
        session_default = None
        if "users" in source_tables and "users" in target_tables:
            old_columns, new_columns = columns(source, "users", deadline), columns(target, "users", deadline)
            if "sessionVersion" not in old_columns and "sessionVersion" in new_columns:
                if "id" not in old_columns:
                    raise SnapshotError("account_schema_unrecognized")
                old_ids = {row[0] for row in checked_rows(source, 'SELECT id FROM users', deadline)}
                session_default = all(version == 0 for identity, version in
                                      checked_rows(target, 'SELECT id,sessionVersion FROM users', deadline)
                                      if identity in old_ids)
        same_schema = schema(source, deadline) == schema(target, deadline)
        migration_complete = None
        if "_prisma_migrations" in target_tables:
            needed = {"finished_at", "rolled_back_at"}
            if not needed.issubset(columns(target, "_prisma_migrations", deadline)):
                raise SnapshotError("migration_schema_unrecognized")
            migration_complete = not list(checked_rows(target,
                'SELECT 1 FROM _prisma_migrations WHERE finished_at IS NULL '
                'AND rolled_back_at IS NULL LIMIT 1', deadline))
        passed = (all(integrity) and all(foreign_keys) and all(c["passed"] for c in checks)
                  and session_default is not False and migration_complete is not False
                  and (mode == "forward" or (same_schema and source_tables == target_tables)))
        result = {"mode": mode, "passed": passed,
                  "sourceIntegrity": integrity[0], "targetIntegrity": integrity[1],
                  "sourceForeignKeysValid": foreign_keys[0], "targetForeignKeysValid": foreign_keys[1],
                  "schemaIdentical": same_schema, "legacySessionVersionZero": session_default,
                  "targetMigrationsTerminal": migration_complete,
                  "sourceTableCount": len(source_tables), "targetTableCount": len(target_tables),
                  "tables": checks}
        check_deadline(deadline)
    except sqlite3.Error:
        check_deadline(deadline)
        raise
    finally:
        for connection in (source, target):
            if connection is not None:
                connection.close()
    if initial != (fingerprint(source_path, deadline), fingerprint(target_path, deadline)):
        raise SnapshotError("snapshot_changed_during_comparison")
    return result


def compare(source_path, target_path, mode, *, deadline=None):
    """Library boundary: expose only fixed failure codes, never SQLite or path errors."""
    try:
        return _compare(source_path, target_path, mode, deadline=deadline)
    except SnapshotError:
        raise
    except (sqlite3.Error, OSError, ValueError, OverflowError):
        raise SnapshotError("snapshot_comparison_failed") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--target", type=pathlib.Path, required=True)
    parser.add_argument("--mode", choices=("forward", "recovery"), required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    # Refuse historical evidence replacement before reading protected inputs.
    if args.output.exists():
        parser.exit(2, "Evidence output already exists.\n")
    try:
        result = compare(args.source, args.target, args.mode)
    except SnapshotError as error:
        result = {"mode": args.mode, "passed": False, "error": str(error)}
    except (sqlite3.Error, OSError, ValueError, OverflowError):
        result = {"mode": args.mode, "passed": False, "error": "snapshot_comparison_failed"}
    result.update(capturedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope="Supplied SQLite snapshots only; no image, native Secret, storage or cold-checkpoint proof",
                  valuesReported=False, credentialDigestsReported=False, databaseWrites=False)
    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except OSError:
        parser.exit(2, "Could not create new evidence output.\n")
    print(json.dumps({"passed": result["passed"], "mode": args.mode,
                      "error": result.get("error")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
