"""Connected owner-image path: store, describe, embed, review, retrieve, attach."""
import io
import unittest

from django.test import TestCase

from campaigns.models import Campaign
from catalogue.services import own_artist
from context.content_features import review_features
from context.inspiration_services import attach_reference, save_peer_media
from context.models import ActivityReference, PeerProfile
from context.owner_asset import ingest_owner_image
from core import clock
from intelligence.clip_adapter import encode_text
from intelligence.inspiration_retrieve import retrieve_candidates
from intelligence.inspiration_service import recommend_for_activity
from tests.helpers import bootstrap


def _png(rgb):
    from PIL import Image

    image = Image.new("RGB", (64, 64), rgb)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@unittest.skipUnless(__import__("importlib").util.find_spec("open_clip"), "open_clip is not installed")
class OwnerAssetWorkflowTests(TestCase):
    def test_local_image_is_retrieved_and_attached(self):
        bootstrap()
        try:
            red = ingest_owner_image(_png((210, 40, 40)), caption="release teaser artwork")
            blue = ingest_owner_image(_png((30, 40, 210)), caption="studio still")
            query = encode_text("a red square")
        except Exception as exc:
            self.fail(f"owner-asset processing failed: {type(exc).__name__}: {exc}")

        self.assertFalse(red["instagram_policy_consulted"])
        self.assertEqual(red["descriptors"]["status"], "ready")
        self.assertIsNotNone(red["descriptors"]["mean_luminance"])
        self.assertEqual(red["embedding"]["state"], "stored")
        self.assertEqual(red["embedding"]["dimensions"], 512)
        self.assertNotEqual(red["gemma"].get("state"), "embedding_pending")
        self.assertEqual(red["proposed_purpose"], "teaser")
        self.assertEqual(PeerProfile.objects.get(label="Owner library").peer_role, "reference_only")

        review_features(red["post_id"], [{"feature_key": "reviewed_purpose", "review_state": "accepted", "value": "teaser"}])
        found = retrieve_candidates({"purpose": "teaser", "format": "image", "visual_query": query["vector"]})
        self.assertFalse(any("embedding_pending" in gap for gap in found["gaps"]))
        visual_ids = [card["id"] for card in found["candidates"] if "visual" in (card.get("routes") or {})]
        self.assertEqual(visual_ids[0], red["post_id"])
        self.assertIn(blue["post_id"], visual_ids)

        artist = own_artist()
        campaign = Campaign.objects.create(
            artist=artist,
            type="release",
            name="Owner asset",
            start_date=clock.now().date(),
            end_date=clock.now().date(),
            timezone="Australia/Perth",
            created_at=clock.now(),
        )
        from campaigns.models import Activity

        activity = Activity.objects.create(
            campaign=campaign,
            title="Teaser post",
            purpose="teaser",
            format="image",
            timezone="Australia/Perth",
            created_at=clock.now(),
        )
        recommendation = recommend_for_activity(
            activity, context={"purpose": "teaser", "format": "image"}, limit=5
        )
        ids = [item["id"] for item in recommendation["suggestions"]]
        self.assertIn(red["post_id"], ids)
        chosen = next(item for item in recommendation["suggestions"] if item["id"] == red["post_id"])
        self.assertEqual(chosen["tier"], 1)
        saved = save_peer_media(red["post_id"], note="owner asset")
        link = attach_reference(activity.pk, saved.pk, origin="owner_attach")
        self.assertEqual(ActivityReference.objects.filter(pk=link.pk, activity=activity).count(), 1)
