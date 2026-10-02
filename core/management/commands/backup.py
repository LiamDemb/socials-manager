from django.core.management.base import BaseCommand

from core import backup, clock
from core.models import BackupRecord
from core.paths import data_root


class Command(BaseCommand):
    help = "Create a consistent backup (SQLite snapshot + referenced files + manifest) in the data root."

    def add_arguments(self, parser):
        parser.add_argument("--reason", default="manual")
        parser.add_argument("--list", action="store_true")

    def handle(self, reason, list, **opts):
        if list:
            for b in backup.list_backups():
                self.stdout.write(f"{b['created_at']}  {b['reason']:<12} {b['path']}")
            return
        dest, manifest = backup.create_backup(reason)
        BackupRecord.objects.create(created_at=clock.now(), relative_path=str(dest.relative_to(data_root())), reason=reason, status="ok",
                                    detail={"counts": manifest["counts"]})
        self.stdout.write(self.style.SUCCESS(f"Backup written to {dest}"))
        self.stdout.write(f"integrity={manifest['integrity']} files={len(manifest['files'])} observations={manifest['counts']['sources_observation']}")
