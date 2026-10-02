"""Analysis agenda from campaign needs (not primary-metric allowlist)."""
AGENDA_VERSION = "agenda-v1"


def build_analysis_agenda(ctx: dict, needs: dict) -> list[dict]:
    """Return typed analysis request dicts for the resolver."""
    priorities = needs.get("role_priorities") or []
    group = ctx.get("campaign_group") or "growth"
    agenda = []
    if "discovery" in priorities[:3] or group == "growth":
        agenda.append(
            {
                "intent": "summary",
                "analysis_key": "post_public_response_v1",
                "scope": "own_and_comparable_peers",
                "context": {"campaign_group": group},
                "requested_use": "campaign_draft",
            }
        )
    if "engagement" in priorities[:3]:
        agenda.append(
            {
                "intent": "contrast",
                "analysis_key": "post_public_response_v1",
                "scope": "reviewed_comparable_peers",
                "context": {"role": "engagement"},
                "requested_use": "campaign_draft",
            }
        )
    agenda.append(
        {
            "intent": "temporal",
            "analysis_key": "temporal_broad_window_v1",
            "scope": "own_account",
            "context": {"phase": needs.get("phase")},
            "requested_use": "scheduling",
        }
    )
    if group in ("release", "growth"):
        agenda.append(
            {
                "intent": "cadence",
                "analysis_key": "interval_cadence_v1",
                "scope": "own_account",
                "context": {"metric_id": ctx.get("primary_metric_id")},
                "requested_use": "campaign_draft",
            }
        )
    return agenda
