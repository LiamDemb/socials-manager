import uuid

from django.db import models

from campaigns.models import Activity, Campaign


class SchedulingDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="scheduling_decisions")
    version = models.PositiveIntegerField()
    requested_window = models.JSONField(default=dict)
    feasible_candidates = models.JSONField(default=list)
    chosen_local = models.CharField(max_length=32)
    timezone = models.CharField(max_length=64)
    basis = models.CharField(max_length=80)
    fallback = models.BooleanField(default=False)
    rule_version = models.CharField(max_length=40, default="scheduler-v1")
    evidence_refs = models.JSONField(default=list)
    created_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["activity", "version"], name="unique_schedule_version")]
        ordering = ["-version"]


class RecommendationRecord(models.Model):
    STATES = [("draft", "Draft"), ("validated", "Validated"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("superseded", "Superseded")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="recommendations", null=True, blank=True)
    state = models.CharField(max_length=12, choices=STATES, default="draft")
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    evidence_bundle = models.JSONField(default=dict)
    generation = models.JSONField(default=dict)
    validation = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]


class Experiment(models.Model):
    STATES = [("draft", "Draft"), ("approved", "Approved"), ("running", "Running"), ("review", "Review"), ("closed", "Closed")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="experiments")
    title = models.CharField(max_length=200)
    hypothesis = models.TextField()
    success_measure = models.TextField()
    window_start = models.DateField()
    window_end = models.DateField()
    protocol = models.JSONField(default=dict)
    state = models.CharField(max_length=12, choices=STATES, default="draft")
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]


class AdaptationProposal(models.Model):
    STATES = [("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("superseded", "Superseded")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="adaptations")
    fingerprint = models.CharField(max_length=64)
    summary = models.CharField(max_length=300)
    diff = models.JSONField(default=dict)
    evidence = models.JSONField(default=dict)
    state = models.CharField(max_length=12, choices=STATES, default="pending")
    base_campaign_revision = models.PositiveIntegerField()
    created_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "fingerprint"], name="unique_adaptation_fingerprint")]
        ordering = ["-created_at"]


class AnalysisSpec(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=80, unique=True)
    family = models.CharField(max_length=40)
    version = models.CharField(max_length=40)
    target_metric_id = models.CharField(max_length=80, blank=True, default="")
    config = models.JSONField(default=dict)
    runnable = models.BooleanField(default=False)
    created_at = models.DateTimeField()


class FitRun(models.Model):
    STATUSES = [
        ("ready", "ready"),
        ("exploratory", "exploratory"),
        ("qualified", "qualified"),
        ("insufficient_data", "insufficient_data"),
        ("blocked", "blocked"),
        ("stale", "stale"),
        ("descriptive_only", "descriptive_only"),
        ("pending", "pending"),
        ("failed", "failed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spec = models.ForeignKey(AnalysisSpec, on_delete=models.PROTECT, related_name="runs")
    cache_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=24, choices=STATUSES)
    blocker_code = models.CharField(max_length=80, blank=True, default="")
    lineage = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField()


class CohortVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy_version = models.CharField(max_length=40)
    fingerprint = models.CharField(max_length=64, unique=True)
    membership = models.JSONField(default=dict)
    stale = models.BooleanField(default=False)
    created_at = models.DateTimeField()


class AskExchange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.TextField()
    scope = models.JSONField(default=dict)
    answer = models.JSONField(default=dict)
    generation = models.JSONField(default=dict)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
