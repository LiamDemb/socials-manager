import re
from datetime import date

from django.db import transaction

from core import clock
from core.errors import DomainError
from core.services import audit, conditional_update, emit

from .models import Artist, Entity, ExternalIdentity, ObjectRelation, PromotedObject

SPOTIFY_URL = re.compile(
    r"^(?:https?://open\.spotify\.com/(?:intl-[a-z]{2}(?:-[a-z]{2})?/)?(?P<kind>artist|track|album)/(?P<id>[A-Za-z0-9]{22})(?:[/?#].*)?"
    r"|spotify:(?P<kind2>artist|track|album):(?P<id2>[A-Za-z0-9]{22}))$"
)
ISRC = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{2}[0-9]{5}$")


def parse_spotify_reference(text, expected_kind):
    match = SPOTIFY_URL.match((text or "").strip())
    if not match:
        raise DomainError("invalid_spotify_url", f"Paste a Spotify {expected_kind} link, for example https://open.spotify.com/{expected_kind}/…",
                          fields={"spotify_url": "Not a recognised Spotify link"})
    kind = match.group("kind") or match.group("kind2")
    ident = match.group("id") or match.group("id2")
    if kind != expected_kind:
        raise DomainError("wrong_spotify_kind", f"That is a Spotify {kind} link; this needs a {expected_kind} link.",
                          fields={"spotify_url": f"Expected a {expected_kind} link"})
    return ident


def normalise_isrc(text):
    value = (text or "").replace("-", "").replace(" ", "").upper()
    if not ISRC.match(value):
        raise DomainError("invalid_isrc", "An ISRC has 12 characters, for example AUABC2600001.", fields={"isrc": "Not a valid ISRC"})
    return value


def own_artist():
    return Artist.objects.select_related("entity").filter(is_own=True).first()


@transaction.atomic
def create_own_artist(label):
    if own_artist():
        raise DomainError("own_artist_exists", "This installation already has its artist.")
    entity = Entity.objects.create(kind="artist", label=label.strip(), created_at=clock.now())
    artist = Artist.objects.create(entity=entity, is_own=True)
    audit("artist", entity.id, "create", {"label": entity.label})
    return artist


def _set_identity(entity, provider, id_type, external_id, evidence):
    clash = ExternalIdentity.objects.filter(provider=provider, id_type=id_type, external_id=external_id, valid_to__isnull=True).exclude(entity=entity)
    if clash.exists():
        raise DomainError("identity_in_use", f"That {provider} {id_type} is already mapped to {clash.first().entity.label}.")
    now = clock.now()
    current = ExternalIdentity.objects.filter(entity=entity, provider=provider, id_type=id_type, valid_to__isnull=True).first()
    if current and current.external_id == external_id:
        return current
    if current:
        current.valid_to = now
        current.save(update_fields=["valid_to"])
    identity = ExternalIdentity.objects.create(
        entity=entity, provider=provider, id_type=id_type, external_id=external_id, state="owner_supplied", evidence=evidence, valid_from=now
    )
    audit("entity", entity.id, "external_identity", {"provider": provider, "id_type": id_type, "external_id": external_id})
    return identity


@transaction.atomic
def set_artist_spotify(artist, url):
    ident = parse_spotify_reference(url, "artist")
    return _set_identity(artist.entity, "spotify", "artist", ident, {"supplied_url": url.strip()})


def active_identities(entity):
    return list(ExternalIdentity.objects.filter(entity=entity, valid_to__isnull=True).order_by("provider", "id_type"))


@transaction.atomic
def create_object(kind, label, key_date=None, timezone="", date_authority="unverified", metadata=None, key_time_local=None):
    artist = own_artist()
    if not artist:
        raise DomainError("no_artist", "Set up the artist first.")
    if kind not in dict(PromotedObject.KINDS):
        raise DomainError("invalid_kind", "Unknown object type.")
    label = (label or "").strip()
    if not label:
        raise DomainError("label_required", "Give it a name.", fields={"label": "Required"})
    if kind == "event" and not timezone:
        raise DomainError("event_timezone_required", "An event needs its local timezone.", fields={"timezone": "Required"})
    entity = Entity.objects.create(kind="object", label=label[:200], created_at=clock.now())
    obj = PromotedObject.objects.create(
        entity=entity,
        artist=artist,
        kind=kind,
        key_date=key_date,
        key_time_local=key_time_local,
        date_precision="day" if key_date else "unknown",
        date_authority=date_authority if key_date else "unverified",
        timezone=timezone,
        metadata=metadata or {},
    )
    audit("object", entity.id, "create", {"kind": kind, "label": label, "key_date": str(key_date) if key_date else None})
    return obj


def recompute_identity_state(obj):
    ids = {(i.provider, i.id_type) for i in active_identities(obj.entity)}
    if obj.kind == "recording":
        has_id = ("spotify", "track") in ids or ("isrc", "isrc") in ids
    elif obj.kind == "release":
        has_id = ("spotify", "album") in ids or ("upc", "upc") in ids
    else:
        has_id = True
    confirmed = has_id and obj.key_date is not None and obj.date_authority == "owner_confirmed"
    state = "confirmed" if confirmed else "pending"
    if state != obj.identity_state:
        PromotedObject.objects.filter(pk=obj.pk).update(identity_state=state)
        obj.identity_state = state
    return state


@transaction.atomic
def update_object(obj_id, expected_revision, label=None, key_date=..., date_confirmed=None, spotify_url=None, isrc=None, metadata=None):
    obj = PromotedObject.objects.select_related("entity").get(pk=obj_id)
    changes = {}
    old_date = obj.key_date
    if key_date is not ...:
        changes["key_date"] = key_date
        changes["date_precision"] = "day" if key_date else "unknown"
    if date_confirmed is not None:
        changes["date_authority"] = "owner_confirmed" if (date_confirmed and changes.get("key_date", obj.key_date)) else "unverified"
    if metadata is not None:
        changes["metadata"] = {**obj.metadata, **metadata}
    conditional_update(PromotedObject, obj.pk, expected_revision, what="object", **changes)
    if label is not None and label.strip() and label.strip() != obj.entity.label:
        Entity.objects.filter(pk=obj.pk).update(label=label.strip()[:200])
    if spotify_url:
        kind = {"recording": "track", "release": "album"}.get(obj.kind)
        if not kind:
            raise DomainError("no_spotify_kind", "Spotify links apply to recordings and releases.")
        _set_identity(obj.entity, "spotify", kind, parse_spotify_reference(spotify_url, kind), {"supplied_url": spotify_url.strip()})
    if isrc:
        if obj.kind != "recording":
            raise DomainError("isrc_recording_only", "An ISRC identifies a recording.")
        _set_identity(obj.entity, "isrc", "isrc", normalise_isrc(isrc), {})
    obj.refresh_from_db()
    recompute_identity_state(obj)
    audit("object", obj.pk, "update", {k: str(v) for k, v in changes.items()}, revision=obj.revision)
    if "key_date" in changes and changes["key_date"] != old_date:
        emit("object.key_date_changed", {"object_id": str(obj.pk), "from": str(old_date), "to": str(changes["key_date"]), "at": clock.now().isoformat()})
        from campaigns.services import flag_work_for_date_change

        flag_work_for_date_change(object_id=obj.pk, reason=f"{obj.entity.label} date changed from {old_date or 'unset'} to {changes['key_date'] or 'unset'}")
    return obj


@transaction.atomic
def relate(parent_id, child_id, relation="contains_track"):
    parent = PromotedObject.objects.get(pk=parent_id)
    child = PromotedObject.objects.get(pk=child_id)
    if parent.kind != "release" or child.kind != "recording":
        raise DomainError("invalid_relation", "Only a release can contain a recording.")
    rel, _ = ObjectRelation.objects.get_or_create(parent=parent, child=child, relation=relation)
    return rel


def release_recordings(release_id):
    return list(PromotedObject.objects.filter(parents__parent_id=release_id, parents__relation="contains_track").distinct())


def parse_date(text, field="date"):
    if text in (None, ""):
        return None
    try:
        return date.fromisoformat(str(text))
    except ValueError:
        raise DomainError("invalid_date", "Use a valid date (YYYY-MM-DD).", fields={field: "Invalid date"})
