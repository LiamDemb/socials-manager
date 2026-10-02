from django.db import transaction

from core import clock
from core.errors import DomainError
from core.services import audit, idempotent

from .models import Experiment


def create_experiment(campaign_id, data, key):
    def run():
        from campaigns.models import Campaign

        campaign = Campaign.objects.get(pk=campaign_id)
        exp = Experiment.objects.create(
            campaign=campaign,
            title=str(data.get("title", "Experiment"))[:200],
            hypothesis=str(data.get("hypothesis", ""))[:5000],
            success_measure=str(data.get("success_measure", ""))[:2000],
            window_start=data["window_start"],
            window_end=data["window_end"],
            protocol={
                "frozen_at": clock.now().isoformat(),
                "activity_ids": data.get("activity_ids") or [],
                "variable": data.get("variable", ""),
                "confounders": data.get("confounders") or [],
            },
            state="draft",
            created_at=clock.now(),
        )
        audit("experiment", exp.pk, "create", {"campaign": str(campaign.pk)})
        return {"experiment_id": str(exp.pk), "state": exp.state}

    return idempotent(key, f"experiment.create:{campaign_id}", run)


def approve_experiment(experiment_id, key):
    def run():
        exp = Experiment.objects.select_for_update().get(pk=experiment_id)
        if exp.state != "draft":
            raise DomainError("invalid_state", "Only draft experiments can be approved.")
        exp.state = "approved"
        exp.protocol = {**exp.protocol, "approved_at": clock.now().isoformat()}
        exp.save(update_fields=["state", "protocol"])
        return {"experiment_id": str(exp.pk), "state": exp.state}

    return idempotent(key, f"experiment.approve:{experiment_id}", run)


def start_experiment(experiment_id, key):
    def run():
        exp = Experiment.objects.select_for_update().get(pk=experiment_id)
        if exp.state != "approved":
            raise DomainError("invalid_state", "Approve the experiment before starting.")
        exp.state = "running"
        exp.save(update_fields=["state"])
        return {"experiment_id": str(exp.pk), "state": exp.state}

    return idempotent(key, f"experiment.start:{experiment_id}", run)


def review_experiment(experiment_id, data, key):
    def run():
        exp = Experiment.objects.select_for_update().get(pk=experiment_id)
        if exp.state not in ("running", "review"):
            raise DomainError("invalid_state", "This experiment is not ready for review.")
        conclusion = str(data.get("conclusion", ""))[:5000]
        if bool(data.get("claims_causal")):
            raise DomainError("causal_claim_denied", "Non-randomised comparisons cannot claim causal proof.")
        exp.result = {
            "conclusion": conclusion,
            "inconclusive": bool(data.get("inconclusive")),
            "reviewed_at": clock.now().isoformat(),
        }
        exp.state = "closed"
        exp.save(update_fields=["result", "state"])
        audit("experiment", exp.pk, "review", {"inconclusive": exp.result["inconclusive"]})
        return {"experiment_id": str(exp.pk), "state": exp.state}

    return idempotent(key, f"experiment.review:{experiment_id}", run)
