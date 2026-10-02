import logging
import os
import signal
import socket
import time as systime

from django.db import close_old_connections, transaction

from . import backup, clock, instance
from .models import BackupRecord, OutboxEvent, WorkerHeartbeat
from .services import audit, claim_next_job, enqueue, finish_job

log = logging.getLogger("socials_manager.worker")


def run_backup_job(job):
    dest, manifest = backup.create_backup("daily")
    BackupRecord.objects.create(created_at=clock.now(), relative_path=str(dest.relative_to(backup.settings_root())), reason="daily",
                                status="ok", detail={"counts": manifest["counts"]})


def run_cleanup_job(job):
    removed = 0
    for path in backup.orphan_files():
        path.unlink()
        removed += 1
    if removed:
        audit("operations", "imports", "orphan_cleanup", {"removed": removed}, actor="system")


def run_collect_job(job):
    from sources.collector import run_collect

    run_collect(job)


HANDLERS = {"backup.daily": run_backup_job, "cleanup.orphans": run_cleanup_job, "collect.source": run_collect_job}


def handle_outbox(limit=50):
    from findings.services import invalidate_for_event

    handled = 0
    for event in OutboxEvent.objects.filter(handled_at__isnull=True).order_by("created_at")[:limit]:
        with transaction.atomic():
            if OutboxEvent.objects.filter(pk=event.pk, handled_at__isnull=True).update(handled_at=clock.now()) == 1:
                invalidated = invalidate_for_event(event.kind, event.payload)
                audit("outbox", event.pk, f"handled.{event.kind}", {"invalidated": invalidated}, actor="system")
                handled += 1
    return handled


def schedule_due_jobs():
    tz_name = instance.load()["timezone"]
    local_day = clock.now().astimezone(__import__("zoneinfo").ZoneInfo(tz_name)).date().isoformat()
    enqueue("backup.daily", "instance", local_day)
    enqueue("cleanup.orphans", "imports", local_day)
    enqueue("collect.source", "instagram:graph_api", local_day)
    enqueue("collect.source", "peers:business_discovery", local_day)


def tick(worker_id):
    close_old_connections()
    WorkerHeartbeat.objects.update_or_create(worker_id=worker_id, defaults={"seen_at": clock.now(), "pid": os.getpid()})
    schedule_due_jobs()
    handle_outbox()
    job = claim_next_job(worker_id)
    if job is None:
        return False
    try:
        HANDLERS[job.task](job)
        finish_job(job, worker_id)
    except Exception as exc:  # noqa: BLE001 - job errors are recorded safely and retried with backoff
        log.warning("job %s failed: %s", job.task, type(exc).__name__)
        finish_job(job, worker_id, error=f"{type(exc).__name__}: {exc}"[:300])
    return True


def run_forever(interval=5):
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    stopping = {"flag": False}

    def stop(*_):
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker %s started", worker_id)
    while not stopping["flag"]:
        busy = tick(worker_id)
        if not busy:
            for _ in range(interval * 10):
                if stopping["flag"]:
                    break
                systime.sleep(0.1)
    log.info("worker %s stopped", worker_id)
