"""AC11 restart persistence and AC35 backup/restore, using real processes against a fresh data root."""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)

WRITE = """
from datetime import date
from catalogue.services import create_object
from campaigns.services import create_campaign, add_activity, execute
from sources.services import preview_upload, set_mapping, commit
song = create_object('recording', 'Fixture song')
raw = b'\\xef\\xbb\\xbfdate,streams\\n2026-09-24,50\\n2026-09-25,60\\n'
b = preview_upload(raw, 'fixture.csv')
b = set_mapping(b.pk, b.preview_revision, entity_id=song.pk)
commit(b.pk, b.preview_revision, 'ops-commit-key')
c = create_campaign({'type': 'single', 'name': 'Fixture single', 'start_date': '2026-09-20', 'end_date': '2026-10-20',
    'object': {'mode': 'existing', 'id': str(song.pk)},
    'primary_outcome': {'mode': 'new', 'metric_id': 'spotify.recording.streams.v1', 'outcome_mode': 'total', 'target': 100}}, 'ops-campaign-key')
a = add_activity(c['campaign_id'], {'title': 'Teaser', 'date': '2026-09-24'}, 'ops-activity-key')
execute(a['activity_id'], a['revision'], 'complete', 'ops-exec-key', actual_at='2026-09-24T18:00')
"""

READ = """
import json
from campaigns.models import Activity, Campaign
from campaigns.services import outcome_progress
from sources.models import Observation, RawFile
from sources.services import read_raw
c = Campaign.objects.get()
p = outcome_progress(c.outcome_links.get().outcome_version)
print(json.dumps({'campaigns': Campaign.objects.count(), 'observations': Observation.objects.count(),
  'activity': Activity.objects.get().status, 'progress': [p.status, p.value],
  'raw_ok': all(read_raw(r) is not None for r in RawFile.objects.all())}))
"""


class Operations(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="be-ops-"))
        self.root = self.tmp / "data"

    def run_cmd(self, *args, root=None, check=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith("BAND_EVIDENCE_") and k != "DJANGO_SETTINGS_MODULE"}
        env["BAND_EVIDENCE_DATA_ROOT"] = str(root or self.root)
        env["DJANGO_SETTINGS_MODULE"] = "bandevidence.settings"
        proc = subprocess.run([sys.executable, str(ROOT / "manage.py"), *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        if check and proc.returncode != 0:
            self.fail(f"{args} failed: {proc.stdout}\n{proc.stderr}")
        return proc

    def read_state(self, root=None):
        return json.loads(self.run_cmd("shell", "-c", READ, root=root).stdout.strip().splitlines()[-1])

    def test_init_restart_backup_restore(self):
        self.run_cmd("init_instance", "--artist", "Fixture Band", "--timezone", "Australia/Perth", "--synthetic")
        again = self.run_cmd("init_instance", "--artist", "Other", check=False)
        self.assertNotEqual(again.returncode, 0, "Init never overwrites an installation")
        key_file = self.root / "secret_key"
        self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode) & 0o077, 0)

        self.run_cmd("shell", "-c", WRITE)
        state = self.read_state()  # a new process: simulates app restart
        self.assertEqual(state, {"campaigns": 1, "observations": 2, "activity": "completed", "progress": ["met", 110], "raw_ok": True})

        out = self.run_cmd("backup", "--reason", "test").stdout
        backup_dir = Path(out.split("Backup written to ")[1].split()[0])
        manifest = json.loads((backup_dir / "manifest.json").read_text())
        self.assertEqual(manifest["integrity"], "ok")
        self.assertFalse(manifest["secrets_included"])
        self.assertFalse((backup_dir / "secret_key").exists())
        self.assertEqual(len(manifest["files"]), 1)

        restored = self.tmp / "restored"
        result = self.run_cmd("restore", str(backup_dir), "--to", str(restored))
        self.assertIn("smoke ok", result.stdout)
        self.assertEqual(self.read_state(root=restored), state)
        self.assertTrue((self.root / "app.sqlite3").exists(), "Active root untouched")

        nonempty = self.run_cmd("restore", str(backup_dir), "--to", str(self.root), check=False)
        self.assertNotEqual(nonempty.returncode, 0, "Never restores over an occupied folder")

        (self.root / "run" / "server.pid").write_text(str(os.getpid()))
        second = self.tmp / "restored-2"
        refused = self.run_cmd("restore", str(backup_dir), "--to", str(second), "--promote", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Stop the app", refused.stderr + refused.stdout)
        (self.root / "run" / "server.pid").unlink()

        promoted = self.run_cmd("restore", str(backup_dir), "--to", str(self.tmp / "restored-3"), "--promote")
        self.assertIn("Promoted", promoted.stdout)
        self.assertEqual(self.read_state(), state)
        self.assertTrue(any(p.name.startswith("data.replaced-") for p in self.tmp.iterdir()))

    def test_tampered_backup_is_rejected(self):
        self.run_cmd("init_instance", "--artist", "Fixture Band", "--synthetic")
        out = self.run_cmd("backup").stdout
        backup_dir = Path(out.split("Backup written to ")[1].split()[0])
        with open(backup_dir / "app.sqlite3", "ab") as fh:
            fh.write(b"tamper")
        bad = self.run_cmd("restore", str(backup_dir), "--to", str(self.tmp / "r"), check=False)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("hash mismatch", bad.stderr + bad.stdout)

    def test_data_root_inside_repository_refused(self):
        proc = self.run_cmd("check", root=ROOT / "inside-repo", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((ROOT / "inside-repo").exists())

    def test_worker_once_and_diagnostics(self):
        self.run_cmd("init_instance", "--artist", "Fixture Band", "--synthetic")
        self.run_cmd("run_worker", "--once")
        diag = self.run_cmd("diagnostics").stdout
        self.assertIn("worker", diag.lower())
        self.run_cmd("run_worker", "--once")
        daily = [line for line in self.run_cmd("backup", "--list").stdout.splitlines() if " daily " in line]
        self.assertEqual(len(daily), 1, "One daily backup per local day, even across repeated ticks")
