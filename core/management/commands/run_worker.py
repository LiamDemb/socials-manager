from django.core.management.base import BaseCommand, CommandError

from core import instance, worker


class Command(BaseCommand):
    help = "Run the single leased job worker (daily backup, orphan cleanup, invalidation events)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one tick and exit")

    def handle(self, once, **opts):
        if not instance.is_initialised():
            raise CommandError("Not initialised.")
        if once:
            import os
            import socket

            worker.tick(f"{socket.gethostname()}:{os.getpid()}")
            return
        worker.run_forever()
