import json

from django.core.management.base import BaseCommand

from intelligence.llm_adapter import health, qualify_smoke


class Command(BaseCommand):
    help = "Report local LLM adapter health (no secrets)."

    def handle(self, **opts):
        report = {"health": health(), "smoke": qualify_smoke()}
        self.stdout.write(json.dumps(report, indent=2))
