"""Deterministic labelled fallback when the local model is unavailable or output is invalid."""


def deterministic_response(task: str, payload: dict) -> dict:
    tactic = payload.get("tactic_id") or "ig_reel_teaser"
    evidence_ids = payload.get("evidence_ids") or []
    if task == "activity_brief":
        label = payload.get("object_label") or payload.get("campaign_name") or "this release"
        fmt = payload.get("format", "Reel")
        return {
            "brief": (
                f"Template fallback: plan a {fmt} for {label}. "
                f"Tactic {tactic}. {payload.get('support_reason', '')} "
                f"{payload.get('transfer_limits', '')}"
            ).strip(),
            "cta": payload.get("cta") or "Use your usual release CTA",
            "creative_note": "Template fallback (model unavailable or invalid JSON).",
            "evidence_ids": evidence_ids[:3],
            "interpretation": False,
        }
    if task == "ask_answer":
        facts = payload.get("facts") or []
        question = (payload.get("question") or "").lower()
        words = [w for w in question.split() if len(w) > 3]
        matched = [f for f in facts if words and any(w in f.get("text", "").lower() for w in words)]
        chosen = matched[:8] or facts[:8]
        if chosen:
            lines = "; ".join(f["text"] for f in chosen[:5])
            return {
                "answer": f"From stored records: {lines}",
                "facts": [{"text": f["text"], "evidence_id": f["evidence_id"], "source": f["source"]} for f in chosen],
                "suggestions": [],
                "gaps": payload.get("gaps") or [],
                "interpretation": False,
            }
        return {
            "answer": "No stored records matched this question.",
            "facts": [],
            "suggestions": [],
            "gaps": payload.get("gaps") or ["No stored records in Ask context."],
            "interpretation": False,
        }
    if task == "adaptation_summary":
        return {
            "summary": payload.get("trigger", "New data is available."),
            "reason": "Deterministic fallback summary.",
            "evidence_ids": evidence_ids[:5],
        }
    return {"note": "fallback", "task": task}
