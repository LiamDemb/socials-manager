"""Peers → inspiration library, attachments, and analysis dataset wiring."""
from datetime import timedelta

from django.test import TestCase

from campaigns.models import Activity, Campaign
from context.inspiration_services import (
    add_manual_reference,
    attach_reference,
    detach_reference,
    save_peer_media,
    unsave_reference,
)
from context.library import explore_media_queryset, saved_references_queryset
from context.models import InspirationReference, PeerMedia, PeerProfile
from core import clock
from intelligence.peer_dataset import build_peer_post_dataset
from tests.helpers import bootstrap


class PeersInspirationLibraryTests(TestCase):
    def setUp(self):
        bootstrap()
        self.peer = PeerProfile.objects.create(
            label="Peer A",
            instagram_username="peera",
            review_state="reviewed",
            peer_role="comparable",
            created_at=clock.now(),
            reviewed_at=clock.now(),
        )
        self.media = PeerMedia.objects.create(
            peer=self.peer,
            external_id="ig1",
            caption="Teaser clip",
            media_type="VIDEO",
            permalink="https://instagram.com/p/abc",
            snapshot={"like_count": 10, "comments_count": 2},
            collected_at=clock.now(),
        )

    def test_explore_lists_collected_posts_immediately(self):
        self.assertEqual(explore_media_queryset().count(), 1)

    def test_save_idempotent_and_unsave(self):
        ref1 = save_peer_media(self.media.pk)
        ref2 = save_peer_media(self.media.pk)
        self.assertEqual(ref1.pk, ref2.pk)
        self.assertEqual(saved_references_queryset().count(), 1)
        unsave_reference(ref1.pk)
        self.assertFalse(InspirationReference.objects.filter(pk=ref1.pk, is_bookmark=True).exists())

    def test_manual_reference(self):
        ref = add_manual_reference("Blog", "https://example.com/post", note="idea")
        self.assertEqual(ref.origin_type, "manual")
        self.assertIn(ref, saved_references_queryset())

    def test_attach_multiple_activities(self):
        ref = save_peer_media(self.media.pk)
        from catalogue.services import own_artist

        camp = Campaign.objects.create(
            artist=own_artist(),
            type="release",
            name="C",
            start_date=clock.now().date(),
            end_date=clock.now().date() + timedelta(days=7),
            timezone="Australia/Perth",
            created_at=clock.now(),
        )
        a1 = Activity.objects.create(
            campaign=camp, title="A1", timezone="UTC", created_at=clock.now(), origin="manual"
        )
        a2 = Activity.objects.create(
            campaign=camp, title="A2", timezone="UTC", created_at=clock.now(), origin="manual"
        )
        attach_reference(a1.pk, ref.pk)
        attach_reference(a2.pk, ref.pk)
        detach_reference(a1.pk, ref.pk)
        self.assertEqual(ref.activity_links.count(), 1)

    def test_excluded_peer_not_in_explore(self):
        self.peer.peer_role = "excluded"
        self.peer.save()
        self.assertEqual(explore_media_queryset().count(), 0)

    def test_dataset_builder_uses_metrics(self):
        ds = build_peer_post_dataset()
        self.assertEqual(len(ds["post_rows"]), 1)
        self.assertEqual(ds["post_rows"][0]["response"], 12.0)

    def test_dataset_honest_gap_without_metrics(self):
        PeerMedia.objects.create(
            peer=self.peer,
            external_id="ig2",
            caption="No metrics",
            media_type="IMAGE",
            snapshot={},
            collected_at=clock.now(),
        )
        ds = build_peer_post_dataset()
        self.assertEqual(len(ds["post_rows"]), 1)
        self.assertTrue(any(x["reason"] == "no_public_metrics_at_capture" for x in ds["dataset_meta"]["excluded"]))
