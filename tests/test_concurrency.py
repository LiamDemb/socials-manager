"""AC10 concurrent edits, imports and idempotent replays over separate SQLite connections; AC11 lease recovery."""
import threading
from datetime import timedelta

from django.db import connection, connections
from django.test import TransactionTestCase

from campaigns.models import Activity, Campaign
from campaigns.services import add_activity, create_campaign, reschedule
from core import clock
from core.errors import DomainError
from core.models import Job
from core.services import claim_next_job, enqueue, finish_job
from sources.models import ImportBatch, Observation
from sources.services import commit, preview_upload, set_mapping

from .helpers import bootstrap, key, recording, recording_csv, utc

GROWTH = {"type": "audience_growth", "name": "Grow", "start_date": "2026-10-01", "end_date": "2026-10-31",
          "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 10}}


def race(*fns):
    """Run callables at the same moment on separate threads (separate DB connections)."""
    barrier = threading.Barrier(len(fns))
    results = [None] * len(fns)

    def run(i, fn):
        try:
            barrier.wait()
            results[i] = ("ok", fn())
        except Exception as exc:  # noqa: BLE001
            results[i] = ("error", exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results


class Concurrency(TransactionTestCase):
    def setUp(self):
        bootstrap()
        with connection.cursor() as c:
            c.execute("PRAGMA journal_mode")
            self.journal = c.fetchone()[0]

    def test_file_database_with_expected_journal(self):
        from core.sqlite_runtime import desired_journal_mode

        self.assertEqual(self.journal, desired_journal_mode())

    def test_two_edits_same_revision_one_wins(self):
        c = create_campaign(GROWTH, key())
        a = add_activity(c["campaign_id"], {"title": "Post", "date": "2026-10-05", "time": "18:00"}, key())
        results = race(
            lambda: reschedule(a["activity_id"], a["revision"], "2026-10-06", "18:00", key()),
            lambda: reschedule(a["activity_id"], a["revision"], "2026-10-07", "18:00", key()),
        )
        outcomes = sorted(r[0] for r in results)
        self.assertEqual(outcomes, ["error", "ok"])
        err = next(r[1] for r in results if r[0] == "error")
        self.assertIsInstance(err, DomainError)
        self.assertEqual(err.code, "stale_revision")
        act = Activity.objects.get(pk=a["activity_id"])
        self.assertIn(act.planned_local[:10], {"2026-10-06", "2026-10-07"})
        self.assertEqual(act.revision, a["revision"] + 1)

    def test_same_idempotency_key_creates_once(self):
        k = key()
        results = race(lambda: create_campaign(GROWTH, k), lambda: create_campaign(GROWTH, k))
        self.assertEqual([r[0] for r in results], ["ok", "ok"], results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Campaign.objects.count(), 1)

    def test_competing_imports_of_same_day(self):
        song = recording()
        previews = []
        for value in (5, 6):
            b = preview_upload(recording_csv([("2026-09-01", value)]), f"{value}.csv")
            previews.append(set_mapping(b.pk, b.preview_revision, entity_id=song.pk))
        results = race(*[lambda b=b: commit(b.pk, b.preview_revision, key()) for b in previews])
        self.assertEqual(sorted(r[0] for r in results), ["error", "ok"], results)
        err = next(r[1] for r in results if r[0] == "error")
        self.assertEqual(err.code, "stale_preview")
        self.assertEqual(Observation.objects.filter(entity=song.entity).count(), 1)
        self.assertEqual(ImportBatch.objects.filter(state="committed").count(), 1)

    def test_double_commit_same_batch(self):
        song = recording()
        b = preview_upload(recording_csv([("2026-09-01", 5), ("2026-09-02", 1)]), "a.csv")
        b = set_mapping(b.pk, b.preview_revision, entity_id=song.pk)
        results = race(lambda: commit(b.pk, b.preview_revision, key()), lambda: commit(b.pk, b.preview_revision, key()))
        self.assertIn("ok", [r[0] for r in results])
        self.assertEqual(Observation.objects.filter(entity=song.entity).count(), 2)
        self.assertEqual(ImportBatch.objects.get(pk=b.pk).state, "committed")


class Leases(TransactionTestCase):
    def test_expired_lease_is_recovered_and_failures_dead_letter(self):
        bootstrap()
        t0 = utc(2026, 10, 2, 0, 0)
        with clock.frozen(t0):
            enqueue("backup.daily", "x", "2026-10-02", max_attempts=2)
            job = claim_next_job("worker-a", lease_seconds=60)
            self.assertIsNotNone(job)
            self.assertIsNone(claim_next_job("worker-b"), "Leased job is not double-claimed")
        with clock.frozen(t0 + timedelta(seconds=61)):
            recovered = claim_next_job("worker-b")
            self.assertEqual((recovered.pk, recovered.attempts), (job.pk, 2))
            self.assertEqual(finish_job(job, "worker-a"), 0, "Stale owner cannot finish")
            finish_job(recovered, "worker-b", error="boom")
        self.assertEqual(Job.objects.get(pk=job.pk).state, "dead")
