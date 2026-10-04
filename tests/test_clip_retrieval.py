"""Real CLIP ViT-B/32 retrieval on generated pixels. Requires the OpenAI checkpoint cached locally."""
import struct
import unittest

from django.test import TestCase

from context.models import ContentEmbedding, PeerMedia, PeerProfile
from core import clock
from intelligence.clip_adapter import ENCODER_ID, cosine, encode_rgb, encode_text, rank_vectors
from intelligence.inspiration_retrieve import retrieve_candidates
from tests.helpers import bootstrap


def _solid(rgb):
    return [rgb] * (64 * 64)


@unittest.skipUnless(__import__("importlib").util.find_spec("open_clip"), "open_clip is not installed")
class ClipRetrievalTests(TestCase):
    def test_colour_query_ranks_the_matching_image(self):
        try:
            red = encode_rgb(_solid((220, 30, 30)), 64, 64)
            blue = encode_rgb(_solid((30, 30, 220)), 64, 64)
            query = encode_text("a red square")
        except Exception as exc:
            self.fail(f"CLIP encode failed: {type(exc).__name__}: {exc}")
        self.assertEqual(len(red["vector"]), 512)
        self.assertGreater(cosine(red["vector"], query["vector"]), cosine(blue["vector"], query["vector"]))
        ranked = rank_vectors(query["vector"], [
            {"id": "blue", "vector": blue["vector"]},
            {"id": "red", "vector": red["vector"]},
        ])
        self.assertEqual(ranked[0]["id"], "red")

        bootstrap()
        peer = PeerProfile.objects.create(
            label="Colour", review_state="reviewed", peer_role="comparable", created_at=clock.now(), reviewed_at=clock.now()
        )
        red_post = PeerMedia.objects.create(peer=peer, external_id="red", caption="red", media_type="IMAGE", collected_at=clock.now())
        blue_post = PeerMedia.objects.create(peer=peer, external_id="blue", caption="blue", media_type="IMAGE", collected_at=clock.now())
        for post, vec in ((red_post, red["vector"]), (blue_post, blue["vector"])):
            ContentEmbedding.objects.create(
                post=post,
                encoder_version=ENCODER_ID,
                dimensions=512,
                vector_blob=struct.pack(f"<{len(vec)}f", *vec),
                vector_hash="test",
                created_at=clock.now(),
            )
        found = retrieve_candidates({"purpose": "", "visual_query": query["vector"]})
        visual_ids = [c["id"] for c in found["candidates"] if "visual" in (c.get("routes") or {})]
        self.assertEqual(visual_ids[0], str(red_post.pk))
        self.assertFalse(any("embedding_pending" in g for g in found["gaps"]))
