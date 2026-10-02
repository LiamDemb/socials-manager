import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core import instance
from core.paths import data_root, ensure_layout


class Command(BaseCommand):
    help = "Run the production local server (waitress) on 127.0.0.1 only."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=settings.PORT)

    def handle(self, port, **opts):
        if not instance.is_initialised():
            raise CommandError(f"No installation at {data_root()}. Run: bin/band-evidence init --artist \"Band name\"")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Pending migrations. Run: bin/band-evidence upgrade")
        ensure_layout()
        from waitress import serve

        from bandevidence.wsgi import application

        pid_file = data_root() / "run" / "server.pid"
        pid_file.write_text(str(os.getpid()))
        self.stdout.write(f"Band Evidence on http://127.0.0.1:{port}  (data: {data_root()})")
        try:
            serve(application, host=settings.BIND_HOST, port=port, threads=4, ident="band-evidence", max_request_body_size=settings.DATA_UPLOAD_MAX_MEMORY_SIZE)
        finally:
            pid_file.unlink(missing_ok=True)
