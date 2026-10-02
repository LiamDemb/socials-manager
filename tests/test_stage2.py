"""Stage 2 acceptance slices: Meta probe blocked, collector, findings lineage, peers, policy gates."""
import json
import os
from datetime import date

from django.test import TestCase

from tests.helpers import bootstrap, recording
from context.models import PeerProfile
from context.services import ensure_default_peers
from core.services import enqueue
from findings.models import Finding
from findings.services import publish_window_comparison
from sources import instagram
from sources.collector import run_collect
from sources.models import Source
from sources.services import current_policy, ensure_spotify_source


class Stage2(TestCase):
    def setUp(self):
        bootstrap()
        ensure_spotify_source()
        ensure_default_peers()

    def test_ac14_instagram_probe_blocked_without_credentials(self):
        from sources.models import SourcePolicyVersion

        source = instagram.ensure_instagram_source(Source, SourcePolicyVersion)
        self.assertEqual(source.capability["live_integration"], "Blocked")
        self.assertEqual(source.capability["handle"], "opalseason_")
        policy = current_policy(source)
        self.assertIn(policy.purposes["collect"], ("unresolved", "allowed"))

    def test_ac15_collect_job_blocked_does_not_fake_metrics(self):
        from sources.models import SourcePolicyVersion

        instagram.ensure_instagram_source(Source, SourcePolicyVersion)
        job = enqueue("collect.source", "instagram:graph_api", "test")
        job.refresh_from_db()
        result = run_collect(job)
        self.assertEqual(result["state"], "blocked")

    def test_ac16_finding_carries_lineage(self):
        song = recording("Lineage song")
        publish_window_comparison(song.entity, "spotify.recording.streams.v1", "Test finding", "Summary", date(2026, 9, 1), date(2026, 9, 7), [])
        f = Finding.objects.get()
        self.assertEqual(f.status, "published")
        self.assertIn("observation_refs", f.lineage)

    def test_ac17_peer_fixture_is_reviewed_not_live(self):
        peer = PeerProfile.objects.get()
        self.assertEqual(peer.review_state, "reviewed")
        self.assertEqual(peer.capability.get("live_collection"), "blocked")

    def test_ac26_spotify_policy_allows_all_purposes(self):
        policy = current_policy(ensure_spotify_source())
        self.assertEqual(policy.purposes["statistical_fit"], "allowed")
        self.assertTrue(policy.allows("llm_ingest"))

    def test_instagram_probe_uses_meta_configuration(self):
        from unittest import mock
        from sources.models import SourcePolicyVersion

        with mock.patch("sources.instagram.probe_live", return_value={"live_integration": "Passed", "handle": "opalseason_"}):
            source = instagram.ensure_instagram_source(Source, SourcePolicyVersion)
            self.assertEqual(source.capability["live_integration"], "Passed")
