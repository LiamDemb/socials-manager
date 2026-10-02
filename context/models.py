import uuid

from django.db import models


class PeerProfile(models.Model):
    STATES = [(s, s) for s in ["pending", "reviewed", "rejected"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    handle = models.CharField(max_length=80)
    label = models.CharField(max_length=200)
    review_state = models.CharField(max_length=12, choices=STATES, default="pending")
    notes = models.TextField(blank=True, default="")
    capability = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True)


class InspirationReference(models.Model):
    SCOPES = [(s, s) for s in ["global", "campaign", "object"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=12, choices=SCOPES, default="global")
    scope_ref = models.CharField(max_length=64, blank=True, default="")
    title = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True, default="")
    published_at = models.DateField(null=True)
    retrieved_at = models.DateTimeField()
    excerpt = models.TextField(blank=True, default="")
    influence = models.TextField(blank=True, default="")


class ReviewedContextItem(models.Model):
    MEANING = [(s, s) for s in ["unknown", "confirmed", "corrected", "rejected"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_label = models.CharField(max_length=200)
    raw_text = models.TextField()
    meaning_state = models.CharField(max_length=12, choices=MEANING, default="unknown")
    reviewed_at = models.DateTimeField(null=True)
    notes = models.TextField(blank=True, default="")
