import json
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import backup, clock
from core.env import DEFAULT_DATA_ROOT, LEGACY_DATA_ROOT


class Command(BaseCommand):
    help = "Copy a legacy BandEvidence data folder into SocialsManager with a verified backup. Never overwrites an existing SocialsManager database."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="src", default=str(LEGACY_DATA_ROOT), help="Legacy data root")
        parser.add_argument("--to", dest="dst", default=str(DEFAULT_DATA_ROOT), help="New data root")
        parser.add_argument("--force-empty-target", action="store_true", help="Allow copying when the target folder is empty but exists")

    def handle(self, src, dst, force_empty_target, **opts):
        src = Path(src).expanduser().resolve()
        dst = Path(dst).expanduser().resolve()
        if not src.exists():
            raise CommandError(f"Legacy folder does not exist: {src}")
        if dst.exists() and (dst / "app.sqlite3").exists():
            raise CommandError(f"Target already has a database: {dst}. Stop the app and use restore/promote instead of copying over it.")
        if dst.exists() and any(dst.iterdir()) and not force_empty_target:
            raise CommandError(f"Target is not empty: {dst}. Pass --force-empty-target if it only contains empty subfolders.")
        backup_dir, _ = backup.create_backup("pre_migrate", root=src)
        self.stdout.write(f"Legacy backup: {backup_dir}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=False)
        manifest = {
            "migrated_at": clock.now().isoformat(),
            "from": str(src),
            "to": str(dst),
            "legacy_backup": str(backup_dir),
        }
        (dst / "migration-from-band-evidence.json").write_text(json.dumps(manifest, indent=2) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Migrated {src} -> {dst}. Set SOCIALS_MANAGER_DATA_ROOT={dst}"))
