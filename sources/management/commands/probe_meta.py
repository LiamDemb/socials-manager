import json

from django.core.management.base import BaseCommand

from core.paths import data_root
from sources import meta_graph
from sources.instagram import ensure_instagram_source
from sources.models import Source, SourcePolicyVersion


class Command(BaseCommand):
    help = "Inspect Meta app configuration, own Instagram account, and write a sanitised capability report."

    def add_arguments(self, parser):
        parser.add_argument("--peer", help="Optional Instagram username for a Business Discovery probe")

    def handle(self, peer, **opts):
        cfg = meta_graph.inspect_configuration()
        own = meta_graph.fetch_own_account()
        ensure_instagram_source(Source, SourcePolicyVersion)
        report = {"configuration": cfg, "own_account": own}
        if peer:
            report["business_discovery_sample"] = meta_graph.business_discovery(peer.lstrip("@"))
        out = data_root() / "reports" / "meta-probe-latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        self.stdout.write(json.dumps(report, indent=2))
        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
