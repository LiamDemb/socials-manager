import uuid

from django.db import models

from catalogue.models import Entity


class Finding(models.Model):
    STATUSES = [(s, s) for s in ["draft", "eligible", "published", "superseded"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    summary = models.TextField()
    method_version = models.CharField(max_length=80)
    status = models.CharField(max_length=12, choices=STATUSES, default="draft")
    entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.PROTECT)
    metric_id = models.CharField(max_length=80, blank=True, default="")
    comparison = models.JSONField(default=dict)
    lineage = models.JSONField(default=dict)
    computed_at = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-computed_at"]


class EvidenceBundle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name="bundles")
    version = models.PositiveIntegerField()
    observation_refs = models.JSONField(default=list)
    window_start = models.DateField(null=True)
    window_end = models.DateField(null=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["finding", "version"], name="unique_bundle_version")]
        ordering = ["-version"]
