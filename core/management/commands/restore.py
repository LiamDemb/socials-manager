import json
import os
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import backup
from core.paths import data_root


class Command(BaseCommand):
    help = "Restore a backup into a NEW folder, verify it and smoke-test it. Optionally promote it to the active root."

    def add_arguments(self, parser):
        parser.add_argument("backup_dir")
        parser.add_argument("--to", help="New, empty folder to restore into (default: beside the data root)")
        parser.add_argument("--promote", action="store_true", help="After verification, replace the active data root (app must be stopped)")

    def handle(self, backup_dir, to, promote, **opts):
        if not to:
            from core import clock

            active = data_root()
            to = str(active.with_name(f"{active.name}.restore-{clock.now().strftime('%Y%m%dT%H%M%SZ')}"))
        try:
            report = backup.restore_to(Path(backup_dir), Path(to))
        except (RuntimeError, FileNotFoundError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(json.dumps(report, indent=2))
        if not report["ok"]:
            raise CommandError("Restore verification failed; the active data root was not changed.")
        env = {**os.environ, "BAND_EVIDENCE_DATA_ROOT": str(Path(to).resolve())}
        smoke = subprocess.run([sys.executable, "manage.py", "smoke_check"], env=env, capture_output=True, text=True,
                               cwd=Path(__file__).resolve().parents[3])
        self.stdout.write(smoke.stdout)
        if smoke.returncode:
            self.stderr.write(smoke.stderr[-2000:])
            raise CommandError("Smoke check failed on the restored copy; the active data root was not changed.")
        if promote:
            result = backup.promote(Path(to), data_root())
            self.stdout.write(self.style.SUCCESS(f"Promoted. Previous root kept at {result['previous_root_kept_at']}"))
        else:
            self.stdout.write(self.style.SUCCESS("Restored copy verified. Active root unchanged. Re-run with --promote to switch."))
