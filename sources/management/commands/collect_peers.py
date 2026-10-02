from django.core.management.base import BaseCommand

from context.services import run_peer_collection_batch


class Command(BaseCommand):
    help = "Run one resumable Business Discovery batch for curated peers with Instagram usernames."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, limit, **opts):
        batch = run_peer_collection_batch(limit=limit)
        self.stdout.write(str(batch))
