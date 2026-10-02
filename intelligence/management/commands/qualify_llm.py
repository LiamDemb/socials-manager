import json

from django.core.management.base import BaseCommand

from intelligence.llm_adapter import qualify_smoke
from intelligence.manifest import load_manifest, save_manifest


class Command(BaseCommand):
    help = "Run structured qualification smoke test for the configured local model."

    def handle(self, **opts):
        manifest = load_manifest()
        result = qualify_smoke()
        if result.get("passed"):
            save_manifest({"last_qualification": result, "installed_at": True})
        else:
            save_manifest({"last_qualification": result})
        self.stdout.write(json.dumps({"manifest": load_manifest(), "qualification": result}, indent=2))
        if not result.get("passed"):
            if result.get("backend") == "mlx-lm":
                self.stderr.write(
                    self.style.WARNING(
                        "Qualification did not pass (MLX ran but brief check failed). "
                        f"has_brief={result.get('has_brief')} preview={result.get('brief_preview', '')!r}"
                    )
                )
            else:
                self.stderr.write(self.style.WARNING("Qualification did not pass; deterministic fallback remains active."))
