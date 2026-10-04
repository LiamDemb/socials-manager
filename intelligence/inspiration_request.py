"""Build typed inspiration requests server-side (M06)."""
import hashlib
import json

from core import clock

from context.models import InspirationRequestRecord


def build_inspiration_request(activity=None, context: dict | None = None, mode="best_fit", look_reference_id=None):
    ctx = context or {}
    payload = {
        "schema_version": "inspiration-request-v1",
        "activity_id": str(activity.pk) if activity else None,
        "activity_revision": getattr(activity, "revision", None) if activity else None,
        "roles": ctx.get("roles") or [],
        "channel": (ctx.get("channel") or (activity.channel if activity else "") or "").lower(),
        "format": ctx.get("format") or (activity.format if activity else "") or "",
        "purpose": ctx.get("purpose") or "",
        "phase": ctx.get("phase") or "",
        "constraints": ctx.get("constraints") or {},
        "mode": mode,
        "look_reference_id": look_reference_id,
        "as_of": clock.now().isoformat(),
    }
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]
    rec, _ = InspirationRequestRecord.objects.get_or_create(
        fingerprint=fp,
        defaults={"payload": payload, "created_at": clock.now()},
    )
    return rec, payload
