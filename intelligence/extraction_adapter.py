"""Local extraction adapters (M05). Deterministic path always available."""
import re
import time

ADAPTER_CAPTION = "deterministic-caption-v1"
GEMMA_CANDIDATE = "google/gemma-4-E2B-it"


def extract_labels(post, pack) -> dict:
    t0 = time.time()
    caption = (post.caption or "").lower()
    fields = []
    if "teaser" in caption or "snippet" in caption:
        fields.append(
            {
                "feature_key": "teaser",
                "value": True,
                "support": [{"kind": "caption_span", "text": "teaser"}],
            }
        )
    if "out now" in caption or "announce" in caption:
        fields.append(
            {
                "feature_key": "announcement",
                "value": True,
                "support": [{"kind": "caption_span"}],
            }
        )
    if re.search(r"\?", caption):
        fields.append(
            {
                "feature_key": "visible_opening_text",
                "value": True,
                "support": [{"kind": "caption_span", "note": "question in caption"}],
            }
        )
    from intelligence.gemma_adapter import status as gemma_status

    gemma = gemma_status()
    elapsed = int((time.time() - t0) * 1000)
    return {
        "adapter": ADAPTER_CAPTION,
        "model_revision": ADAPTER_CAPTION,
        "schema_version": "content-labels-v1",
        "status": "ready",
        "elapsed_ms": elapsed,
        "fields": fields,
        "output": {
            "unknown_fields": ["instrument_visible", "paid_status"],
            "multimodal": {
                "candidate": gemma.get("candidate") or GEMMA_CANDIDATE,
                "runtime_id": gemma.get("runtime_id"),
                "status": gemma.get("state"),
                "qualified": False,
                "reason": gemma.get("reason"),
            },
            "description": "Caption-derived proposals only; visual claims require qualified extraction.",
        },
    }
