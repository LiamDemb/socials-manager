import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Retrieval qualification. Blocked until an owner-reviewed brief set exists."

    def handle(self, **opts):
        from intelligence.clip_adapter import status as clip_status

        visual = clip_status()
        report = {
            "status": "blocked",
            "reason": "no_owner_relevance_judgements",
            "required": "30-50 reviewed activity briefs with graded relevance before ranker weights change.",
            "routes_implemented": ["structured", "fts5", "visual"],
            "visual": visual,
            "qualified": False,
        }
        self.stdout.write(json.dumps(report, indent=2))
        raise SystemExit(2)
