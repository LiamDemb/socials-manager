import json

from django.core.management.base import BaseCommand

from core.diagnostics import report


class Command(BaseCommand):
    help = "Print a sanitised diagnostic report (no secrets, no private values)."

    def handle(self, **opts):
        self.stdout.write(json.dumps(report(), indent=2, default=str))
