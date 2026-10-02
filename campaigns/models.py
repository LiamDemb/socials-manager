import uuid

from django.db import models
from django.db.models import Q

from catalogue.models import Artist, Entity, PromotedObject
from sources.models import MetricDefinition


class Campaign(models.Model):
    STATUSES = [("draft", "Draft"), ("active", "Active"), ("paused", "Paused"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT)
    promoted_object = models.ForeignKey(PromotedObject, null=True, blank=True, on_delete=models.PROTECT, related_name="campaigns")
    type = models.CharField(max_length=30)
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    timezone = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=STATUSES, default="draft")
    resources = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end_date__gte=models.F("start_date")), name="campaign_window_order")]
        ordering = ["start_date", "name"]


class Outcome(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField()


class OutcomeVersion(models.Model):
    """Immutable measurement contract. A semantic change creates a new version."""

    MODES = [("total", "Total over window"), ("gain", "Gain from baseline"), ("level", "Level reached")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    outcome = models.ForeignKey(Outcome, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    metric = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT)
    scope_entity = models.ForeignKey(Entity, on_delete=models.PROTECT)
    mode = models.CharField(max_length=8, choices=MODES)
    target = models.BigIntegerField()
    period_start = models.DateField()
    period_end = models.DateField(help_text="Exclusive")
    timezone = models.CharField(max_length=64)
    date_basis = models.CharField(max_length=12, help_text="utc_day or local_day")
    baseline_rule = models.JSONField(default=dict)
    created_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["outcome", "version"], name="unique_outcome_version"),
            models.CheckConstraint(condition=Q(period_end__gt=models.F("period_start")), name="outcome_window_half_open"),
            models.CheckConstraint(condition=Q(target__gte=0), name="outcome_target_non_negative"),
        ]


class CampaignOutcome(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="outcome_links")
    outcome_version = models.ForeignKey(OutcomeVersion, on_delete=models.PROTECT, related_name="campaign_links")
    role = models.CharField(max_length=10, choices=[("primary", "Primary"), ("supporting", "Supporting")])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["campaign", "outcome_version"], name="unique_campaign_outcome"),
            models.UniqueConstraint(fields=["campaign"], condition=Q(role="primary"), name="one_primary_outcome"),
        ]


class Activity(models.Model):
    STATUSES = [("planned", "Planned"), ("completed", "Completed"), ("skipped", "Skipped"), ("cancelled", "Cancelled")]
    KINDS = [("content", "Content"), ("operational", "Operational task"), ("milestone", "Milestone")]
    ORIGINS = [("manual", "Added by you"), ("operational_template", "From your campaign dates")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="activities")
    title = models.CharField(max_length=200)
    purpose = models.TextField(blank=True, default="")
    kind = models.CharField(max_length=12, choices=KINDS, default="content")
    channel = models.CharField(max_length=40, blank=True, default="")
    format = models.CharField(max_length=40, blank=True, default="")
    brief = models.TextField(blank=True, default="")
    cta = models.CharField(max_length=300, blank=True, default="")
    checklist = models.JSONField(default=list)
    planned_at_utc = models.DateTimeField(null=True, blank=True)
    planned_local = models.CharField(max_length=20, blank=True, default="")
    timezone = models.CharField(max_length=64)
    all_day_date = models.DateField(null=True, blank=True)
    actual_at_utc = models.DateTimeField(null=True, blank=True)
    actual_url = models.URLField(max_length=500, blank=True, default="")
    execution_notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUSES, default="planned")
    effort_minutes = models.PositiveIntegerField(default=0)
    origin = models.CharField(max_length=24, choices=ORIGINS, default="manual")
    origin_detail = models.JSONField(default=dict)
    review_flag = models.CharField(max_length=300, blank=True, default="")
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(planned_at_utc__isnull=True) | Q(all_day_date__isnull=True), name="timed_xor_all_day"),
            models.CheckConstraint(condition=~Q(status="completed") | Q(actual_at_utc__isnull=False), name="completed_has_actual"),
        ]
        indexes = [models.Index(fields=["campaign", "planned_at_utc", "status"]), models.Index(fields=["all_day_date"])]


class ActivityOutcome(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="outcome_links")
    outcome_version = models.ForeignKey(OutcomeVersion, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["activity", "outcome_version"], name="unique_activity_outcome")]


class ExecutionEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, related_name="execution_events")
    prior_state = models.CharField(max_length=10)
    new_state = models.CharField(max_length=10)
    actual_at = models.DateTimeField(null=True)
    url = models.URLField(max_length=500, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    actor = models.CharField(max_length=30, default="local-owner")
    recorded_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["recorded_at"]
