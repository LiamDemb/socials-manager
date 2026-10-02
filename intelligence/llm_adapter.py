"""Bounded local LLM adapter with explicit fallback. No cloud fallback."""
import json
import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass

from core.env import env_first

from .manifest import load_manifest

log = logging.getLogger(__name__)

PROMPT_VERSION = "synthesis-v1"


@dataclass
class LlmResult:
    ok: bool
    data: dict | None
    error: str = ""
    backend: str = "unavailable"
    latency_ms: int = 0
    raw: str = ""


def _mlx_available() -> bool:
    try:
        import mlx_lm  # noqa: F401

        return True
    except ImportError:
        return False


def health() -> dict:
    from .llm_worker import worker_health

    manifest = load_manifest()
    mlx = _mlx_available()
    disabled = env_first("SOCIALS_MANAGER_LLM_DISABLED") == "1"
    wh = worker_health(manifest.get("model_id"))
    state = "unavailable"
    if disabled:
        state = "disabled"
    elif mlx:
        state = "ready"
    return {
        "state": state,
        "backend": "mlx-lm" if mlx else "deterministic_fallback",
        "model_id": manifest.get("model_id"),
        "prompt_pack_version": PROMPT_VERSION,
        "cloud_fallback": False,
        "disabled": disabled,
        "worker_importable": wh.importable,
        "worker_loaded": wh.loaded,
        "worker_error": wh.last_error,
    }


def _run_mlx(
    max_tokens: int,
    temperature: float,
    timeout: float,
    *,
    prompt: str | None = None,
    messages: list[dict] | None = None,
) -> LlmResult:
    from .llm_worker import generate_text

    manifest = load_manifest()
    model_id = manifest.get("model_id")
    start = time.monotonic()
    if messages is None:
        messages = [{"role": "user", "content": prompt or ""}]
    text, err = generate_text(model_id, messages, max_tokens, temperature, timeout)
    latency = int((time.monotonic() - start) * 1000)
    if err:
        return LlmResult(False, None, error=err, backend="mlx-lm", latency_ms=latency)
    return LlmResult(True, None, backend="mlx-lm", latency_ms=latency, raw=text)


ASK_SYSTEM = (
    "You are Socials Manager Ask. Reply with exactly one JSON object and no other text. "
    "No markdown. Keys: answer (string), facts (array of objects with evidence_id and text), "
    "suggestions (array of strings), gaps (array of strings), interpretation (boolean). "
    "Use only evidence_id values from the supplied facts. Do not invent metrics."
)

BRIEF_SYSTEM = (
    "You are Socials Manager. Write one JSON object only. Do not echo the input. "
    "Keys: brief (string, mention object_label), cta (string), creative_note (string), "
    "evidence_ids (array of strings), interpretation (boolean). No markdown."
)


def _compact_ask_payload(payload: dict) -> dict:
    facts = []
    for fact in payload.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        facts.append(
            {
                "evidence_id": fact.get("evidence_id"),
                "text": str(fact.get("text") or "")[:100],
            }
        )
    gaps = payload.get("gaps") or []
    return {
        "question": payload.get("question"),
        "facts": facts,
        "gaps": gaps[:5],
        "facts_total": payload.get("facts_total"),
    }


def _salvage_ask_json(text: str) -> dict | None:
    """Best-effort recovery when the model truncates or malforms JSON."""
    match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not match:
        stripped = (text or "").strip()
        if stripped and "{" not in stripped and len(stripped) < 2000:
            return {
                "answer": stripped[:4000],
                "facts": [],
                "suggestions": [],
                "gaps": ["Model returned plain text instead of JSON."],
                "interpretation": False,
            }
        return None
    answer = match.group(1).replace("\\n", "\n").replace('\\"', '"')
    eids = re.findall(r'"evidence_id"\s*:\s*"([^"]+)"', text)[:5]
    facts = [{"evidence_id": eid, "text": ""} for eid in eids]
    gaps_note = "Model response was truncated or malformed; answer may be incomplete."
    return {
        "answer": answer[:4000],
        "facts": facts,
        "suggestions": [],
        "gaps": [gaps_note],
        "interpretation": False,
    }


def _salvage_brief_json(text: str) -> dict | None:
    match = re.search(r'"brief"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not match:
        return None
    brief = match.group(1).replace("\\n", "\n").replace('\\"', '"')
    return {
        "brief": brief[:10000],
        "cta": "",
        "creative_note": "",
        "evidence_ids": [],
        "interpretation": False,
    }


def _extract_json(text: str, prefer_keys: tuple[str, ...] = ("brief", "answer")) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty")
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    pos = 0
    while pos < len(text):
        start = text.find("{", pos)
        if start < 0:
            break
        try:
            data, end = decoder.raw_decode(text[start:])
            if isinstance(data, dict):
                candidates.append(data)
            pos = start + max(end, 1)
        except json.JSONDecodeError:
            pos = start + 1
    for key in prefer_keys:
        for data in reversed(candidates):
            if key in data:
                return data
    if candidates:
        return candidates[-1]
    raise ValueError("no json object")


def generate_structured(task: str, payload: dict, timeout: float = 90.0) -> LlmResult:
    """Generate JSON for a known task schema. Falls back to deterministic templates when MLX unavailable."""
    from .fallback import deterministic_response

    manifest = load_manifest()
    gen = manifest.get("generation") or {}
    temperature = float(gen.get("temperature", 0.2))
    max_tokens = int(gen.get("max_tokens", 1024))
    if task == "ask_answer":
        temperature = float(gen.get("temperature_ask", 0.1))
        max_tokens = int(gen.get("max_tokens_ask", 768))
    elif task == "activity_brief":
        temperature = float(gen.get("temperature_brief", 0.15))
        max_tokens = int(gen.get("max_tokens_brief", 512))
    h = health()
    if h["state"] != "ready":
        data = deterministic_response(task, payload)
        return LlmResult(True, data, backend="deterministic_fallback", latency_ms=0)

    messages = None
    prompt = None
    if task == "ask_answer":
        compact = _compact_ask_payload(payload)
        user_body = json.dumps(
            {"task": task, "prompt_version": PROMPT_VERSION, "input": compact},
            ensure_ascii=False,
        )
        messages = [
            {"role": "system", "content": ASK_SYSTEM},
            {"role": "user", "content": user_body},
        ]
    elif task == "activity_brief":
        messages = [
            {"role": "system", "content": BRIEF_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"prompt_version": PROMPT_VERSION, "brief_input": payload},
                    ensure_ascii=False,
                ),
            },
        ]
    else:
        prompt = json.dumps({"task": task, "prompt_version": PROMPT_VERSION, "input": payload}, ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": "You are Socials Manager. Reply with valid JSON only, no markdown.",
            },
            {"role": "user", "content": prompt},
        ]
    result = _run_mlx(max_tokens, temperature, timeout, messages=messages, prompt=prompt)
    if not result.ok:
        data = deterministic_response(task, payload)
        return LlmResult(True, data, backend="deterministic_fallback", latency_ms=result.latency_ms, error=result.error)
    try:
        parse_error = ""
        try:
            data = _extract_json(result.raw)
        except (json.JSONDecodeError, ValueError) as exc:
            if task == "ask_answer":
                salvaged = _salvage_ask_json(result.raw)
                if salvaged:
                    data = salvaged
                    parse_error = "partial_json"
                else:
                    raise exc
            elif task == "activity_brief":
                salvaged = _salvage_brief_json(result.raw)
                if salvaged:
                    data = salvaged
                    parse_error = "partial_json"
                else:
                    raise exc
            else:
                raise exc
        return LlmResult(
            True,
            data,
            backend="mlx-lm",
            latency_ms=result.latency_ms,
            raw=result.raw,
            error=parse_error,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("LLM JSON parse failed (%s): %s", exc, (result.raw or "")[:240])
        data = deterministic_response(task, payload)
        return LlmResult(True, data, backend="deterministic_fallback", latency_ms=result.latency_ms, error=str(exc))


def qualify_smoke() -> dict:
    """Run a minimal structured task for installation qualification."""
    sample = {
        "campaign_type": "audience_growth",
        "campaign_name": "Qualification smoke",
        "object_label": "Smoke object",
        "tactic_id": "ig_reel_teaser",
        "format": "Reel",
        "support_reason": "Smoke test",
    }
    result = generate_structured("activity_brief", sample, timeout=120.0)
    passed = (
        result.ok
        and result.backend == "mlx-lm"
        and isinstance(result.data, dict)
        and result.data.get("brief")
        and "Smoke object" in (result.data.get("brief") or "")
    )
    brief = (result.data or {}).get("brief") or ""
    return {
        "passed": bool(passed),
        "backend": result.backend,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "has_brief": bool(brief),
        "brief_preview": brief[:120],
    }
