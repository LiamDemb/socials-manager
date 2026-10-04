from django.core.management.base import BaseCommand

from context.media_storage import media_root, usage_bytes
from context.models import MediaAsset


class Command(BaseCommand):
    help = "Reconcile media blob storage vs MediaAsset records."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, dry_run, **opts):
        db_paths = set(MediaAsset.objects.exclude(relative_path="").values_list("relative_path", flat=True))
        orphan_files = []
        root = media_root()
        for p in root.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(root.parent.parent))
                if rel not in db_paths:
                    orphan_files.append(rel)
        self.stdout.write(
            self.style.SUCCESS(
                json_dumps(
                    {
                        "usage_bytes": usage_bytes(),
                        "db_assets": len(db_paths),
                        "orphan_files": len(orphan_files),
                        "dry_run": dry_run,
                    }
                )
            )
        )


def json_dumps(obj):
    import json

    return json.dumps(obj, indent=2)
