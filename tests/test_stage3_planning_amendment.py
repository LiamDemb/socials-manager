"""Stage 3 planning amendment: relevance vs evidence compatibility."""
import json
import uuid
from datetime import date
from unittest import mock

from django.test import Client, TestCase

from campaigns.services import preview_operational
from intelligence.composition import COMPOSITION_POLICY_VERSION, rank_and_compose
from intelligence.contracts import metric_ids_match
from intelligence.evidence_slices import build_metric_slice
from intelligence.needs import derive_campaign_needs
from intelligence.planning import resolve_planning_context
from intelligence.synthesis import generate_evidence_activities
from intelligence.tactics import TACTICS, candidate_tactics, tactic_observable_metrics
from intelligence.support import SUPPORT_SUPPORTED
from sources.models import MetricDefinition
from catalogue.services import create_object
from tests.helpers import bootstrap, recording_csv, import_file, ensure_spotify_source


class PlanningAmendmentTests(TestCase):
    def setUp(self):
        bootstrap()
        ensure_spotify_source()

    def _growth_payload(self, channels=None):
        return {
            "type": "audience_growth",
            "name": "Grow IG",
            "start_date": "2026-10-01",
            "end_date": "2026-10-30",
            "timezone": "Australia/Perth",
            "primary_outcome": {
                "metric_id": "instagram.account.followers.v1",
                "mode": "new",
                "outcome_mode": "gain",
                "target": 100,
            },
            "resources": {"channels": channels or ["instagram"]},
        }

    def test_story_allowed_for_follower_growth_without_metric_gate(self):
        ctx = resolve_planning_context(self._growth_payload())
        candidates, rejected = candidate_tactics("audience_growth", "launch", ctx["channels"], context=ctx)
        ids = {t["id"] for t in candidates}
        self.assertIn("ig_story_teaser", ids)
        self.assertFalse(any(r == "metric_mismatch" for _, r in rejected))

    def test_follower_growth_includes_story_as_hypothesis_without_evidence(self):
        preview = preview_operational(
            {
                "type": "audience_growth",
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 30),
                "primary_metric": MetricDefinition.objects.get(pk="instagram.account.followers.v1"),
                "resources": {"channels": ["instagram"]},
            }
        )
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(ok=True, data={"brief": "Story reminder", "cta": ""}, backend="mlx-lm", error="")
            out = generate_evidence_activities(self._growth_payload(), preview)
        story = [a for a in out["activities"] if a["template_key"] == "ig_story_teaser"]
        self.assertTrue(story, out.get("planning_notes"))
        self.assertEqual(story[0]["provenance"]["draft_kind"], "planning_hypothesis")
        self.assertNotEqual(story[0]["provenance"]["support"], SUPPORT_SUPPORTED)

    def test_email_hard_excluded_without_list(self):
        ctx = resolve_planning_context({**self._growth_payload(channels=["email"]), "resources": {"channels": ["email"]}})
        _, rejected = candidate_tactics("audience_growth", "launch", ["email"], context=ctx)
        self.assertTrue(any(t == "email_list_update" and r == "email_list_missing" for t, r in rejected))

    def test_release_vs_growth_needs_differ(self):
        ctx_g = resolve_planning_context(self._growth_payload())
        ctx_r = resolve_planning_context(
            {
                "type": "single",
                "start_date": "2026-11-01",
                "end_date": "2026-12-01",
                "primary_outcome": {"metric_id": "spotify.recording.streams.v1"},
                "resources": {"channels": ["instagram", "spotify"]},
            }
        )
        ng = derive_campaign_needs(ctx_g, {}, "launch")
        nr = derive_campaign_needs(ctx_r, {}, "launch")
        self.assertNotEqual(ng["role_priorities"][0], nr["role_priorities"][0])

    def test_irrelevant_metric_not_in_tactic_slice(self):
        song = create_object("recording", "SliceTest", key_date=date(2026, 11, 1))
        import_file(recording_csv([("2026-10-01", 5)]), "slice.csv", recording=song)
        ctx = resolve_planning_context(
            {
                "type": "single",
                "start_date": "2026-11-01",
                "end_date": "2026-12-01",
                "object": {"mode": "existing", "id": str(song.pk)},
                "primary_outcome": {"metric_id": "spotify.recording.streams.v1"},
            }
        )
        story = next(t for t in TACTICS if t["id"] == "ig_story_teaser")
        slice_ig = build_metric_slice(ctx, "instagram.account.followers.v1")
        self.assertFalse(any(r.get("metric_id") == "spotify.recording.streams.v1" for r in slice_ig["observation_refs"]))
        obs_story = set(tactic_observable_metrics(story))
        self.assertNotIn("spotify.recording.streams.v1", obs_story)

    def test_composition_deterministic(self):
        ctx = resolve_planning_context(self._growth_payload(channels=["instagram", "facebook"]))
        needs = derive_campaign_needs(ctx, {}, "launch")
        candidates, _ = candidate_tactics("audience_growth", "launch", ctx["channels"], context=ctx)
        from intelligence.evidence_slices import build_slices_for_tactics

        slices = build_slices_for_tactics(ctx, candidates)
        days = [date(2026, 10, 5), date(2026, 10, 7), date(2026, 10, 9)]
        a, meta_a, _ = rank_and_compose(candidates, ctx, needs, slices, days)
        b, meta_b, _ = rank_and_compose(candidates, ctx, needs, slices, days)
        self.assertEqual([x["tactic"]["id"] for x in a], [x["tactic"]["id"] for x in b])
        self.assertEqual(meta_a["composition_policy"], COMPOSITION_POLICY_VERSION)

    def test_streams_release_includes_ig_story_without_metric_mismatch(self):
        song = create_object("recording", "HYDROGEN2", key_date=date(2026, 11, 1))
        preview = preview_operational(
            {
                "type": "single",
                "start_date": date(2026, 11, 1),
                "end_date": date(2026, 12, 1),
                "object_label": song.label,
                "primary_metric": MetricDefinition.objects.get(pk="spotify.recording.streams.v1"),
                "resources": {"channels": ["instagram"]},
            }
        )
        payload = {
            "type": "single",
            "name": "HYDROGEN2",
            "start_date": "2026-11-01",
            "end_date": "2026-12-01",
            "object": {"mode": "existing", "id": str(song.pk)},
            "primary_outcome": {"metric_id": "spotify.recording.streams.v1", "mode": "new", "outcome_mode": "total", "target": 100},
            "resources": {"channels": ["instagram"]},
            "key_date": song.key_date.isoformat(),
        }
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(ok=True, data={"brief": "Teaser", "cta": ""}, backend="mlx-lm", error="")
            out = generate_evidence_activities(payload, preview)
        notes = " ".join(out.get("planning_notes") or [])
        self.assertNotIn("metric mismatch", notes.lower())
        self.assertTrue(any(a["template_key"] in ("ig_story_teaser", "ig_reel_teaser") for a in out["activities"]))

    def test_metric_ids_match_still_strict_for_evidence_families(self):
        self.assertFalse(
            metric_ids_match({"instagram.account.followers.v1"}, {"spotify.recording.streams.v1"})
        )
        self.assertTrue(metric_ids_match({"spotify.recording.streams.v1"}, {"spotify.recording.streams.v1"}))

    def test_approval_stores_provenance(self):
        client = Client(REMOTE_ADDR="127.0.0.1")
        preview = preview_operational(
            {
                "type": "audience_growth",
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 30),
                "primary_metric": MetricDefinition.objects.get(pk="instagram.account.followers.v1"),
                "resources": {"channels": ["instagram"]},
            }
        )
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(ok=True, data={"brief": "x", "cta": ""}, backend="mlx-lm", error="")
            ev = generate_evidence_activities(self._growth_payload(), preview)
        act = ev["activities"][0]
        body = {
            "campaign": {
                "name": "Grow IG",
                "type": "audience_growth",
                "start_date": "2026-10-01",
                "end_date": "2026-10-30",
                "primary_outcome": {"mode": "new", "metric_id": "instagram.account.followers.v1", "outcome_mode": "gain", "target": 100},
                "resources": {"channels": ["instagram"]},
                "activities": [act],
                "recommendation_id": ev["recommendation_id"],
            }
        }
        res = client.post(
            "/api/campaigns",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(res.status_code, 200, res.content)
        from campaigns.models import Activity

        data = json.loads(res.content)["data"]
        created = Activity.objects.get(pk=data["activities"][0])
        self.assertIn("strategic_fit", created.origin_detail.get("provenance", {}))
        self.assertEqual(created.origin_detail["provenance"].get("tactic_catalogue_version"), "tactics-v3")
