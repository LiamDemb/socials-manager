from django.core.management.base import BaseCommand

from context.services import discover_lastfm_similar


class Command(BaseCommand):
    help = "Fetch Last.fm similar artists as peer candidates (requires LAST_FM_API_KEY in .env)."

    def add_arguments(self, parser):
        parser.add_argument("--artist", default="Opal Season")
        parser.add_argument("--limit", type=int, default=30)

    def handle(self, artist, limit, **opts):
        result = discover_lastfm_similar(artist, limit=limit)
        self.stdout.write(str(result))
