import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

from django.conf import settings

import socials_manager

from . import clock
from .paths import data_root, safe_path
from .sqlite_runtime import desired_journal_mode

COUNT_TABLES = [
    "catalogue_entity", "catalogue_promotedobject", "sources_rawfile", "sources_importbatch", "sources_observation",
    "sources_observationversion", "sources_observationcontribution", "campaigns_campaign", "campaigns_outcomeversion",
    "campaigns_activity", "campaigns_executionevent", "core_auditevent",
]
RETAIN = 20


def _sha(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_report(path: Path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in COUNT_TABLES}
        migrations = [f"{a}.{n}" for a, n in con.execute("SELECT app, name FROM django_migrations ORDER BY app, name")]
        files = [(r, s) for r, s in con.execute("SELECT relative_path, sha256 FROM sources_rawfile ORDER BY relative_path")]
        return {"integrity": integrity, "foreign_key_violations": len(fk), "counts": counts, "migrations": migrations, "files": files}
    finally:
        con.close()


def create_backup(reason="manual", root: Path | None = None):
    root = root or data_root()
    db_path = root / "app.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError("No database to back up.")
    stamp = clock.now().strftime("%Y%m%dT%H%M%S%fZ")
    dest = root / "backups" / f"{stamp}-{reason}"
    dest.mkdir(parents=True)
    os.chmod(dest, 0o700)
    src = sqlite3.connect(db_path, timeout=30)
    dst = sqlite3.connect(dest / "app.sqlite3")
    try:
        # Consistent snapshot even while the app is running (WAL-safe); never copy the live main file alone.
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    report = _db_report(dest / "app.sqlite3")
    files = []
    for relative, sha in report.pop("files"):
        source_file = safe_path(relative, root)
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
        actual = _sha(target)
        if actual != sha:
            raise RuntimeError(f"Referenced file {relative} does not match its recorded hash.")
        files.append({"path": relative, "sha256": sha})
    shutil.copy2(root / "instance.json", dest / "instance.json")
    manifest = {
        "format": "socials-manager-backup-1",
        "created_at": clock.now().isoformat(),
        "reason": reason,
        "app_version": socials_manager.APP_VERSION,
        "sqlite_runtime": sqlite3.sqlite_version,
        "database_sha256": _sha(dest / "app.sqlite3"),
        "instance_sha256": _sha(dest / "instance.json"),
        "files": files,
        "secrets_included": False,
        **report,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _prune(root)
    return dest, manifest


def _prune(root):
    backups = sorted(p for p in (root / "backups").iterdir() if p.is_dir() and (p / "manifest.json").exists())
    for old in backups[:-RETAIN]:
        shutil.rmtree(old)


def list_backups(root: Path | None = None):
    root = root or data_root()
    out = []
    folder = root / "backups"
    if not folder.exists():
        return out
    for p in sorted(folder.iterdir(), reverse=True):
        m = p / "manifest.json"
        if m.exists():
            data = json.loads(m.read_text())
            out.append({"path": p, "created_at": data["created_at"], "reason": data["reason"], "counts": data["counts"]})
    return out


def restore_to(backup_dir: Path, target_root: Path):
    """Restore into a new, empty root and verify it. Never touches the active root."""
    backup_dir = Path(backup_dir).resolve()
    target_root = Path(target_root).resolve()
    if target_root.exists() and any(target_root.iterdir()):
        raise RuntimeError("Restore target must be a new, empty folder.")
    manifest = json.loads((backup_dir / "manifest.json").read_text())
    if manifest.get("format") not in ("socials-manager-backup-1", "band-evidence-backup-1"):
        raise RuntimeError("Unknown backup format.")
    if _sha(backup_dir / "app.sqlite3") != manifest["database_sha256"]:
        raise RuntimeError("Backup database hash mismatch.")
    target_root.mkdir(parents=True, exist_ok=True)
    os.chmod(target_root, 0o700)
    for sub in ["imports", "assets", "datasets", "models", "reports", "cache", "backups", "run", "staging"]:
        (target_root / sub).mkdir(exist_ok=True)
    shutil.copy2(backup_dir / "app.sqlite3", target_root / "app.sqlite3")
    shutil.copy2(backup_dir / "instance.json", target_root / "instance.json")
    for f in manifest["files"]:
        src = backup_dir / f["path"]
        dst = safe_path(f["path"], target_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if _sha(dst) != f["sha256"]:
            raise RuntimeError(f"Restored file {f['path']} hash mismatch.")
    report = _db_report(target_root / "app.sqlite3")
    problems = []
    if report["integrity"] != "ok":
        problems.append(f"integrity_check: {report['integrity']}")
    if report["foreign_key_violations"]:
        problems.append(f"{report['foreign_key_violations']} foreign key violations")
    if report["counts"] != manifest["counts"]:
        problems.append("row counts differ from manifest")
    if report["migrations"] != manifest["migrations"]:
        problems.append("schema migrations differ from manifest")
    missing = [r for r, _ in report["files"] if not (target_root / r).exists()]
    if missing:
        problems.append(f"{len(missing)} referenced files missing")
    con = sqlite3.connect(target_root / "app.sqlite3")
    con.execute(f"PRAGMA journal_mode={desired_journal_mode()}")
    con.close()
    return {"target": str(target_root), "ok": not problems, "problems": problems, "counts": report["counts"], "files": len(manifest["files"])}


def server_running(root: Path):
    pid_file = root / "run" / "server.pid"
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text().strip()), 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def promote(restored_root: Path, active_root: Path):
    restored_root, active_root = Path(restored_root).resolve(), Path(active_root).resolve()
    if server_running(active_root):
        raise RuntimeError("Stop the app before promoting a restore.")
    if (active_root / "app.sqlite3").exists():
        create_backup("pre-restore", active_root)
    stamp = clock.now().strftime("%Y%m%dT%H%M%SZ")
    replaced = active_root.with_name(active_root.name + f".replaced-{stamp}")
    if active_root.exists():
        active_root.rename(replaced)
    restored_root.rename(active_root)
    if replaced.exists() and (replaced / "backups").exists():
        shutil.rmtree(active_root / "backups", ignore_errors=True)
        shutil.copytree(replaced / "backups", active_root / "backups")
    return {"active": str(active_root), "previous_root_kept_at": str(replaced)}


def orphan_files(root: Path | None = None, min_age_seconds=3600):
    """Raw files written before an interrupted DB commit. Regenerable only by re-upload, so they are reported then removed."""
    root = root or data_root()
    con = sqlite3.connect(f"file:{root / 'app.sqlite3'}?mode=ro", uri=True)
    known = {r for (r,) in con.execute("SELECT relative_path FROM sources_rawfile")}
    con.close()
    now = clock.now().timestamp()
    out = []
    for path in (root / "imports").rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if rel not in known and now - path.stat().st_mtime > min_age_seconds:
                out.append(path)
    return out


def settings_root():
    return Path(settings.DATA_ROOT)
