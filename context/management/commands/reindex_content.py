import json

from django.core.management.base import BaseCommand

from context.models import ContentFeatureValue, PeerMedia


class Command(BaseCommand):
    help = "Report the searchable content index. FTS is rebuilt per query from stored captions and reviewed labels."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, dry_run, **opts):
        report = {
            "status": "blocked" if not PeerMedia.objects.exists() and not dry_run else "passed",
            "posts": PeerMedia.objects.count(),
            "reviewed_features": ContentFeatureValue.objects.filter(review_state__in=["accepted", "corrected"]).count(),
            "index": "ephemeral_fts5_per_query",
            "dry_run": dry_run,
            "note": "No separate vector index is written until a qualified encoder is enabled.",
        }
        if not PeerMedia.objects.exists():
            report["status"] = "blocked"
            report["reason"] = "no_posts"
        self.stdout.write(json.dumps(report))
        if report["status"] == "blocked" and not dry_run:
            raise SystemExit(2)
