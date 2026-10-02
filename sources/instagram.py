"""Instagram Graph adapter boundary. Live calls stay blocked until owner authorisation is stored."""
import json
from pathlib import Path

from django.conf import settings

from core import clock
from core.paths import data_root

IG_PROVIDER = "instagram"
IG_ROUTE = "graph_api"
HANDLE = "opalseason_"

SETUP_STEPS = [
    "Create a Meta developer app at developers.facebook.com (Business type).",
    "Add the Instagram product and Graph API. Pin an API version in the app settings.",
    "Connect the Opal Season Facebook Page that owns the @opalseason_ professional account.",
    "Request and complete App Review for instagram_basic, instagram_manage_insights, and pages_read_engagement (exact set may vary by route).",
    "Generate a long-lived user token for the Page, or use a System User token in Business Manager. Store it locally only (never in the repository).",
    "Run: python manage.py probe_instagram --store-token (with the app stopped) to record capability without logging the secret.",
    "Until that succeeds, live collection remains Blocked; reviewed imports and manual observations still work.",
]


def secret_path():
    return data_root() / "secrets" / "instagram.json"


def load_credentials():
    path = secret_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("revoked"):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def capability_report(live_state, detail):
    return {
        "handle": HANDLE,
        "account": "@opalseason_",
        "route": IG_ROUTE,
        "live_integration": live_state,
        "detail": detail,
        "checked_at": clock.now().isoformat(),
        "timezone_semantics": "unknown until a live media payload is captured",
        "metrics": {
            "account.followers": "unsupported until probe",
            "media.insights": "unsupported until probe",
            "online_followers": "unsupported until probe",
        },
    }


def probe_live():
    creds = load_credentials()
    if creds is None:
        return capability_report(
            "Blocked",
            "No authorised token on disk. Meta developer/app access is UNSURE. Complete docs/META-SETUP.md before enabling live calls.",
        )
    if settings.ALLOW_SYNTHETIC_SOURCES and creds.get("fixture"):
        return capability_report("Passed", "Synthetic fixture credentials; no network call.")
    return capability_report(
        "Blocked",
        "Credentials are present but live probe is not enabled in this build until App Review and pinned API version are confirmed.",
    )


def ensure_instagram_source(Source, SourcePolicyVersion):
    from .models import Source

    source, _ = Source.objects.get_or_create(
        provider=IG_PROVIDER,
        route=IG_ROUTE,
        defaults={
            "label": "Instagram (@opalseason_)",
            "state": "active",
            "capability": probe_live(),
            "url": "https://www.instagram.com/opalseason_/",
        },
    )
    if not source.policies.exists():
        SourcePolicyVersion.objects.create(
            source=source,
            version=1,
            purposes={
                "collect": "unresolved",
                "store": "unresolved",
                "display": "unresolved",
                "descriptive_derive": "unresolved",
                "export": "unresolved",
                "statistical_fit": "denied",
                "model_infer": "denied",
                "llm_ingest": "denied",
            },
            assessment_ref="Pending authorised Meta capability probe (spec/INTEGRATIONS.md). Unknown denies each purpose until allowed.",
            conditions="Loopback installation; no publishing; captions treated as untrusted text.",
            retention={"raw": "until owner deletes"},
            effective_at=clock.now(),
        )
    source.capability = probe_live()
    source.save(update_fields=["capability", "revision"])
    return source
