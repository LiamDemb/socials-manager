from datetime import date

from django.core.management.base import BaseCommand

from catalogue.models import PromotedObject
from catalogue.services import own_artist, update_object


class Command(BaseCommand):
    help = "Apply owner-supplied catalogue facts without inferring from filenames or first observations."

    def handle(self, **opts):
        artist = own_artist()
        if not artist:
            self.stdout.write("No installation yet.")
            return
        obj = PromotedObject.objects.filter(entity__label__iexact="Better Man", kind="recording").first()
        if not obj:
            self.stdout.write("No Better Man recording in catalogue yet; import or create it first.")
            return
        update_object(
            obj.pk,
            obj.revision,
            spotify_url="https://open.spotify.com/track/7n6t9MVmHySFjov060YHcf",
            key_date=date(2026, 9, 25),
            date_confirmed=False,
        )
        obj.refresh_from_db()
        self.stdout.write(
            f"Updated {obj.entity.label}: track URL stored, release date 2026-09-25 (unverified). "
            f"Identity state remains {obj.identity_state} until you confirm in Settings."
        )
