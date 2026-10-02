from core import clock

from .ask_retrieval import retrieve_for_question
from .llm_adapter import generate_structured
from .models import AskExchange
from .validation import sanitize_retrieved_text

LLM_FACT_LIMIT = 28


def _facts_for_llm(question: str, facts: list, limit: int = LLM_FACT_LIMIT) -> list:
    """Subset of facts for the model prompt (full set remains in basis)."""
    words = [w.lower() for w in question.split() if len(w) > 3]
    priority = {"instagram": 3, "identity": 3, "catalogue": 2, "observation": 2, "finding": 2}

    def score(fact):
        text = fact.get("text", "").lower()
        s = priority.get(fact.get("kind"), 0)
        if words and any(w in text for w in words):
            s += 4
        return s

    ranked = sorted(facts, key=score, reverse=True)
    return ranked[:limit]


def answer_question(question: str, scope: dict | None = None):
    """Answer from stored records. Persists the exchange only; does not change campaigns or sources."""
    scope = scope or {}
    safe_question = sanitize_retrieved_text(question, 2000)
    context = retrieve_for_question(safe_question, scope)
    resolver_notes = []
    if any(w in safe_question.lower() for w in ("better", "compare", "contrast")):
        resolver_notes.append("Ambiguous comparison may need clarification before analysis runs.")
    allowed = {f["evidence_id"] for f in context["facts"] + context.get("activities", [])}
    payload = {
        "question": safe_question,
        "instructions": (
            "Answer only from the supplied facts. Cite evidence_id values that appear in facts. "
            "If a fact is missing, say so in gaps. Do not propose creating or changing campaigns. "
            "Separate observed facts from interpretation."
        ),
        "facts": _facts_for_llm(safe_question, context["facts"] + context.get("activities", [])),
        "gaps": list(context["gaps"]) + resolver_notes,
        "facts_total": context["basis_count"],
        "truncated": context.get("truncated"),
    }
    llm = generate_structured("ask_answer", payload)
    data = llm.data or {}
    cited = []
    facts_out = []
    for fact in data.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        eid = str(fact.get("evidence_id") or "")
        if eid and eid not in allowed:
            continue
        facts_out.append(
            {
                "text": sanitize_retrieved_text(str(fact.get("text") or ""), 500),
                "evidence_id": eid,
                "source": fact.get("source") or "",
            }
        )
        if eid:
            cited.append(eid)
    basis = [
        {"evidence_id": f["evidence_id"], "source": f["source"], "kind": f["kind"], "text": f["text"]}
        for f in context["facts"]
        if not cited or f["evidence_id"] in cited
    ]
    if not basis:
        basis = context["facts"][:12]
    exchange = AskExchange.objects.create(
        question=safe_question,
        scope={**scope, "read_only": True},
        answer={
            "text": data.get("answer") or "",
            "facts": facts_out,
            "suggestions": data.get("suggestions") or [],
            "gaps": data.get("gaps") or context["gaps"],
            "interpretation": bool(data.get("interpretation")),
            "basis": basis,
            "basis_count": len(context["facts"]),
        },
        generation={"backend": llm.backend, "prompt_version": "ask-v2", "error": llm.error},
        created_at=clock.now(),
    )
    return exchange
