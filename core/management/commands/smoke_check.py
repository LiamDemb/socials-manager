from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core import clock, instance


class Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Read checks plus a rolled-back write of the core campaign flow against the configured data root."

    def handle(self, **opts):
        from campaigns.models import Activity, Campaign
        from campaigns.services import add_activity, create_campaign, execute, outcome_progress
        from catalogue.services import own_artist
        from sources.models import Observation
        from sources.services import committed_entities, export_common

        config = instance.load()
        with connection.cursor() as c:
            c.execute("PRAGMA integrity_check")
            if c.fetchone()[0] != "ok":
                raise CommandError("integrity_check failed")
            c.execute("PRAGMA foreign_key_check")
            if c.fetchall():
                raise CommandError("foreign key violations")
            c.execute("PRAGMA journal_mode")
            journal = c.fetchone()[0]
        artist = own_artist()
        obs = Observation.objects.filter(active_version__isnull=False).count()
        export_common()
        outcomes = 0
        for campaign in Campaign.objects.all():
            for link in campaign.outcome_links.all():
                outcome_progress(link.outcome_version)
                outcomes += 1
        try:
            with transaction.atomic():
                result = create_campaign({
                    "type": "audience_growth", "name": "Smoke check", "start_date": clock.now().date().isoformat(),
                    "end_date": clock.now().date().isoformat(),
                    "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 1},
                }, "smoke-check-create-key")
                act = add_activity(result["campaign_id"], {"title": "Smoke", "date": clock.now().date().isoformat()}, "smoke-check-activity-key")
                execute(act["activity_id"], act["revision"], "complete", "smoke-check-execute-key")
                if Activity.objects.get(pk=act["activity_id"]).status != "completed":
                    raise CommandError("write flow failed")
                raise Rollback
        except Rollback:
            pass
        self.stdout.write(f"smoke ok: artist={artist.label if artist else None} tz={config['timezone']} journal={journal} "
                          f"observations={obs} entities={len(committed_entities())} outcomes_computed={outcomes} write_flow=rolled_back")
