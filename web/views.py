from datetime import timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from campaigns import measurement, registry
from campaigns.models import Activity, Campaign, OutcomeVersion
from campaigns.services import TRANSITIONS, describe_outcome, due_work, has_source, outcome_progress, upcoming_milestones
from catalogue.models import Entity, PromotedObject
from catalogue.services import active_identities, own_artist
from core import clock, instance
from core.errors import DomainError
from sources import services as sources
from sources.models import ImportBatch, MetricDefinition, Observation, ObservationVersion, Source

from . import presenters as p

NAV = [("today", "Today"), ("campaigns", "Campaigns"), ("evidence", "Evidence"), ("peers", "Peers"), ("inspiration", "Inspiration"), ("sources", "Sources")]
EVIDENCE_TABS = [("findings", "Findings"), ("data", "Observed data"), ("review", "Review context")]


def page(request, template, section, title, **ctx):
    if not instance.is_initialised():
        return render(request, "web/setup.html", {"data_root": settings.DATA_ROOT}, status=503)
    cfg = instance.load()
    return render(request, template, {"section": section, "page_title": title, "nav": NAV, "cfg": cfg, "artist": own_artist(),
                                      "local_now": p.local_now(), **ctx})


def fragment(request, template, **ctx):
    return render(request, template, {"cfg": instance.load(), **ctx})


# Pages

@require_GET
def today(request):
    if not instance.is_initialised():
        return page(request, "", "", "")
    now = clock.now()
    due = [p.activity_view(a, now) for a, _ in due_work(now)]
    milestones = [p.activity_view(a, now) for a in upcoming_milestones(now)]
    return page(request, "web/today.html", "today", "Today", trends=p.trend_cards(), outcomes=p.outcome_rows(p.active_campaigns()),
                due=due, milestones=milestones, alerts=p.alerts(), campaigns=p.active_campaigns(),
                has_data=Observation.objects.filter(active_version__isnull=False).exists())


@require_GET
def campaigns(request):
    qs = Campaign.objects.select_related("promoted_object__entity").order_by("-start_date")
    grouped = {s: [c for c in qs if c.status == s] for s in ("active", "draft", "paused", "completed", "cancelled")}
    return page(request, "web/campaigns.html", "campaigns", "Campaigns", grouped=grouped, outcomes=p.outcome_rows(),
                any_campaigns=qs.exists())


@require_GET
def calendar(request):
    ctx = p.calendar_context(request, p.active_campaigns())
    return page(request, "web/calendar.html", "campaigns", "Calendar", cal=ctx, base_url=request.path)


@require_GET
def campaign(request, campaign_id, tab="calendar"):
    c = get_object_or_404(Campaign.objects.select_related("promoted_object__entity"), pk=campaign_id)
    if tab not in ("calendar", "strategy", "outcomes", "learning"):
        raise Http404
    ctx = {"c": c, "tab": tab, "tabs": [("calendar", "Calendar"), ("strategy", "Strategy"), ("outcomes", "Outcomes"), ("learning", "Learning")],
           "base_url": request.path}
    if tab == "calendar":
        today_local = p.local_now().date()
        default_month = c.start_date if c.start_date > today_local else (c.end_date if c.end_date < today_local else today_local)
        ctx["cal"] = p.calendar_context(request, Campaign.objects.filter(pk=c.pk), default_month=default_month)
    if tab == "outcomes":
        ctx["outcomes"] = p.outcome_rows(Campaign.objects.filter(pk=c.pk))
        ctx["roles"] = {link.outcome_version_id: link.role for link in c.outcome_links.all()}
    if tab == "strategy":
        from intelligence.models import RecommendationRecord

        acts = list(c.activities.all())
        ctx["counts"] = {
            "total": len(acts),
            "operational": sum(a.origin == "operational_template" for a in acts),
            "manual": sum(a.origin == "manual" for a in acts),
            "evidence": sum(a.origin == "evidence_recommendation" for a in acts),
        }
        rec = RecommendationRecord.objects.filter(campaign=c).order_by("-created_at").first()
        ctx["strategy_gaps"] = (rec.evidence_bundle or {}).get("gaps") if rec else []
        ctx["strategy_composition"] = ((rec.payload or {}).get("meta") or {}) if rec else {}
        if not ctx["strategy_gaps"] and not ctx["counts"]["evidence"]:
            ctx["strategy_gaps"] = ["No evidence-backed activities on this campaign yet."]
    return page(request, "web/campaign.html", "campaigns", c.name, **ctx)


def _evidence_filters(request):
    return {k: request.GET.get(k, "") for k in ("entity", "metric", "start", "end")}


@require_GET
def evidence(request, tab="findings"):
    if tab not in dict(EVIDENCE_TABS):
        raise Http404
    ctx = {"tab": tab, "tabs": EVIDENCE_TABS}
    if tab == "findings":
        from findings.models import Finding

        ctx["findings"] = Finding.objects.filter(status="published").select_related("entity")[:50]
    if tab == "review":
        from context.models import ReviewedContextItem

        ctx["review_items"] = ReviewedContextItem.objects.order_by("-reviewed_at", "source_label")[:50]
    if tab == "data":
        f = _evidence_filters(request)
        rows = p.coverage_rows()
        if f["entity"]:
            rows = [r for r in rows if str(r["entity"].pk) == f["entity"]]
        if f["metric"]:
            rows = [r for r in rows if r["metric"].pk == f["metric"]]
        ctx.update(filters=f, rows=rows, entities=sources.committed_entities(),
                   metrics=MetricDefinition.objects.filter(pk__in=Observation.objects.values("metric_id")).order_by("label"))
    return page(request, "web/evidence.html", "evidence", "Evidence", **ctx)


@require_GET
def evidence_series(request, entity_id, metric_id):
    entity = get_object_or_404(Entity, pk=entity_id)
    metric = get_object_or_404(MetricDefinition, pk=metric_id)
    f = _evidence_filters(request)
    start = _safe_date(f["start"])
    end = _safe_date(f["end"])
    points = sources.series(entity, metric.pk, start=start, end=(end + timedelta(days=1)) if end else None)
    total, rule = measurement.aggregate(metric.kind, [(d, v) for d, v, _ in points])
    rows = list(reversed(points))
    pager = Paginator(rows, 100).get_page(request.GET.get("page"))
    back_query = "&".join(f"{k}={v}" for k, v in f.items() if v)
    return page(request, "web/evidence_series.html", "evidence", f"{metric.label}: {entity.label}", entity=entity, metric=metric,
                pager=pager, total=total, rule=rule, filters=f, back_query=back_query, tab="data", tabs=EVIDENCE_TABS,
                count=len(points), first=points[0][0] if points else None, through=points[-1][0] if points else None)


def _safe_date(text):
    from datetime import date

    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


@require_GET
def sources_page(request):
    spotify = sources.ensure_spotify_source()
    policy = sources.current_policy(spotify)
    batches = ImportBatch.objects.select_related("mapped_entity", "raw_file").order_by("-created_at")[:50]
    instagram = sources.refresh_instagram_source()
    return page(request, "web/sources.html", "sources", "Sources", spotify=spotify, policy=policy, batches=batches,
                coverage=p.coverage_rows(), purposes=list(policy.purposes.items()), instagram=instagram)


@require_GET
def import_batch(request, batch_id):
    batch = get_object_or_404(ImportBatch.objects.select_related("mapped_entity", "raw_file", "source", "policy_version"), pk=batch_id)
    if batch.state == "staged":
        batch = sources.refresh_preview(batch.pk)
        batch.refresh_from_db()
    conflicts = batch.staged.filter(classification="conflict").select_related("existing_version", "metric").order_by("period_start")[:200]
    recordings = PromotedObject.objects.filter(kind="recording").select_related("entity").order_by("entity__label")
    return page(request, "web/import_batch.html", "sources", f"Import: {batch.original_name}", batch=batch, conflicts=conflicts,
                issues=batch.issues.all()[:200], recordings=recordings, suggested=sources.suggested_label(batch.original_name),
                metrics=batch.staged.values_list("metric__label", flat=True).distinct())


@require_GET
def import_download(request, batch_id, kind):
    batch = get_object_or_404(ImportBatch, pk=batch_id)
    try:
        if kind == "original":
            body, name = sources.read_raw(batch.raw_file), batch.original_name
        elif kind == "source" and batch.mapped_entity_id and batch.state == "committed":
            body, name = sources.export_source_shaped(batch.mapped_entity), f"{batch.mapped_entity.label}-source-shaped.csv"
        elif kind == "common" and batch.mapped_entity_id and batch.state == "committed":
            body, name = sources.export_common(batch.mapped_entity), f"{batch.mapped_entity.label}-common.csv"
        else:
            raise Http404
    except DomainError as exc:
        return HttpResponse(exc.message, status=exc.status, content_type="text/plain")
    response = HttpResponse(body, content_type="text/csv")
    safe = "".join(ch if ch.isalnum() or ch in " ._-()" else "_" for ch in name)
    response["Content-Disposition"] = f'attachment; filename="{safe}"'
    return response


@require_GET
def export_all(request):
    response = HttpResponse(sources.export_common(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="socials-manager-observations.csv"'
    return response


@require_GET
def settings_page(request):
    from core import diagnostics
    from core.backup import list_backups
    from evaluation.models import ForecastRecord
    from evaluation.services import availability_ledger, gate_report

    artist = own_artist()
    gates = []
    for entity in sources.committed_entities():
        for metric in MetricDefinition.objects.filter(kind="flow", pk__in=Observation.objects.filter(entity=entity).values("metric_id")):
            gates.append({"entity": entity, "metric": metric, "report": gate_report(entity, metric.pk)})
    objects = PromotedObject.objects.select_related("entity").order_by("kind", "entity__label")
    return page(request, "web/settings.html", "settings", "Settings", artist_ids=active_identities(artist.entity) if artist else [],
                objects=objects, backups=list_backups()[:10], diag=diagnostics.report(), gates=gates,
                ledger=availability_ledger(20), forecasts=ForecastRecord.objects.order_by("-issued_at")[:20])


@require_GET
def placeholder(request, section):
    if section == "peers":
        from context.models import PeerCandidate, PeerProfile

        return page(
            request,
            "web/peers.html",
            "peers",
            "Peers",
            peers=PeerProfile.objects.prefetch_related("media").order_by("label"),
            candidates=PeerCandidate.objects.filter(review_state="pending").order_by("-match_score", "name")[:50],
            reviewed_count=PeerProfile.objects.filter(review_state="reviewed").count(),
        )
    if section == "inspiration":
        from context.models import InspirationReference

        refs = InspirationReference.objects.order_by("-retrieved_at")[:50]
        return page(request, "web/inspiration.html", "inspiration", "Inspiration", refs=refs)
    if section == "ask":
        from intelligence.llm_adapter import health
        from intelligence.models import AskExchange

        return page(
            request,
            "web/ask.html",
            "ask",
            "Ask",
            llm=health(),
            exchanges=AskExchange.objects.all()[:10],
        )
    raise Http404


# Dialog fragments

@require_GET
def ui_activity(request, activity_id):
    a = get_object_or_404(Activity.objects.select_related("campaign__promoted_object__entity"), pk=activity_id)
    return fragment(request, "web/dialogs/activity.html", v=p.activity_view(a), events=a.execution_events.order_by("recorded_at"),
                    outcomes=[link.outcome_version for link in a.outcome_links.select_related("outcome_version__metric")],
                    default_actual=clock.now())


@require_GET
def ui_activity_edit(request, activity_id):
    a = get_object_or_404(Activity.objects.select_related("campaign"), pk=activity_id)
    return fragment(request, "web/dialogs/activity_edit.html", v=p.activity_view(a), formats=registry.FORMATS)


@require_GET
def ui_activity_new(request, campaign_id):
    c = get_object_or_404(Campaign, pk=campaign_id)
    return fragment(request, "web/dialogs/activity_new.html", c=c, channels=registry.CHANNELS, date_hint=request.GET.get("date", ""))


@require_GET
def ui_activity_why(request, activity_id):
    a = get_object_or_404(Activity.objects.select_related("campaign"), pk=activity_id)
    outcomes = [link.outcome_version for link in a.outcome_links.select_related("outcome_version__metric", "outcome_version__scope_entity")]
    sources_for = Source.objects.filter(provider__in={ov.metric.provider for ov in outcomes})
    return fragment(request, "web/dialogs/why.html", v=p.activity_view(a), outcomes=outcomes, sources_for=sources_for)


@require_GET
def ui_activity_timing(request, activity_id):
    a = get_object_or_404(Activity, pk=activity_id)
    return fragment(request, "web/dialogs/timing.html", v=p.activity_view(a))


@require_GET
def ui_source(request, source_id):
    s = get_object_or_404(Source, pk=source_id)
    policy = s.policies.order_by("-version").first()
    coverage = [r for r in p.coverage_rows() if r["metric"].provider == s.provider]
    return fragment(request, "web/dialogs/source.html", s=s, policy=policy, coverage=coverage,
                    batches=s.batches.filter(state="committed").order_by("-committed_at")[:10])


@require_GET
def ui_outcome(request, ov_id):
    ov = get_object_or_404(OutcomeVersion.objects.select_related("metric", "scope_entity"), pk=ov_id)
    progress = outcome_progress(ov)
    return fragment(request, "web/dialogs/outcome.html", ov=ov, progress=progress, status_label=measurement.STATUS_LABEL[progress.status],
                    tone=measurement.STATUS_TONE[progress.status], campaigns=[link.campaign for link in ov.campaign_links.select_related("campaign")],
                    source=Source.objects.filter(provider=ov.metric.provider).first(), window_end=ov.period_end - timedelta(days=1))


@require_GET
def ui_observation(request, version_id):
    """Opened from a value row, so keyed by the version that row displayed."""
    version = get_object_or_404(ObservationVersion.objects.select_related("observation"), pk=version_id)
    o = Observation.objects.select_related("entity", "metric", "source").get(pk=version.observation_id)
    versions = o.versions.select_related("policy_version").prefetch_related("contributions__batch").order_by("-version")
    return fragment(request, "web/dialogs/observation.html", o=o, versions=versions, shown=version)


@require_GET
def ui_upload(request):
    return fragment(request, "web/dialogs/upload.html", max_mb=settings.MAX_UPLOAD_BYTES // (1024 * 1024))


@require_GET
def ui_campaign_new(request):
    objects = PromotedObject.objects.select_related("entity").order_by("entity__label")
    metrics = sorted(MetricDefinition.objects.exclude(outcome_modes=[]), key=lambda m: (not has_source(m), m.label))
    reusable = [{"ov": ov, "label": describe_outcome(ov), "end": ov.period_end - timedelta(days=1)}
                for ov in OutcomeVersion.objects.select_related("metric", "scope_entity")]
    return fragment(request, "web/dialogs/campaign_new.html", types=registry.TYPES, objects=objects, metrics=metrics,
                    channels=registry.CHANNELS, today=p.local_now().date(), sourced={m.pk: has_source(m) for m in metrics},
                    reusable=reusable, default_time=instance.load()["default_post_time"])


@require_GET
def ui_campaign_edit(request, campaign_id):
    c = get_object_or_404(Campaign, pk=campaign_id)
    transitions = [t for (s, t) in sorted(TRANSITIONS) if s == c.status]
    return fragment(request, "web/dialogs/campaign_edit.html", c=c, transitions=transitions)


@require_GET
def ui_outcome_add(request, campaign_id):
    c = get_object_or_404(Campaign.objects.select_related("promoted_object"), pk=campaign_id)
    linked = set(c.outcome_links.values_list("outcome_version_id", flat=True))
    candidates = [{"ov": ov, "label": describe_outcome(ov), "end": ov.period_end - timedelta(days=1)}
                  for ov in OutcomeVersion.objects.select_related("metric", "scope_entity").exclude(pk__in=linked)]
    return fragment(request, "web/dialogs/outcome_add.html", c=c, candidates=candidates,
                    metrics=MetricDefinition.objects.exclude(outcome_modes=[]).order_by("provider", "label"))


@require_GET
def ui_object(request, object_id=None):
    obj = get_object_or_404(PromotedObject.objects.select_related("entity"), pk=object_id) if object_id else None
    ids = {(i.provider, i.id_type): i for i in active_identities(obj.entity)} if obj else {}
    return fragment(request, "web/dialogs/object.html", obj=obj, ids=ids, kinds=PromotedObject.KINDS)


def root(request):
    return redirect("today")


def favicon(request):
    return HttpResponse(status=204)
