"""AC06 campaign-first outcomes and deduplication; operational proposals; date-change flags."""
from datetime import date

from django.test import TestCase

from campaigns.models import Activity, ActivityOutcome, Campaign, CampaignOutcome, OutcomeVersion
from campaigns.services import (
    add_activity,
    create_campaign,
    deduplicated_outcomes,
    link_outcome,
    preview_operational,
    update_campaign,
)
from catalogue.services import create_object, update_object
from core.errors import DomainError
from sources.models import MetricDefinition

from .helpers import bootstrap, key

FOLLOWERS = {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 100,
             "period_start": "2026-10-01", "period_end": "2026-11-01"}


class CampaignFirst(TestCase):
    def setUp(self):
        self.artist = bootstrap()

    def test_ac06_release_growth_show_and_shared_outcome_counted_once(self):
        song = create_object("recording", "Next single", key_date=date(2026, 10, 16))
        release = create_campaign({
            "type": "single", "name": "Next single", "start_date": "2026-10-01", "end_date": "2026-10-31",
            "object": {"mode": "existing", "id": str(song.pk)},
            "primary_outcome": {"mode": "new", "metric_id": "spotify.recording.streams.v1", "outcome_mode": "total", "target": 1000},
            "supporting_outcomes": [FOLLOWERS],
        }, key())
        growth = create_campaign({"type": "audience_growth", "name": "Grow", "start_date": "2026-10-01", "end_date": "2026-10-31",
                                  "primary_outcome": FOLLOWERS}, key())
        show = create_campaign({
            "type": "live_show", "name": "Perth show", "start_date": "2026-10-01", "end_date": "2026-11-13",
            "object": {"mode": "new", "label": "Perth headline", "key_date": "2026-11-12", "venue": "The Bird"},
            "primary_outcome": {"mode": "new", "metric_id": "tickets.event.net.v1", "outcome_mode": "level", "target": 150},
        }, key())
        self.assertEqual(Campaign.objects.count(), 3)
        follower_versions = OutcomeVersion.objects.filter(metric_id="spotify.artist.followers.v1")
        self.assertEqual(follower_versions.count(), 1, "Identical contract is shared, not copied")
        self.assertEqual(CampaignOutcome.objects.filter(outcome_version=follower_versions.get()).count(), 2)
        rows = deduplicated_outcomes()
        self.assertEqual(len(rows), 3)
        shared = next(r for r in rows if r["ov"].metric_id == "spotify.artist.followers.v1")
        self.assertEqual({c.name for c, _ in shared["campaigns"]}, {"Next single", "Grow"})
        self.assertIsNone(Campaign.objects.get(pk=growth["campaign_id"]).promoted_object, "Growth has no release object")
        event = Campaign.objects.get(pk=show["campaign_id"]).promoted_object
        self.assertEqual((event.kind, event.timezone), ("event", "Australia/Perth"))
        self.assertTrue(release["campaign_id"])

    def test_different_window_is_a_separate_contract(self):
        create_campaign({"type": "audience_growth", "name": "A", "start_date": "2026-10-01", "end_date": "2026-10-31", "primary_outcome": FOLLOWERS}, key())
        other = {**FOLLOWERS, "period_end": "2026-12-01"}
        create_campaign({"type": "audience_growth", "name": "B", "start_date": "2026-10-01", "end_date": "2026-11-30", "primary_outcome": other}, key())
        self.assertEqual(OutcomeVersion.objects.filter(metric_id="spotify.artist.followers.v1").count(), 2)

    def test_scope_mismatch_rejected(self):
        with self.assertRaises(DomainError) as err:
            create_campaign({
                "type": "live_show", "name": "Show", "start_date": "2026-10-01", "end_date": "2026-11-13",
                "object": {"mode": "new", "label": "Gig", "key_date": "2026-11-12"},
                "primary_outcome": {"mode": "new", "metric_id": "spotify.recording.streams.v1", "outcome_mode": "total", "target": 5},
            }, key())
        self.assertEqual(err.exception.code, "scope_mismatch")
        self.assertEqual(Campaign.objects.count(), 0, "Atomic: nothing persisted")

    def test_growth_needs_no_object_and_invalid_mode_rejected(self):
        with self.assertRaises(DomainError) as err:
            create_campaign({"type": "audience_growth", "name": "G", "start_date": "2026-10-01", "end_date": "2026-10-31",
                             "primary_outcome": {**FOLLOWERS, "outcome_mode": "total"}}, key())
        self.assertEqual(err.exception.code, "invalid_mode")

    def test_approval_creates_only_selected_activities_and_is_idempotent(self):
        song = create_object("recording", "S", key_date=date(2026, 10, 16))
        metric = MetricDefinition.objects.get(pk="spotify.recording.streams.v1")
        preview = preview_operational({"type": "single", "start_date": date(2026, 10, 1), "end_date": date(2026, 10, 31),
                                       "key_date": song.key_date, "object_label": song.label, "primary_metric": metric})
        keys = [a["template_key"] for a in preview["activities"]]
        self.assertIn("anchor", keys)
        self.assertTrue(any("No eligible evidence" in g for g in preview["gaps"]))
        acts = [{**a, "selected": a["template_key"] != "links"} for a in preview["activities"]]
        payload = {"type": "single", "name": "S", "start_date": "2026-10-01", "end_date": "2026-10-31",
                   "object": {"mode": "existing", "id": str(song.pk)},
                   "primary_outcome": {"mode": "new", "metric_id": metric.pk, "outcome_mode": "total", "target": 10}, "activities": acts}
        k = key()
        first = create_campaign(payload, k)
        again = create_campaign(payload, k)
        self.assertEqual(first, again)
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertEqual(Activity.objects.count(), len(acts) - 1)
        self.assertFalse(Activity.objects.filter(origin_detail__template_key="links").exists())
        self.assertEqual(ActivityOutcome.objects.count(), Activity.objects.count())

    def test_presave_without_provider_is_a_gap_and_setup_task(self):
        song = create_object("recording", "S", key_date=date(2026, 10, 16))
        preview = preview_operational({"type": "single", "start_date": date(2026, 10, 1), "end_date": date(2026, 10, 31),
                                       "key_date": song.key_date, "object_label": "S", "primary_metric": MetricDefinition.objects.get(pk="presave.release.confirmed.v1")})
        self.assertIn("source_setup", [a["template_key"] for a in preview["activities"]])

    def test_email_needs_opted_in_list(self):
        c = create_campaign({"type": "audience_growth", "name": "G", "start_date": "2026-10-01", "end_date": "2026-10-31",
                             "resources": {"channels": ["email", "instagram"]}, "primary_outcome": FOLLOWERS}, key())
        camp = Campaign.objects.get(pk=c["campaign_id"])
        self.assertNotIn("email", camp.resources["channels"])
        with self.assertRaises(DomainError) as err:
            add_activity(camp.pk, {"title": "Newsletter", "channel": "email", "date": "2026-10-05"}, key())
        self.assertEqual(err.exception.code, "no_email_list")

    def test_key_date_change_flags_work_without_moving_it(self):
        song = create_object("recording", "S", key_date=date(2026, 10, 16))
        c = create_campaign({"type": "single", "name": "S", "start_date": "2026-10-01", "end_date": "2026-10-31",
                             "object": {"mode": "existing", "id": str(song.pk)},
                             "primary_outcome": {"mode": "new", "metric_id": "spotify.recording.streams.v1", "outcome_mode": "total", "target": 10},
                             "activities": [{"title": "Release post", "date": "2026-10-16", "time": "18:00", "channel": "instagram"}]}, key())
        act = Activity.objects.get(pk=c["activities"][0])
        song.refresh_from_db()
        update_object(song.pk, song.revision, key_date=date(2026, 10, 23))
        act.refresh_from_db()
        self.assertIn("date changed", act.review_flag)
        self.assertEqual(act.planned_local, "2026-10-16T18:00", "Not moved silently")
        camp = Campaign.objects.get(pk=c["campaign_id"])
        result = update_campaign(camp.pk, camp.revision, {"end_date": "2026-11-07"}, key())
        self.assertEqual(result["flagged_activities"], 1)

    def test_link_existing_outcome_is_a_link_not_copy(self):
        a = create_campaign({"type": "audience_growth", "name": "A", "start_date": "2026-10-01", "end_date": "2026-10-31", "primary_outcome": FOLLOWERS}, key())
        b = create_campaign({"type": "content_push", "name": "B", "start_date": "2026-10-01", "end_date": "2026-10-31",
                             "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.streams.v1", "outcome_mode": "total", "target": 50}}, key())
        ov = OutcomeVersion.objects.get(metric_id="spotify.artist.followers.v1")
        link_outcome(b["campaign_id"], ov.pk)
        link_outcome(b["campaign_id"], ov.pk)
        self.assertEqual(OutcomeVersion.objects.count(), 2)
        self.assertEqual(CampaignOutcome.objects.filter(outcome_version=ov).count(), 2)
        self.assertTrue(a)
