import json

from django.core.management.base import BaseCommand

from core.paths import data_root
from sources import instagram
from sources.models import Source, SourcePolicyVersion


class Command(BaseCommand):
    help = "Run a sanitised Instagram capability probe (live Blocked until authorised)."

    def handle(self, **opts):
        source = instagram.ensure_instagram_source(Source, SourcePolicyVersion)
        report = source.capability
        stamp = report["checked_at"].replace(":", "").replace("+", "")
        out = data_root() / "reports" / f"instagram-probe-{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        self.stdout.write(json.dumps(report, indent=2))
        state = report["live_integration"]
        if state == "Blocked":
            self.stdout.write(self.style.WARNING(f"Live integration: {state}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Live integration: {state}"))
