"""Contract tests T01-T11 subset for media intelligence plan."""
from datetime import timedelta
from unittest import mock

from django.test import TestCase

from context.inspiration_services import attach_reference, detach_reference, save_peer_media
from context.library import explore_media_queryset
from context.media_capability import resolve_media_capability
from context.models import InspirationReference, PeerMedia, PeerProfile, PeerMediaMetricSnapshot
from core import clock
from intelligence.inspiration_rank import reciprocal_rank_fusion, rank_candidates
from intelligence.peer_snapshots import select_snapshot_at_age
from intelligence.response_support import performance_adjustment
from tests.helpers import bootstrap


class LibraryContractTests(TestCase):
    def setUp(self):
        bootstrap()
        self.peer = PeerProfile.objects.create(
            label="P",
            review_state="reviewed",
            peer_role="comparable",
            created_at=clock.now(),
            reviewed_at=clock.now(),
        )
        self.media = PeerMedia.objects.create(
            peer=self.peer,
            external_id="1",
            caption="teaser",
            media_type="VIDEO",
            collected_at=clock.now(),
        )

    def test_t01_save_attach_detach(self):
        ref = save_peer_media(self.media.pk)
        from campaigns.models import Activity, Campaign
        from catalogue.services import own_artist

        camp = Campaign.objects.create(
            artist=own_artist(),
            type="release",
            name="c",
            start_date=clock.now().date(),
            end_date=clock.now().date() + timedelta(days=1),
            timezone="Australia/Perth",
            created_at=clock.now(),
        )
        a1 = Activity.objects.create(campaign=camp, title="a1", timezone="Australia/Perth", created_at=clock.now())
        a2 = Activity.objects.create(campaign=camp, title="a2", timezone="Australia/Perth", created_at=clock.now())
        attach_reference(a1.pk, ref.pk)
        attach_reference(a2.pk, ref.pk)
        detach_reference(a1.pk, ref.pk)
        self.assertEqual(ref.activity_links.count(), 1)
        self.assertEqual(PeerMedia.objects.count(), 1)


class CapabilityTests(TestCase):
    def setUp(self):
        bootstrap()

    def test_t02_manual_save_not_auto_analytical_pool(self):
        from context.inspiration_services import add_manual_reference

        ref = add_manual_reference("x", "https://example.com/x")
        self.assertFalse(ref.in_analytical_pool)

    @mock.patch("context.media_capability.purpose_state", return_value=("denied", "denied"))
    def test_t02_denied_operation(self, _):
        peer = PeerProfile.objects.create(
            label="p", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        media = PeerMedia.objects.create(peer=peer, external_id="m", collected_at=clock.now())
        cap = resolve_media_capability(media, "feature_extract_multimodal")
        self.assertEqual(cap["state"], "denied")

    @mock.patch("context.media_capability.purpose_state", return_value=("unknown", "unresolved"))
    def test_t02_unresolved_is_not_denied(self, _):
        peer = PeerProfile.objects.create(
            label="p2", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        media = PeerMedia.objects.create(peer=peer, external_id="m2", collected_at=clock.now())
        cap = resolve_media_capability(media, "feature_extract_multimodal")
        self.assertEqual(cap["state"], "unknown")
        self.assertEqual(cap["reason"], "source_use_unknown")


class RankFusionTests(TestCase):
    def test_t09_rrf_normalised(self):
        card = {"id": "1", "routes": {"structured": 1, "fts": 2}}
        score = reciprocal_rank_fusion(card)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1.0)


class TierTests(TestCase):
    def test_t08_tier_and_rank(self):
        request = {"purpose": "teaser", "format": "video", "channel": "instagram"}
        retrieval = {
            "candidates": [
                {
                    "id": "a",
                    "peer_label": "A",
                    "media_type": "VIDEO",
                    "caption_excerpt": "teaser clip",
                    "structured_score": 5,
                    "routes": {"structured": 1},
                    "media_type_display": "Video",
                },
                {
                    "id": "b",
                    "peer_label": "B",
                    "media_type": "VIDEO",
                    "caption_excerpt": "unrelated",
                    "routes": {},
                },
            ]
        }
        ranked = rank_candidates(request, retrieval)
        self.assertTrue(any(c["id"] == "a" for c in ranked["candidates"]))
        self.assertTrue(any(e["id"] == "b" for e in ranked["excluded"]))


class PerformanceAdjustmentTests(TestCase):
    def test_t10_unknown_neutral(self):
        b, _, pathway = performance_adjustment({"id": "missing"}, mode="best_fit")
        self.assertEqual(pathway, "none")
        self.assertEqual(b, 0.0)


class StorageQuotaTests(TestCase):
    def test_t03_quota_blocks_over_cap(self):
        from context.media_storage import quota_allows

        from context import media_config

        old = media_config.QUOTAS["preview_analysis_bytes"]
        media_config.QUOTAS["preview_analysis_bytes"] = 10
        try:
            ok, reason = quota_allows(20)
            self.assertFalse(ok)
            self.assertEqual(reason, "quota_exceeded")
        finally:
            media_config.QUOTAS["preview_analysis_bytes"] = old


class SnapshotAgeTests(TestCase):
    def setUp(self):
        bootstrap()
        self.peer = PeerProfile.objects.create(
            label="P", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        pub = clock.now() - timedelta(hours=200)
        self.media = PeerMedia.objects.create(
            peer=self.peer, external_id="1", published_at=pub, collected_at=clock.now()
        )

    def test_t11_rejects_wrong_age(self):
        PeerMediaMetricSnapshot.objects.create(
            media=self.media,
            captured_at=clock.now(),
            metrics={"like_count": 5},
        )
        snap, reason = select_snapshot_at_age(self.media)
        self.assertIsNone(snap)
        self.assertEqual(reason, "insufficient_age_snapshots")


class SamplingTests(TestCase):
    def test_t04_frames_carousel_and_oversize(self):
        from context.visual_descriptors import carousel_selection, compute_video_frame_targets, reject_oversize_frame

        short = compute_video_frame_targets(2)
        self.assertLessEqual(short["frame_count"], 8)
        times = [f["target_seconds"] for f in short["frames"]]
        self.assertEqual(len(times), len(set(times)))
        long = compute_video_frame_targets(400)
        self.assertTrue(long["partial_segment"])
        self.assertEqual(long["palette_name"], "sampled first segment")
        self.assertLessEqual(long["frame_count"], 12)
        picked = carousel_selection(12)
        self.assertEqual(len(picked["selected_indices"]), 8)
        self.assertTrue(picked["omitted_indices"])
        self.assertEqual(reject_oversize_frame(10000, 6000), "oversize_frame")

    def test_t05_uniform_palette_ignores_opening_only(self):
        from context.visual_descriptors import compute_visual_descriptors, uniform_palette

        red = [(1.0, 0.0, 0.0)] * 20
        blue = [(0.0, 0.0, 1.0)] * 20
        opening = {**compute_visual_descriptors(red), "roles": ["hook_opening"]}
        uniform = {**compute_visual_descriptors(blue), "roles": ["palette_uniform"]}
        pooled = uniform_palette([opening, uniform])
        self.assertAlmostEqual(pooled["mean_luminance"], uniform["mean_luminance"])
        unknown = compute_visual_descriptors([(1.0, 0.0, 0.0)], colour_space="hdr")
        self.assertIsNone(unknown["mean_luminance"])
        self.assertIsNone(uniform["temporal"]["cut_rate"])


class ExtractionContractTests(TestCase):
    def test_t06_rejects_invented_fields(self):
        from intelligence.extraction_validate import validate_extraction

        out = validate_extraction(
            {
                "fields": [
                    {"feature_key": "made_up", "value": True, "support": [{"asset_id": "x"}]},
                    {"feature_key": "teaser", "value": True, "support": []},
                    {"feature_key": "teaser", "value": True, "support": [{"asset_id": "missing"}]},
                ],
                "output": {"description": "This performed well."},
            },
            known_asset_ids={"real"},
        )
        self.assertEqual(out["fields"], [])
        self.assertGreaterEqual(len(out["rejected"]), 3)
        self.assertEqual(out["description"], "")

    def test_t07_review_appends_and_omits_popularity(self):
        from context.content_features import review_features
        from context.models import ContentFeatureValue, MediaPack
        from intelligence.extraction_adapter import extract_labels

        bootstrap()
        peer = PeerProfile.objects.create(
            label="P", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        media = PeerMedia.objects.create(
            peer=peer,
            external_id="pop",
            caption="teaser",
            snapshot={"like_count": 99999},
            collected_at=clock.now(),
        )
        pack = MediaPack.objects.create(post=media, profile_version="media-compact-v1", input_hash="h", created_at=clock.now())
        labels = extract_labels(media, pack)
        blob = str(labels)
        self.assertNotIn("99999", blob)
        ContentFeatureValue.objects.create(
            post=media,
            feature_key="teaser",
            value_json={"value": True},
            review_state="suggested",
            review_revision=1,
            support=[{"kind": "caption_span"}],
            created_at=clock.now(),
        )
        review_features(media.pk, [{"feature_key": "teaser", "review_state": "corrected", "value": False}], expected_revision=1)
        self.assertEqual(ContentFeatureValue.objects.filter(post=media, feature_key="teaser").count(), 2)
        latest = ContentFeatureValue.objects.filter(post=media, feature_key="teaser").order_by("-created_at").first()
        self.assertEqual(latest.review_state, "corrected")
        self.assertEqual(latest.review_revision, 2)


class RankingPolicyTests(TestCase):
    def test_t08_transfer_tier(self):
        request = {"purpose": "teaser", "format": "video"}
        retrieval = {
            "route_counts": {"structured": 1},
            "candidates": [
                {
                    "id": "carousel-post",
                    "peer_label": "A",
                    "media_type": "CAROUSEL_ALBUM",
                    "media_type_display": "Carousel",
                    "reviewed_purpose": "teaser",
                    "routes": {"structured": 1},
                    "caption_excerpt": "",
                }
            ],
        }
        ranked = rank_candidates(request, retrieval)
        self.assertEqual(ranked["candidates"][0]["tier"], 2)
        self.assertTrue(any(r["kind"] == "transfer_assumption" for r in ranked["candidates"][0]["reasons"]))

    def test_t09_mmr_and_rrf_denominator(self):
        from intelligence.inspiration_rank import mmr_select

        card = {"id": "1", "routes": {"structured": 1, "fts": 2}}
        score = reciprocal_rank_fusion(card, available_routes=["structured", "fts"])
        expected = ((1 / 61) + (1 / 62)) / (2 / 61)
        self.assertAlmostEqual(score, expected)
        items = [{"id": str(i), "peer_label": "Same", "utility": 0.4, "canonical_key": str(i)} for i in range(4)]
        selected, relaxed = mmr_select(items, 4)
        self.assertTrue(relaxed)
        self.assertEqual(len(selected), 4)

    def test_t10_viral_does_not_change_tier(self):
        request = {"purpose": "teaser", "format": "video"}
        retrieval = {
            "route_counts": {"structured": 1},
            "candidates": [
                {
                    "id": "fit",
                    "peer_label": "A",
                    "media_type": "VIDEO",
                    "reviewed_purpose": "teaser",
                    "routes": {"structured": 1},
                    "caption_excerpt": "teaser",
                    "public_likes": 1,
                },
                {
                    "id": "viral",
                    "peer_label": "B",
                    "media_type": "IMAGE",
                    "routes": {},
                    "caption_excerpt": "unrelated",
                    "public_likes": 1000000,
                },
            ],
        }
        ranked = rank_candidates(request, retrieval)
        self.assertEqual(ranked["candidates"][0]["id"], "fit")
        self.assertEqual(ranked["candidates"][0]["tier"], 1)
        self.assertTrue(any(e["id"] == "viral" for e in ranked["excluded"]))


class ContentAssociationTests(TestCase):
    def test_t11_one_post_one_row(self):
        from context.models import MediaAsset

        bootstrap()
        peer = PeerProfile.objects.create(
            label="P", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        media = PeerMedia.objects.create(
            peer=peer,
            external_id="one",
            media_type="VIDEO",
            snapshot={"like_count": 3},
            collected_at=clock.now(),
        )
        for i in range(4):
            MediaAsset.objects.create(post=media, role="analysis_frame", captured_at=clock.now(), byte_size=10)
        from intelligence.peer_dataset import build_peer_post_dataset

        ds = build_peer_post_dataset()
        self.assertEqual(len(ds["post_rows"]), 1)
        self.assertEqual(ds["post_rows"][0]["frame_count"], 4)

    def test_t12_confounded_and_repeated_rows(self):
        from intelligence.stats.content_association import contrast

        rows = []
        for i in range(10):
            rows.append(
                {
                    "peer_media_id": f"a{i}",
                    "peer_id": "artist-a",
                    "response": 10,
                    "response_basis": "post-age-7d-v1",
                    "features": {"reviewed_purpose": "teaser"},
                }
            )
            rows.append(
                {
                    "peer_media_id": f"b{i}",
                    "peer_id": "artist-b",
                    "response": 1,
                    "response_basis": "post-age-7d-v1",
                    "features": {"reviewed_purpose": "announcement"},
                }
            )
        blocked = contrast(rows, "reviewed_purpose", {"min_per_level": 10})
        self.assertEqual(blocked["blocker_code"], "confounded_artist")
        mixed = []
        for i in range(10):
            mixed.append(
                {
                    "peer_media_id": f"t{i}",
                    "peer_id": "artist-a" if i % 2 == 0 else "artist-b",
                    "response": 10,
                    "response_basis": "post-age-7d-v1",
                    "features": {"reviewed_purpose": "teaser"},
                }
            )
            mixed.append(
                {
                    "peer_media_id": f"n{i}",
                    "peer_id": "artist-a" if i % 2 else "artist-c",
                    "response": 2,
                    "response_basis": "post-age-7d-v1",
                    "features": {"reviewed_purpose": "announcement"},
                }
            )
        repeated = contrast(mixed + mixed, "reviewed_purpose", {"min_per_level": 10})
        self.assertEqual(repeated["groups"]["teaser"]["n"], 10)


class IntegrationGuardTests(TestCase):
    def test_t13_ask_does_not_attach(self):
        from context.models import ActivityReference
        from intelligence.ask_retrieval import retrieve_for_question

        bootstrap()
        before = ActivityReference.objects.count()
        retrieve_for_question("show rehearsal teaser examples")
        self.assertEqual(ActivityReference.objects.count(), before)

    def test_t15_save_does_not_mark_fits(self):
        from context.inspiration_services import save_peer_media
        from context.media_invalidation import note_preference_only_save

        bootstrap()
        peer = PeerProfile.objects.create(
            label="P", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        media = PeerMedia.objects.create(peer=peer, external_id="s", collected_at=clock.now())
        with mock.patch("intelligence.lineage.mark_fits_stale") as stale:
            save_peer_media(media.pk)
            self.assertFalse(stale.called)
        self.assertFalse(note_preference_only_save("x")["fits_invalidated"])

    def test_t03_dedup_and_cap(self):
        from context.media_storage import read_bounded, store_blob, usage_bytes

        a, path_a = store_blob(b"same-bytes", ext="bin")
        b, path_b = store_blob(b"same-bytes", ext="bin")
        self.assertEqual(a, b)
        self.assertEqual(path_a, path_b)
        self.assertEqual(usage_bytes(), len(b"same-bytes"))
        with self.assertRaises(ValueError):
            read_bounded([b"abcdef"], 3)

    def test_t02_private_url_and_manual_upload_mime(self):
        from context.media_acquire import assert_public_http_url, sniff_image_mime

        with self.assertRaises(ValueError):
            assert_public_http_url("http://127.0.0.1/secret.jpg")
        self.assertIsNone(sniff_image_mime(b"not-an-image"))

    def test_t17_library_without_invented_assets(self):
        from context.library import explore_media_queryset
        from context.models import MediaAsset

        bootstrap()
        peer = PeerProfile.objects.create(
            label="P", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        PeerMedia.objects.create(peer=peer, external_id="legacy", caption="kept", collected_at=clock.now())
        self.assertEqual(explore_media_queryset().count(), 1)
        self.assertEqual(MediaAsset.objects.count(), 0)
        from django.test import Client

        client = Client(REMOTE_ADDR="127.0.0.1")
        media = PeerMedia.objects.get(external_id="legacy")
        self.assertEqual(client.get("/inspiration").status_code, 200)
        self.assertEqual(client.get(f"/inspiration/posts/{media.pk}").status_code, 200)
        self.assertEqual(client.get("/inspiration/review").status_code, 200)
        self.assertEqual(client.get("/settings").status_code, 200)
