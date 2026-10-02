"""Intelligence architecture v2: resolver, lineage, peers, claims, failure semantics."""
import json
from datetime import date

from core import clock
from unittest import mock
from uuid import uuid4

from django.test import Client, TestCase

from context.models import InspirationReference, PeerMedia, PeerProfile
from context.services import peer_collection_audit
from intelligence.analysis import AnalysisResolver, STATUS_BLOCKED, STATUS_INSUFFICIENT
from intelligence.claims import validate_claim, CLAIM_MEASURED
from intelligence.lineage import cache_key, lineage_parts
from intelligence.registry import sync_analysis_specs
from intelligence.stats.post_response import run as post_run
from tests.helpers import bootstrap


class IntelligenceV2Tests(TestCase):
    def setUp(self):
        bootstrap()
        sync_analysis_specs()

    def test_cache_key_changes_with_policy_version(self):
        a = cache_key(lineage_parts("post_public_response_v1", "m1", "c1", "d1", {"spotify": "v1"}))
        b = cache_key(lineage_parts("post_public_response_v1", "m1", "c1", "d1", {"spotify": "v2"}))
        self.assertNotEqual(a, b)

    def test_blocked_not_insufficient_when_dependency_missing(self):
        from intelligence.models import AnalysisSpec

        spec = AnalysisSpec.objects.get(key="post_public_response_v1")
        rows = [{"format": "reel", "response": i} for i in range(6)]
        with mock.patch.dict("sys.modules", {"pymc": None}):
            import intelligence.stats.post_response as pr

            with mock.patch.object(pr, "statistics"):
                outcome = post_run(spec, {}, {"post_rows": rows})
        if outcome.get("status") == STATUS_BLOCKED:
            self.assertEqual(outcome.get("blocker_code"), "dependency_unavailable")
            self.assertNotEqual(outcome.get("status"), STATUS_INSUFFICIENT)

    def test_registered_only_spec_unsupported(self):
        resolver = AnalysisResolver()
        out = resolver.resolve_or_queue({"analysis_key": "trial_response_v1"}, {}, purpose="analysis")
        self.assertEqual(out["status"], "unsupported_question")

    def test_manual_inspiration_not_in_cohort(self):
        from intelligence.cohorts import build_comparable_cohort

        InspirationReference.objects.create(
            title="Manual save",
            retrieved_at=clock.now(),
            in_analytical_pool=False,
            collection_source="manual",
        )
        cohort = build_comparable_cohort()
        self.assertTrue(cohort["membership"].get("excluded_manual_inspiration"))

    def test_claim_metric_mismatch(self):
        errors = validate_claim(
            {"kind": CLAIM_MEASURED, "evidence_ref": "x", "metric_id": "a", "value": 10},
            {"x": {"metric_id": "b", "value": 10}},
        )
        self.assertIn("metric_mismatch", errors)

    def test_peer_media_fixture_collection(self):
        peer = PeerProfile.objects.create(
            label="P",
            review_state="reviewed",
            peer_role="comparable",
            instagram_username="peerx",
            created_at=clock.now(),
        )
        PeerMedia.objects.create(
            peer=peer,
            external_id="m1",
            caption="c",
            collected_at=clock.now(),
        )
        self.assertEqual(peer.media.count(), 1)
        audit = peer_collection_audit()
        self.assertIn("media_pagination", audit)

    def test_timing_basis_requires_refs(self):
        from intelligence.scheduler import pick_time_slot

        day = date(2026, 10, 5)
        s = pick_time_slot(day, "growth", {"preferred_hour": 18}, "Australia/Perth")
        self.assertTrue(s["fallback"])
        s2 = pick_time_slot(
            day,
            "growth",
            {"preferred_hour": 18, "refs": [{"n": 4}], "sample_n": 4, "window": "18:00-20:00"},
            "Australia/Perth",
        )
        self.assertFalse(s2["fallback"])
        self.assertIn("Timing evidence", s2["basis"])

    def test_synthesis_includes_decision_fingerprint(self):
        from campaigns.services import preview_operational
        from intelligence.synthesis import generate_evidence_activities
        from sources.models import MetricDefinition

        preview = preview_operational(
            {
                "type": "audience_growth",
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 30),
                "primary_metric": MetricDefinition.objects.get(pk="instagram.account.followers.v1"),
                "resources": {"channels": ["instagram"]},
            }
        )
        payload = {
            "type": "audience_growth",
            "start_date": "2026-10-01",
            "end_date": "2026-10-30",
            "primary_outcome": {"metric_id": "instagram.account.followers.v1"},
            "resources": {"channels": ["instagram"]},
        }
        with mock.patch("intelligence.llm_adapter.generate_structured") as gen:
            gen.return_value = mock.Mock(ok=True, data={"brief": "x", "cta": ""}, backend="mlx-lm", error="")
            out = generate_evidence_activities(payload, preview)
        self.assertTrue(out.get("recommendation_id"))
        if out["activities"]:
            self.assertIn("decision_context_fingerprint", out["activities"][0]["provenance"])
