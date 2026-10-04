"""Save, unsave, manual references, and activity attachments."""
import re

from django.db import transaction

from core import clock
from core.errors import DomainError
from core.services import audit

from .library import media_card
from .models import ActivityReference, InspirationReference, PeerMedia, RecommendationExposure

HTTP_URL = re.compile(r"^https?://", re.I)


@transaction.atomic
def save_peer_media(peer_media_id, note=""):
    media = PeerMedia.objects.select_related("peer").get(pk=peer_media_id)
    if media.peer.peer_role not in ("comparable", "aspirational", "reference_only"):
        raise DomainError("peer_not_eligible", "This peer is not eligible for creative references.")
    key = f"peer_media:{media.pk}"
    ref, created = InspirationReference.objects.get_or_create(
        peer_media=media,
        is_bookmark=True,
        defaults={
            "canonical_key": key,
            "origin_type": "peer_media",
            "collection_source": "peer_business_discovery",
            "title": f"{media.peer.label} · {media.media_type or 'post'}",
            "url": media.permalink or "",
            "excerpt": (media.caption or "")[:2000],
            "retrieved_at": clock.now(),
            "owner_note": note or "",
            "scope": "global",
            "in_analytical_pool": True,
        },
    )
    if not created and note:
        ref.owner_note = note
        ref.save(update_fields=["owner_note"])
    audit("inspiration", ref.pk, "save_peer_media", {"peer_media": str(media.pk), "created": created})
    return ref


@transaction.atomic
def unsave_reference(reference_id):
    ref = InspirationReference.objects.get(pk=reference_id)
    if not ref.is_bookmark:
        raise DomainError("not_bookmark", "Only saved bookmarks can be removed this way.")
    if ref.activity_links.exists():
        ref.is_bookmark = False
        ref.save(update_fields=["is_bookmark"])
        audit("inspiration", ref.pk, "unsave_keep_attachments", {})
        return ref
    ref.delete()
    audit("inspiration", reference_id, "unsave_delete", {})
    return None


@transaction.atomic
def add_manual_reference(title, url, note="", scope="global", scope_ref=""):
    title = (title or "").strip()
    url = (url or "").strip()
    if not title:
        raise DomainError("title_required", "Enter a title.", fields={"title": "Required"})
    if not url or not HTTP_URL.match(url):
        raise DomainError("url_required", "Enter a valid http(s) URL.", fields={"url": "Required"})
    ref = InspirationReference.objects.create(
        title=title[:200],
        url=url[:500],
        excerpt=note[:2000],
        owner_note=note[:2000],
        scope=scope,
        scope_ref=scope_ref or "",
        origin_type="manual",
        collection_source="manual",
        canonical_key=f"manual:{clock.now().timestamp()}",
        is_bookmark=True,
        in_analytical_pool=False,
        retrieved_at=clock.now(),
    )
    audit("inspiration", ref.pk, "manual_add", {"scope": scope})
    return ref


@transaction.atomic
def attach_reference(activity_id, reference_id, origin="owner_attach", note=""):
    from campaigns.models import Activity

    activity = Activity.objects.get(pk=activity_id)
    ref = InspirationReference.objects.get(pk=reference_id)
    link, created = ActivityReference.objects.get_or_create(
        activity=activity,
        reference=ref,
        defaults={"origin": origin, "note": note or "", "created_at": clock.now()},
    )
    if not created:
        raise DomainError("already_attached", "This reference is already on the activity.")
    audit("activity", activity.pk, "attach_reference", {"reference": str(ref.pk), "origin": origin})
    RecommendationExposure.objects.create(
        reference=ref,
        peer_media=ref.peer_media,
        event="attached",
        note=origin[:200],
        created_at=clock.now(),
    )
    return link


@transaction.atomic
def detach_reference(activity_id, reference_id):
    deleted, _ = ActivityReference.objects.filter(activity_id=activity_id, reference_id=reference_id).delete()
    if not deleted:
        raise DomainError("not_attached", "That reference is not attached to this activity.")
    audit("activity", activity_id, "detach_reference", {"reference": str(reference_id)})
    return True


def persist_preview_attachments(activity, attachment_ids):
    """After campaign create, attach references listed on preview activity payload."""
    for rid in attachment_ids or []:
        try:
            attach_reference(activity.pk, rid, origin="generation_suggest")
        except DomainError as exc:
            if exc.code != "already_attached":
                raise
