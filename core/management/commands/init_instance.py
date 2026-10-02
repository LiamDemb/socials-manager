from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core import instance
from core.errors import DomainError
from core.paths import data_root, ensure_layout


class Command(BaseCommand):
    help = "Create the persistent data root, an empty migrated database and instance.json. Refuses to overwrite."

    def add_arguments(self, parser):
        parser.add_argument("--artist", required=True, help="The band's name as it should appear in the app")
        parser.add_argument("--timezone", default="Australia/Perth", help="IANA timezone, e.g. Australia/Perth")
        parser.add_argument("--synthetic", action="store_true", help="Mark this root as a synthetic test/demo root")

    def handle(self, artist, timezone, synthetic, **opts):
        root = data_root()
        if (root / "instance.json").exists() or (root / "app.sqlite3").exists():
            raise CommandError(f"{root} already holds an installation. Nothing was changed.")
        try:
            instance.validate_timezone(timezone)
        except DomainError as exc:
            raise CommandError(exc.message)
        ensure_layout(root)
        call_command("migrate", interactive=False, verbosity=0)
        from catalogue.services import create_own_artist
        from sources.services import ensure_spotify_source

        own = create_own_artist(artist)
        instance.create(own.pk, artist, timezone, fixture_class="synthetic" if synthetic else "owner")
        ensure_spotify_source()
        from sources import instagram
        from sources.models import Source, SourcePolicyVersion

        instagram.ensure_instagram_source(Source, SourcePolicyVersion)
        self.stdout.write(self.style.SUCCESS(f"Initialised {root} for {artist} ({timezone})."))
