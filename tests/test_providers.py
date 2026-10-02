"""Provider adapters with mocked HTTP (synthetic). Live retrieval is test_live_integrations.py."""
import json
from unittest import mock

from django.test import TestCase

from tests.helpers import bootstrap


class Providers(TestCase):
    def setUp(self):
        bootstrap()

    @mock.patch("sources.musicbrainz.musicbrainz_get")
    def test_musicbrainz_search_ambiguous(self, mb):
        mb.return_value = mock.Mock(ok=True, status=200, data={"artists": [{"id": "a1", "name": "A"}, {"id": "a2", "name": "B"}]})
        from sources import musicbrainz

        r = musicbrainz.search_artists("Opal Season")
        self.assertEqual(r["state"], "ambiguous")
        self.assertEqual(len(r["candidates"]), 2)

    @mock.patch("sources.lastfm.lastfm_get")
    def test_lastfm_similar(self, lf):
        lf.return_value = mock.Mock(
            ok=True,
            status=200,
            data={"similarartists": {"artist": [{"name": "Peer A", "match": "0.5", "url": "http://x", "mbid": ""}]}},
        )
        from sources import lastfm

        r = lastfm.artist_get_similar("Opal Season", 5)
        self.assertEqual(r["state"], "found")
        self.assertEqual(r["similar"][0]["name"], "Peer A")

    @mock.patch("sources.meta_graph.graph_get")
    def test_meta_business_discovery_blocked_without_page(self, gg):
        gg.side_effect = [
            mock.Mock(ok=True, data={"data": {"scopes": []}}),
            mock.Mock(ok=True, data={"id": "1"}),
            mock.Mock(ok=True, data={"data": []}),
        ]
        from sources import meta_graph

        cfg = meta_graph.inspect_configuration()
        self.assertFalse(cfg["business_discovery_supported"])
