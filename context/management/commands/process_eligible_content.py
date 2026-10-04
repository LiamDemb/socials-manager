import json

from django.core.management.base import BaseCommand

from context.media_pack import ensure_media_pack
from context.media_schedule import select_extraction_batch


class Command(BaseCommand):
    help = "Queue a fair batch of content packs. Does not download during migrate."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, limit, dry_run, **opts):
        chosen = select_extraction_batch(limit)
        report = {"selected": [str(m.pk) for m in chosen], "queued": [], "dry_run": dry_run}
        if not dry_run:
            for media in chosen:
                report["queued"].append(ensure_media_pack(media.pk))
        self.stdout.write(json.dumps(report, default=str))
