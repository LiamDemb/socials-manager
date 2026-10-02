"""Provider adapters with mocked HTTP (synthetic). Live retrieval is test_live_integrations.py."""
import json
import os
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

    @mock.patch.dict(os.environ, {"META_ACCESS_TOKEN": "meta-user-token"}, clear=False)
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

    @mock.patch.dict(
        os.environ,
        {"INSTAGRAM_ACCESS_TOKEN": "ig-token", "META_ACCESS_TOKEN": "meta-user-token"},
        clear=False,
    )
    @mock.patch("sources.meta_graph._instagram_basic_me")
    @mock.patch("sources.meta_graph.graph_get")
    def test_meta_graph_uses_meta_token_when_both_tokens_set(self, gg, ig_me):
        ig_me.return_value = {"user_id": "ig-basic-id", "username": "from_ig"}
        gg.side_effect = [
            mock.Mock(ok=True, data={"data": {"scopes": ["pages_show_list"]}}),
            mock.Mock(ok=True, data={"id": "fb-user"}),
            mock.Mock(
                ok=True,
                data={"data": [{"id": "page-1", "name": "Opal", "instagram_business_account": {"id": "ig-biz-99"}}]},
            ),
            mock.Mock(ok=True, data={"username": "from_graph", "followers_count": 100}),
        ]
        from sources import meta_graph

        cfg = meta_graph.inspect_configuration()
        self.assertTrue(cfg["business_discovery_supported"])
        self.assertEqual(cfg["facebook_page_id"], "page-1")
        self.assertEqual(cfg["auth_route"], "facebook_login_graph")
        for call in gg.call_args_list:
            self.assertEqual(call[0][1], "meta-user-token")
