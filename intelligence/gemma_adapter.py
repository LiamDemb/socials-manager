"""Local Gemma extraction. Unqualified until a reviewed corpus exists."""
import time

CANDIDATE_ID = "google/gemma-4-E2B-it"
RUNTIME_ID = "mlx-community/gemma-4-e2b-it-4bit"
RUNTIME = "mlx-vlm"


def status() -> dict:
    try:
        import mlx_vlm  # noqa: F401
    except Exception as exc:
        return {
            "state": "unavailable",
            "candidate": CANDIDATE_ID,
            "runtime_id": RUNTIME_ID,
            "reason": f"{type(exc).__name__}: {exc}",
            "qualified": False,
        }
    return {
        "state": "importable",
        "candidate": CANDIDATE_ID,
        "runtime_id": RUNTIME_ID,
        "runtime": RUNTIME,
        "qualified": False,
        "reason": "Weights load on the first extraction call. Outputs are proposals, not qualified labels.",
    }


def extract_image(image_path: str, prompt: str) -> dict:
    report = status()
    if report["state"] != "importable":
        return {**report, "text": ""}
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config

    started = time.perf_counter()
    model, processor = load(RUNTIME_ID)
    config = load_config(RUNTIME_ID)
    formatted = apply_chat_template(processor, config, prompt, num_images=1)
    result = generate(model, processor, formatted, image=image_path, max_tokens=80, temperature=0)
    text = (getattr(result, "text", None) or "").strip()
    return {
        "state": "ran",
        "qualified": False,
        "candidate": CANDIDATE_ID,
        "runtime_id": RUNTIME_ID,
        "text": text,
        "prompt_tokens": getattr(result, "prompt_tokens", None),
        "generation_tokens": getattr(result, "generation_tokens", None),
        "peak_memory_gb": getattr(result, "peak_memory", None),
        "elapsed_s": round(time.perf_counter() - started, 2),
        "finish_reason": getattr(result, "finish_reason", None),
        "reason": "Single-image smoke on an owner-created file. Not a qualified field model.",
    }
