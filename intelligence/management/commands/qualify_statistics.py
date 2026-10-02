"""Real statistical qualification (synthetic path). Does not write owner DB fiction."""
import json

from django.core.management.base import BaseCommand

from intelligence.qualification_criteria import STATS_CRITERIA
from intelligence.registry import sync_analysis_specs
from intelligence.stats import post_response


class Command(BaseCommand):
    help = "Run frozen statistical qualification on isolated synthetic data"

    def handle(self, *args, **options):
        sync_analysis_specs()
        from intelligence.models import AnalysisSpec

        spec = AnalysisSpec.objects.get(key="post_public_response_v1")
        rows = [{"format": "reel", "response": 100 + i * 5} for i in range(STATS_CRITERIA["synthetic_min_posts"])]
        ctx = {"post_rows": rows}
        outcome = post_response.run(spec, {"intent": "summary"}, ctx)
        report = {
            "criteria": STATS_CRITERIA,
            "outcome_status": outcome.get("status"),
            "sample_size": outcome.get("sample_size"),
            "blocked": outcome.get("status") == "blocked",
            "blocker_code": outcome.get("blocker_code"),
            "note": "Owner DB not modified. Real domains may be data-gated.",
        }
        self.stdout.write(json.dumps(report, indent=2))
        if outcome.get("status") == "blocked" and outcome.get("blocker_code") == "dependency_unavailable":
            self.stdout.write(self.style.WARNING("Blocked: dependency unavailable (not insufficient_data)"))
