from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core import backup, instance
from core.paths import data_root


class Command(BaseCommand):
    help = "Back up, then apply pending migrations. Never resets or wipes the data root."

    def handle(self, **opts):
        if not instance.is_initialised():
            raise CommandError(f"No installation at {data_root()}. Run: bin/socials-manager init --artist \"Band name\"")
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if not plan:
            self.stdout.write("Schema is current.")
            return
        dest, _ = backup.create_backup("pre-migrate")
        self.stdout.write(f"Backed up to {dest} before applying {len(plan)} migration(s).")
        call_command("migrate", interactive=False, verbosity=1)
