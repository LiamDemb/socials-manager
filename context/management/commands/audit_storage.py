import json

from django.core.management.base import BaseCommand

from context.media_storage import orphan_relative_paths, usage_report


class Command(BaseCommand):
    help = "Report media quota usage and orphan files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, dry_run, **opts):
        report = {**usage_report(), "orphans": orphan_relative_paths(), "dry_run": dry_run}
        self.stdout.write(json.dumps(report))
