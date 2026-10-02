import json
from datetime import datetime, timezone

from .paths import manifest_path

DEFAULT_MANIFEST = {
    "schema_version": 1,
    "model_id": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "revision": "main",
    "quantization": "4bit",
    "runtime": "mlx-lm",
    "prompt_pack_version": "synthesis-v1",
    "generation": {
        "temperature": 0.2,
        "max_tokens": 1024,
        "temperature_ask": 0.1,
        "max_tokens_ask": 512,
        "temperature_brief": 0.15,
        "max_tokens_brief": 512,
    },
    "context_token_budget": 4096,
    "installed_at": None,
    "sha256": None,
}


def load_manifest() -> dict:
    path = manifest_path()
    if not path.is_file():
        return dict(DEFAULT_MANIFEST)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_MANIFEST)
    merged = dict(DEFAULT_MANIFEST)
    merged.update(data)
    return merged


def save_manifest(patch: dict) -> dict:
    data = load_manifest()
    data.update(patch)
    if patch.get("installed_at") is True:
        data["installed_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
