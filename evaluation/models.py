import uuid

from django.db import models

from catalogue.models import Entity
from sources.models import MetricDefinition


class DatasetManifest(models.Model):
    """Frozen, as-of dataset definition. Never edited after freezing; a change is a new manifest."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=40)
    metric = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT)
    cutoff = models.DateTimeField()
    fixture_class = models.CharField(max_length=10)
    input_version_ids = models.JSONField()
    policy_version_ids = models.JSONField()
    content_hash = models.CharField(max_length=64)
    splits = models.JSONField()
    criteria = models.JSONField()
    readiness_policy = models.CharField(max_length=40)
    gates = models.JSONField()
    frozen_at = models.DateTimeField()
    holdout_opened_at = models.DateTimeField(null=True)


class ModelRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=40)
    model_ref = models.CharField(max_length=80)
    manifest = models.ForeignKey(DatasetManifest, on_delete=models.PROTECT, related_name="runs")
    configuration = models.JSONField(default=dict)
    report = models.JSONField(default=dict)
    state = models.CharField(max_length=20)
    created_at = models.DateTimeField()


class ForecastRecord(models.Model):
    """Prospective ledger entry: saved before the outcome exists, scored later."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_ref = models.CharField(max_length=80)
    metric = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT)
    fixture_class = models.CharField(max_length=10)
    issued_at = models.DateTimeField()
    information_cutoff = models.DateTimeField()
    target_start = models.DateField()
    target_end = models.DateField(help_text="Exclusive")
    prediction = models.JSONField()
    input_fingerprint = models.CharField(max_length=64)
    actual = models.JSONField(null=True)
    evaluation = models.JSONField(null=True)
    state = models.CharField(max_length=12, default="pending")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(target_end__gt=models.F("target_start")), name="forecast_window_order")]
