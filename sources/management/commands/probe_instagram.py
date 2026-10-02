from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Alias for probe_meta (Instagram / Meta Graph capability)."

    def add_arguments(self, parser):
        parser.add_argument("--peer", help="Optional peer username for Business Discovery sample")

    def handle(self, peer, **opts):
        call_command("probe_meta", peer=peer)
