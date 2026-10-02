"""Instagram / Meta Graph adapter for own account and peer Business Discovery."""

from core import clock

from . import meta_graph

IG_PROVIDER = "instagram"
IG_ROUTE = "graph_api"
HANDLE = "opalseason_"

INSTAGRAM_POLICY = {
    "assessment_ref": (
        "Owner override: all purposes allowed on this private loopback instance for development "
        "(Meta tokens; peer metrics are Business Discovery fields only; docs/META-SETUP.md)."
    ),
    "conditions": "No publishing; captions untrusted; no fabricated reach or conversions.",
    "retention": {"raw": "api cache under data root"},
}


def probe_live():
    cfg = meta_graph.inspect_configuration()
    own = meta_graph.fetch_own_account()
    live = (
        "Passed"
        if own.get("state") == "ok"
        else ("Blocked" if own.get("state") == "blocked" else "Failed")
    )
    username = (
        cfg.get("instagram_username")
        or (own.get("fields") or {}).get("username")
        or HANDLE
    ).strip()
    profile = dict(own.get("fields") or {}) if own.get("state") == "ok" else {}
    return {
        "handle": username,
        "account": f"@{username}",
        "route": IG_ROUTE,
        "live_integration": live,
        "detail": cfg.get("detail"),
        "checked_at": clock.now().isoformat(),
        "auth_route": cfg.get("auth_route"),
        "business_discovery_supported": cfg.get("business_discovery_supported"),
        "instagram_login_only_warning": cfg.get("instagram_login_only_warning"),
        "profile": profile,
        "own_account": {
            "state": own.get("state"),
            "account_id": own.get("account_id"),
            "fields_available": list((own.get("fields") or {}).keys()),
            "unavailable_fields": own.get("unavailable_fields") or [],
            "note": own.get("note") or own.get("reason") or "",
        },
        "metrics": {
            "account.followers": (
                "ok"
                if own.get("state") == "ok"
                and "followers_count" in (own.get("fields") or {})
                else "unsupported"
            ),
            "media.insights": "unsupported until per-media insights probe",
            "online_followers": "unsupported",
            "peer.business_discovery": (
                "ok" if cfg.get("business_discovery_supported") else "blocked"
            ),
        },
    }


def ensure_instagram_source(Source, SourcePolicyVersion):
    from .models import Source, SourcePolicyVersion as PolicyVersion

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
    from .services import all_allowed_purposes

    if not source.policies.exists():
        PolicyVersion.objects.create(
            source=source,
            version=1,
            purposes=all_allowed_purposes(),
            assessment_ref=INSTAGRAM_POLICY["assessment_ref"],
            conditions=INSTAGRAM_POLICY["conditions"],
            retention=INSTAGRAM_POLICY["retention"],
            effective_at=clock.now(),
        )
    source.capability = probe_live()
    source.save(update_fields=["capability", "revision"])
    return source
