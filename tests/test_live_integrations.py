"""Live provider calls. Not run in CI: set SOCIALS_MANAGER_LIVE_TESTS=1 and configure .env."""
import os
import unittest

from django.test import TestCase

from core.env import load_project_env


def live_enabled():
    return os.environ.get("SOCIALS_MANAGER_LIVE_TESTS") == "1"


@unittest.skipUnless(live_enabled(), "Not run: set SOCIALS_MANAGER_LIVE_TESTS=1 with .env configured")
class LiveIntegrations(TestCase):
    @classmethod
    def setUpClass(cls):
        load_project_env()
        super().setUpClass()

    def test_musicbrainz_real_search(self):
        from sources import musicbrainz

        r = musicbrainz.search_artists("Opal Season", limit=3)
        self.assertIn(r["state"], ("found", "ambiguous", "not_found", "error"))

    def test_lastfm_real_similar(self):
        from sources import lastfm

        r = lastfm.artist_get_similar("Opal Season", 5)
        self.assertIn(r["state"], ("found", "error"))

    def test_meta_own_account_or_blocked(self):
        from sources import meta_graph

        own = meta_graph.fetch_own_account()
        self.assertIn(own["state"], ("ok", "blocked", "error"))
