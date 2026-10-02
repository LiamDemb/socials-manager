import sqlite3

# WAL-reset fix: 3.51.3+, or the fixed backports 3.44.6 and 3.50.7 (spec/ARCHITECTURE.md).
WAL_FIXED_BACKPORTS = {(3, 44, 6), (3, 50, 7)}
WAL_MINIMUM = (3, 51, 3)


def runtime_version():
    return tuple(int(p) for p in sqlite3.sqlite_version.split("."))


def wal_safe(version=None):
    version = version or runtime_version()
    if version >= WAL_MINIMUM:
        return True
    if version in WAL_FIXED_BACKPORTS:
        return True
    return False


def desired_journal_mode(version=None):
    return "wal" if wal_safe(version) else "delete"


def configure_connection(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA journal_mode = {desired_journal_mode()}")
        cursor.execute("PRAGMA synchronous = FULL")
