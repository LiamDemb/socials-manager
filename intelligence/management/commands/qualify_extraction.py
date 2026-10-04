import json

from django.core.management.base import BaseCommand

from intelligence.extraction_adapter import extract_labels
from intelligence.qualification_criteria import STATS_CRITERIA


class Command(BaseCommand):
    help = "Run local extraction qualification gates (requires owner-reviewed corpus for full pass)."

    def handle(self, **opts):
        from context.models import MediaPack, PeerMedia

        media = PeerMedia.objects.first()
        if not media:
            self.stdout.write(self.style.WARNING("No PeerMedia rows; run on fixtures or after collection."))
            report = {"status": "blocked", "reason": "no_data"}
        else:
            pack = MediaPack.objects.filter(post=media).first() or MediaPack(
                post=media,
                profile_version="media-compact-v1",
                input_hash="qual",
                created_at=media.collected_at,
            )
            outcome = extract_labels(media, pack)
            report = {
                "status": outcome.get("status"),
                "adapter": outcome.get("adapter"),
                "multimodal": (outcome.get("output") or {}).get("multimodal"),
                "criteria_note": "Full M05 gates require 50+ human-reviewed corpus; not satisfied in automated run.",
                "stats_criteria_ref": STATS_CRITERIA.get("synthetic_min_posts"),
            }
        self.stdout.write(json.dumps(report, indent=2))
        if report.get("status") != "ready":
            raise SystemExit(2)
