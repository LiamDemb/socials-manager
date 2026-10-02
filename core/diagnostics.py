import sqlite3
import sys
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

import socials_manager

from . import backup, clock, instance
from .models import Job, OutboxEvent, WorkerHeartbeat
from .paths import data_root
from .sqlite_runtime import desired_journal_mode, wal_safe


def report():
    with connection.cursor() as c:
        c.execute("PRAGMA journal_mode")
        journal = c.fetchone()[0]
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    beat = WorkerHeartbeat.objects.order_by("-seen_at").first()
    now = clock.now()
    backups = backup.list_backups()
    return {
        "app_version": socials_manager.APP_VERSION,
        "python": sys.version.split()[0],
        "sqlite_runtime": sqlite3.sqlite_version,
        "wal_safe_runtime": wal_safe(),
        "journal_mode": journal,
        "expected_journal_mode": desired_journal_mode(),
        "pending_migrations": len(pending),
        "data_root": str(data_root()),
        "instance_id": instance.load()["instance_id"],
        "fixture_class": instance.load().get("fixture_class"),
        "worker_last_seen": beat.seen_at if beat else None,
        "worker_alive": bool(beat and now - beat.seen_at < timedelta(seconds=60)),
        "expired_leases": Job.objects.filter(state="leased", lease_until__lt=now).count(),
        "dead_jobs": Job.objects.filter(state="dead").count(),
        "unhandled_events": OutboxEvent.objects.filter(handled_at__isnull=True).count(),
        "last_backup": backups[0]["created_at"] if backups else None,
        "backup_count": len(backups),
    }
