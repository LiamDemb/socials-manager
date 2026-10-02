import uuid

from django.db import models
from django.db.models import Q


class Entity(models.Model):
    KINDS = [("artist", "Artist"), ("object", "Promoted object"), ("account", "Account"), ("content", "Content")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KINDS)
    label = models.CharField(max_length=200)
    created_at = models.DateTimeField()

    def __str__(self):
        return self.label


class Artist(models.Model):
    entity = models.OneToOneField(Entity, primary_key=True, on_delete=models.PROTECT, related_name="artist")
    is_own = models.BooleanField(default=False)
    aliases = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["is_own"], condition=Q(is_own=True), name="one_own_artist")]

    @property
    def label(self):
        return self.entity.label


class PromotedObject(models.Model):
    KINDS = [("recording", "Recording"), ("release", "Release"), ("event", "Event"), ("video", "Music video"), ("merch", "Merch item")]
    PRECISION = [("day", "Day"), ("month", "Month"), ("year", "Year"), ("unknown", "Unknown")]
    AUTHORITY = [("owner_confirmed", "Confirmed by you"), ("unverified", "Unverified"), ("provider", "Provider")]
    IDENTITY = [("pending", "Identity pending"), ("confirmed", "Identity confirmed")]

    entity = models.OneToOneField(Entity, primary_key=True, on_delete=models.PROTECT, related_name="promoted_object")
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name="promoted_objects")
    kind = models.CharField(max_length=12, choices=KINDS)
    key_date = models.DateField(null=True, blank=True)
    key_time_local = models.TimeField(null=True, blank=True)
    date_precision = models.CharField(max_length=10, choices=PRECISION, default="unknown")
    date_authority = models.CharField(max_length=20, choices=AUTHORITY, default="unverified")
    timezone = models.CharField(max_length=64, blank=True, default="")
    identity_state = models.CharField(max_length=12, choices=IDENTITY, default="pending")
    metadata = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(kind="event") | ~Q(timezone=""), name="event_has_timezone"),
        ]

    @property
    def label(self):
        return self.entity.label

    @property
    def id(self):
        return self.entity_id


class ObjectRelation(models.Model):
    parent = models.ForeignKey(PromotedObject, on_delete=models.CASCADE, related_name="children")
    child = models.ForeignKey(PromotedObject, on_delete=models.CASCADE, related_name="parents")
    relation = models.CharField(max_length=20, default="contains_track")
    verified_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "child", "relation"], name="unique_object_relation"),
            models.CheckConstraint(condition=~Q(parent=models.F("child")), name="relation_not_self"),
        ]


class ExternalIdentity(models.Model):
    STATES = [("owner_supplied", "Supplied by you"), ("provider_verified", "Provider verified"), ("revoked", "Revoked")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="external_ids")
    provider = models.CharField(max_length=40)
    id_type = models.CharField(max_length=20)
    external_id = models.CharField(max_length=120)
    state = models.CharField(max_length=20, choices=STATES)
    evidence = models.JSONField(default=dict)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "id_type", "external_id"], condition=Q(valid_to__isnull=True), name="unique_active_external_identity"
            )
        ]
