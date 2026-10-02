from pathlib import Path

from django.conf import settings


def models_dir() -> Path:
    path = settings.DATA_ROOT / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def manifest_path() -> Path:
    return models_dir() / "manifest.json"
