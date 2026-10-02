import json

from django.core.management.base import BaseCommand

from sources import musicbrainz


class Command(BaseCommand):
    help = "Bounded MusicBrainz artist search or MBID lookup (does not auto-merge ambiguous matches)."

    def add_arguments(self, parser):
        parser.add_argument("--artist", help="Artist name to search")
        parser.add_argument("--mbid", help="Artist MBID to look up")

    def handle(self, artist, mbid, **opts):
        if mbid:
            result = musicbrainz.lookup_artist(mbid)
        elif artist:
            result = musicbrainz.search_artists(artist)
        else:
            self.stderr.write("Provide --artist or --mbid")
            return
        self.stdout.write(json.dumps(result, indent=2))
