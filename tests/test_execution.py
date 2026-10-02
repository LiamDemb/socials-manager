"""AC08 execution clock/terminal states and AC09 completion versus outcome."""
from datetime import date, datetime, time, timezone

from django.test import SimpleTestCase, TestCase

from campaigns.models import Activity, ExecutionEvent
from campaigns.rules import derived_state, local_to_utc
from campaigns.services import add_activity, create_campaign, execute, outcome_progress, reschedule, set_status
from core import clock
from core.errors import DomainError

from .helpers import bootstrap, import_file, key, recording_csv, utc

PERTH = "Australia/Perth"


class Clock(SimpleTestCase):
    five_pm = local_to_utc(date(2026, 10, 2), time(17, 0), PERTH)

    def state(self, now, planned=None, all_day=None, status="planned"):
        return derived_state(status, planned, all_day, now, PERTH)

    def test_timed_before_and_after_5pm(self):
        self.assertEqual(self.state(utc(2026, 10, 2, 8, 59), self.five_pm), "Due today")
        self.assertEqual(self.state(utc(2026, 10, 2, 9, 0), self.five_pm), "Overdue")
        self.assertEqual(self.state(utc(2026, 10, 1, 8, 0), self.five_pm), "Upcoming")

    def test_all_day_overdue_after_local_day(self):
        day = date(2026, 10, 2)
        self.assertEqual(self.state(utc(2026, 10, 2, 15, 59), all_day=day), "Due today", "23:59 Perth")
        self.assertEqual(self.state(utc(2026, 10, 2, 16, 0), all_day=day), "Overdue", "00:00 Perth next day")
        self.assertEqual(self.state(utc(2026, 10, 1, 15, 59), all_day=day), "Upcoming")

    def test_terminal_precedence_and_unscheduled(self):
        for status, label in [("completed", "Completed"), ("skipped", "Skipped"), ("cancelled", "Cancelled")]:
            self.assertEqual(self.state(utc(2027, 1, 1), self.five_pm, status=status), label)
        self.assertEqual(self.state(utc(2026, 10, 2)), "Unscheduled")

    def test_dst_nonexistent_and_ambiguous(self):
        with self.assertRaises(DomainError) as err:
            local_to_utc(date(2026, 10, 4), time(2, 30), "Australia/Sydney")
        self.assertEqual(err.exception.code, "nonexistent_local_time")
        with self.assertRaises(DomainError) as err:
            local_to_utc(date(2026, 4, 5), time(2, 30), "Australia/Sydney")
        self.assertEqual(err.exception.code, "ambiguous_local_time")
        self.assertEqual(local_to_utc(date(2026, 10, 2), time(17, 0), PERTH), utc(2026, 10, 2, 9, 0))


def growth_campaign(**overrides):
    payload = {
        "type": "audience_growth", "name": "Grow", "start_date": "2026-09-20", "end_date": "2026-10-20",
        "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 100},
    }
    payload.update(overrides)
    return create_campaign(payload, key())


class Execution(TestCase):
    def setUp(self):
        bootstrap()
        self.now = utc(2026, 10, 2, 3, 0)

    def activity(self, **data):
        with clock.frozen(self.now):
            c = growth_campaign()
            r = add_activity(c["campaign_id"], {"title": "Post", "date": "2026-10-02", "time": "17:00", **data}, key())
        return c, r

    def test_complete_records_actual_time_and_history(self):
        _, r = self.activity()
        with clock.frozen(self.now):
            done = execute(r["activity_id"], r["revision"], "complete", key(), actual_at="2026-10-02T10:30", url="https://instagram.com/p/x")
        a = Activity.objects.get(pk=r["activity_id"])
        self.assertEqual(a.actual_at_utc, utc(2026, 10, 2, 2, 30))
        self.assertNotEqual(a.actual_at_utc, a.planned_at_utc)
        with clock.frozen(self.now):
            reopened = execute(a.pk, done["revision"], "reopen", key(), reason="posted the wrong cut")
        events = list(ExecutionEvent.objects.filter(activity=a).values_list("prior_state", "new_state"))
        self.assertEqual(events, [("planned", "completed"), ("completed", "planned")])
        self.assertEqual(reopened["status"], "planned")

    def test_future_completion_rejected(self):
        _, r = self.activity()
        with clock.frozen(self.now), self.assertRaises(DomainError) as err:
            execute(r["activity_id"], r["revision"], "complete", key(), actual_at="2026-10-02T18:00")
        self.assertEqual(err.exception.code, "future_completion")

    def test_skip_cancel_need_reason(self):
        _, r = self.activity()
        with clock.frozen(self.now):
            for action in ("skip", "cancel"):
                with self.assertRaises(DomainError):
                    execute(r["activity_id"], r["revision"], action, key(), reason="")
            execute(r["activity_id"], r["revision"], "skip", key(), reason="Rain")
        self.assertEqual(Activity.objects.get(pk=r["activity_id"]).status, "skipped")

    def test_completed_cannot_be_rescheduled_without_reopen(self):
        _, r = self.activity()
        with clock.frozen(self.now):
            done = execute(r["activity_id"], r["revision"], "complete", key())
            with self.assertRaises(DomainError) as err:
                reschedule(r["activity_id"], done["revision"], "2026-10-05", "18:00", key())
        self.assertEqual(err.exception.code, "reopen_first")

    def test_paused_campaign_suppressed_from_due_work(self):
        from campaigns.models import Campaign
        from campaigns.services import due_work

        c, _ = self.activity()
        with clock.frozen(utc(2026, 10, 2, 12, 0)):
            self.assertEqual(len(due_work()), 1)
            camp = Campaign.objects.get(pk=c["campaign_id"])
            set_status(camp.pk, camp.revision, "paused", "", key())
            self.assertEqual(due_work(), [])
            self.assertEqual(Activity.objects.filter(campaign=camp).count(), 1, "Still visible in history")

    def test_reactivation_requires_reason(self):
        from campaigns.models import Campaign

        c, _ = self.activity()
        camp = Campaign.objects.get(pk=c["campaign_id"])
        r = set_status(camp.pk, camp.revision, "completed", "", key())
        with self.assertRaises(DomainError):
            set_status(camp.pk, r["revision"], "active", "", key())
        set_status(camp.pk, r["revision"], "active", "One more show added", key())


class CompletionVersusOutcome(TestCase):
    def test_ac09_completion_changes_no_metric_then_observation_does(self):
        bootstrap()
        from campaigns.models import OutcomeVersion
        from catalogue.services import create_object

        song = create_object("recording", "Single")
        with clock.frozen(utc(2026, 9, 29, 2, 0)):
            c = create_campaign({
                "type": "single", "name": "Single", "start_date": "2026-09-20", "end_date": "2026-10-03",
                "object": {"mode": "existing", "id": str(song.pk)},
                "primary_outcome": {"mode": "new", "metric_id": "spotify.recording.streams.v1", "outcome_mode": "total", "target": 150},
                "activities": [{"title": "Teaser", "date": "2026-09-24", "channel": "instagram", "format": "Reel"}],
            }, key())
            ov = OutcomeVersion.objects.get(pk=c["primary_outcome_version_id"])
            before = outcome_progress(ov)
            act = Activity.objects.get(pk=c["activities"][0])
            execute(act.pk, act.revision, "complete", key(), actual_at="2026-09-24T18:00")
            after_completion = outcome_progress(ov)
            self.assertEqual((before.status, before.value), ("unknown", None))
            self.assertEqual((after_completion.status, after_completion.value), (before.status, before.value))
            import_file(recording_csv([("2026-09-24", 50), ("2026-09-25", 60), ("2026-09-26", 45), ("2026-09-27", 30), ("2026-09-28", 15)]),
                        "s.csv", recording=song)
            after_import = outcome_progress(ov)
        self.assertEqual(after_import.value, 200)
        self.assertEqual(after_import.status, "met")
