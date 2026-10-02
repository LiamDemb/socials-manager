"""Analysis resolver: eligibility, cache, queue, honest status codes."""
from core import clock
from core.services import enqueue

from .lineage import cache_key, lineage_parts
from .registry import sync_analysis_specs

RESOLVER_VERSION = "resolver-v1"

STATUS_READY = "ready"
STATUS_DESCRIPTIVE_ONLY = "descriptive_only"
STATUS_EXPLORATORY = "exploratory"
STATUS_PENDING = "pending"
STATUS_INSUFFICIENT = "insufficient_data"
STATUS_UNSUPPORTED = "unsupported_question"
STATUS_RESTRICTED = "restricted"
STATUS_STALE = "stale"
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"


class AnalysisResolver:
    def __init__(self):
        sync_analysis_specs()

    def resolve_or_queue(self, request: dict, ctx: dict, purpose: str = "analysis") -> dict:
        from .models import AnalysisSpec, FitRun

        key = request.get("analysis_key")
        spec = AnalysisSpec.objects.filter(key=key).first()
        if not spec:
            return self._result(request, STATUS_UNSUPPORTED, detail=f"Unknown analysis_key {key}")

        if not spec.runnable:
            return self._result(request, STATUS_UNSUPPORTED, detail="Spec registered but no runner")

        metric_id = request.get("metric_id") or ctx.get("primary_metric_id") or ""
        cohort_fp = (ctx.get("cohort") or {}).get("fingerprint") or "cohort-none"
        dataset_hash = ctx.get("dataset_hash") or "dataset-empty"
        policy_versions = ctx.get("policy_versions") or {}
        parts = lineage_parts(spec.key, metric_id, cohort_fp, dataset_hash, policy_versions)
        ck = cache_key({**parts, "query": request, "resolver": RESOLVER_VERSION})

        existing = FitRun.objects.filter(cache_key=ck).first()
        if existing:
            if existing.status == STATUS_STALE:
                return self._result(request, STATUS_STALE, run_id=str(existing.pk), detail="Fit stale")
            if existing.status == STATUS_BLOCKED:
                return self._result(
                    request,
                    STATUS_BLOCKED,
                    run_id=str(existing.pk),
                    blocker_code=existing.blocker_code or "blocked",
                    detail=existing.result.get("detail"),
                )
            if existing.status in (STATUS_READY, STATUS_EXPLORATORY, "qualified", STATUS_DESCRIPTIVE_ONLY):
                return self._result(request, existing.status, run_id=str(existing.pk), result=existing.result)

        # Policy gate (simplified: require metric purpose if metric set)
        if metric_id and purpose == "llm_ingest":
            return self._result(request, STATUS_RESTRICTED, detail="llm_ingest not analysis purpose")

        from .stats.runner import execute_spec

        outcome = execute_spec(spec, request, ctx)
        status = outcome.get("status") or STATUS_FAILED
        if status == STATUS_BLOCKED:
            run = FitRun.objects.create(
                spec=spec,
                cache_key=ck,
                status=STATUS_BLOCKED,
                blocker_code=outcome.get("blocker_code") or "dependency_unavailable",
                lineage=parts,
                result=outcome,
                created_at=clock.now(),
            )
            return self._result(
                request,
                STATUS_BLOCKED,
                run_id=str(run.pk),
                blocker_code=run.blocker_code,
                detail=outcome.get("detail"),
                descriptive=outcome.get("descriptive"),
            )

        run = FitRun.objects.create(
            spec=spec,
            cache_key=ck,
            status=status,
            blocker_code="",
            lineage=parts,
            result=outcome,
            created_at=clock.now(),
        )
        if status == STATUS_PENDING:
            enqueue("analysis.fit", scope_key=spec.key, input_key=ck)
        return self._result(request, status, run_id=str(run.pk), result=outcome)

    def resolve_agenda(self, agenda: list, ctx: dict) -> list[dict]:
        return [self.resolve_or_queue(req, ctx) for req in agenda]

    def _result(self, request, status, run_id=None, result=None, detail=None, blocker_code=None, descriptive=None):
        return {
            "request": request,
            "status": status,
            "run_id": run_id,
            "result": result or {},
            "detail": detail,
            "blocker_code": blocker_code,
            "descriptive": descriptive,
        }
