"""Unified inspiration library: Explore (collected posts) and Saved (bookmarks + manual)."""
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q

from .media_labels import channel_for_media_type, display_media_type
from .models import InspirationReference, PeerMedia, PeerProfile
from .roles import CREATIVE_EXPLORE_ROLES


def _eligible_peers_qs():
    return PeerProfile.objects.filter(review_state="reviewed", peer_role__in=CREATIVE_EXPLORE_ROLES)


def explore_media_queryset(peer_id=None, media_type=None, q=""):
    bookmarked = InspirationReference.objects.filter(peer_media_id=OuterRef("pk"), is_bookmark=True)
    qs = (
        PeerMedia.objects.filter(peer__in=_eligible_peers_qs())
        .select_related("peer")
        .annotate(is_saved=Exists(bookmarked))
        .order_by("-published_at", "-collected_at")
    )
    if peer_id:
        qs = qs.filter(peer_id=peer_id)
    if media_type:
        qs = qs.filter(media_type__iexact=media_type)
    if q:
        qs = qs.filter(Q(caption__icontains=q) | Q(peer__label__icontains=q))
    return qs


def saved_references_queryset(peer_id=None, q=""):
    qs = InspirationReference.objects.filter(
        Q(is_bookmark=True) | Q(origin_type="manual")
    ).select_related("peer_media", "peer_media__peer").order_by("-retrieved_at")
    if peer_id:
        qs = qs.filter(Q(peer_media__peer_id=peer_id) | Q(scope_ref=str(peer_id)))
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(owner_note__icontains=q))
    return qs


def paginate(qs, page, per_page=24):
    p = Paginator(qs, per_page)
    page_obj = p.get_page(page)
    return page_obj, p.num_pages, p.count


def media_card(media: PeerMedia, saved_ref_id=None, is_saved=False) -> dict:
    snap = media.snapshot or {}
    likes = snap.get("like_count")
    comments = snap.get("comments_count")
    metrics = {}
    if likes is not None:
        metrics["public_likes"] = likes
    if comments is not None:
        metrics["public_comments"] = comments
    return {
        "kind": "peer_media",
        "id": str(media.pk),
        "canonical_key": f"peer_media:{media.pk}",
        "peer_id": str(media.peer_id),
        "peer_label": media.peer.label,
        "peer_role": media.peer.peer_role,
        "channel": channel_for_media_type(media.media_type),
        "media_type": media.media_type,
        "media_type_display": display_media_type(media.media_type),
        "published_at": media.published_at.isoformat() if media.published_at else None,
        "collected_at": media.collected_at.isoformat(),
        "caption_excerpt": (media.caption or "")[:280],
        "permalink": media.permalink or "",
        "is_saved": bool(is_saved or saved_ref_id),
        "saved_reference_id": str(saved_ref_id) if saved_ref_id else None,
        "metrics": metrics,
        "metrics_note": "Public counts at collection; not performance proof.",
    }


def reference_card(ref: InspirationReference) -> dict:
    media = ref.peer_media
    if media:
        base = media_card(media, saved_ref_id=ref.pk if ref.is_bookmark else None, is_saved=ref.is_bookmark)
        base["kind"] = "saved_reference"
        base["reference_id"] = str(ref.pk)
        base["title"] = ref.title or f"{media.peer.label} post"
        base["owner_note"] = ref.owner_note
        base["origin_type"] = ref.origin_type
        return base
    return {
        "kind": "saved_reference",
        "reference_id": str(ref.pk),
        "canonical_key": ref.canonical_key or f"manual:{ref.pk}",
        "title": ref.title,
        "url": ref.url,
        "excerpt": ref.excerpt,
        "owner_note": ref.owner_note,
        "origin_type": ref.origin_type,
        "scope": ref.scope,
        "retrieved_at": ref.retrieved_at.isoformat(),
        "is_saved": True,
        "channel": "external",
        "media_type_display": "Manual reference",
        "metrics_note": "Manual link; performance not verified by this app.",
    }


def library_state_summary() -> dict:
    peers = _eligible_peers_qs().count()
    posts = PeerMedia.objects.filter(peer__in=_eligible_peers_qs()).count()
    saved = InspirationReference.objects.filter(Q(is_bookmark=True) | Q(origin_type="manual")).count()
    return {"eligible_peers": peers, "explore_posts": posts, "saved_count": saved}
