"""Stage 3 repair: contracts and end-to-end synthesis paths."""
import uuid
from datetime import date
from unittest import mock

from django.test import TestCase

from campaigns.services import preview_operational
from intelligence.contracts import campaign_group, validate_tactic_catalogue
from intelligence.synthesis import generate_evidence_activities
from intelligence.tactics import TACTICS
from sources.models import MetricDefinition
from catalogue.services import create_object
from tests.helpers import bootstrap, recording_csv, import_file, ensure_spotify_source


class Stage3Repair(TestCase):
    def setUp(self):
        bootstrap()
        ensure_spotify_source()

    def test_registry_groups_cover_types(self):
        from campaigns import registry

        for key in registry.TYPES:
            self.assertIn(campaign_group(key), ("release", "show", "growth"))

    def test_tactic_metrics_exist(self):
        errors = validate_tactic_catalogue(TACTICS)
        self.assertEqual(errors, [])

    def test_operational_preview_no_unconditional_gap(self):
        metric = MetricDefinition.objects.get(pk="spotify.recording.streams.v1")
        preview = preview_operational(
            {
                "type": "single",
                "start_date": date(2026, 11, 1),
                "end_date": date(2026, 12, 1),
                "key_date": date(2026, 11, 1),
                "object_label": "HYDROGEN",
                "primary_metric": metric,
                "resources": {"channels": ["instagram"]},
            }
        )
        self.assertFalse(any("No eligible evidence yet" in g for g in preview["gaps"]))

    def test_single_release_proposes_tactic_with_recording_observations(self):
        song = create_object("recording", "HYDROGEN", key_date=date(2026, 11, 1))
        import_file(recording_csv([("2026-10-01", 10), ("2026-10-02", 20), ("2026-10-03", 30)]), "hydrogen.csv", recording=song)
        metric = MetricDefinition.objects.get(pk="spotify.recording.streams.v1")
        op = preview_operational(
            {
                "type": "single",
                "start_date": date(2026, 11, 1),
                "end_date": date(2026, 12, 1),
                "key_date": song.key_date,
                "object_label": song.label,
                "primary_metric": metric,
                "resources": {"channels": ["instagram", "spotify"]},
            }
        )
        payload = {
            "type": "single",
            "name": "HYDROGEN",
            "start_date": "2026-11-01",
            "end_date": "2026-12-01",
            "object": {"mode": "existing", "id": str(song.pk)},
            "primary_outcome": {"metric_id": metric.pk, "mode": "new", "outcome_mode": "total", "target": 1000},
            "resources": {"channels": ["instagram", "spotify"]},
            "key_date": song.key_date.isoformat(),
        }
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(
                ok=True,
                data={"brief": f"Teaser for {song.label}", "cta": "Listen"},
                backend="mlx-lm",
                error="",
            )
            out = generate_evidence_activities(payload, op)
        self.assertTrue(out.get("recommendation_id"))
        self.assertGreater(len(out["activities"]), 0)
        self.assertTrue(any(a["channel"] in ("instagram", "spotify") for a in out["activities"]))

    def test_preview_recommendation_json_with_resource_dates(self):
        from datetime import date

        from django.test import Client

        from catalogue.services import create_object
        from intelligence.models import RecommendationRecord

        song = create_object("recording", "Date test", key_date=date(2026, 11, 1))
        client = Client(REMOTE_ADDR="127.0.0.1")
        body = {
            "use_evidence": True,
            "campaign": {
                "type": "single",
                "name": "JSON dates",
                "start_date": "2026-11-01",
                "end_date": "2026-12-01",
                "object": {"mode": "existing", "id": str(song.pk)},
                "primary_outcome": {
                    "mode": "new",
                    "metric_id": "spotify.recording.streams.v1",
                    "outcome_mode": "total",
                    "target": 100,
                },
                "resources": {
                    "channels": ["instagram"],
                    "assets_ready_date": "2026-10-25",
                    "blackout_dates": ["2026-11-15"],
                },
            },
        }
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(ok=True, data={"brief": "x", "cta": ""}, backend="mlx-lm", error="")
            res = client.post(
                "/api/campaigns/preview",
                data=__import__("json").dumps(body),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(RecommendationRecord.objects.exists())

    def test_adaptation_accept_applies_date(self):
        from core import clock
        from catalogue.services import own_artist
        from campaigns.models import Activity, Campaign
        from intelligence.adaptations import decide, propose

        campaign = Campaign.objects.create(
            name="T",
            artist=own_artist(),
            type="single",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 1),
            timezone="Australia/Perth",
            status="active",
            created_at=clock.now(),
        )
        act = Activity.objects.create(
            campaign=campaign,
            title="Post",
            origin="manual",
            origin_detail={},
            status="planned",
            all_day_date=date(2026, 11, 5),
            created_at=clock.now(),
        )
        prop = propose(campaign, "Reschedule", {"activities": [{"activity_id": str(act.pk), "date": "2026-11-10"}]}, {"reason": "test"})
        decide(prop.pk, "accept", str(uuid.uuid4()))
        act.refresh_from_db()
        self.assertEqual(act.all_day_date, date(2026, 11, 10))
