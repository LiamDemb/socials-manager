"""Resident MLX model worker (single load per process)."""
import queue
import threading
import time
from dataclasses import dataclass

_holder = {"model": None, "tokenizer": None, "model_id": None, "error": ""}
_lock = threading.Lock()
_loaded = threading.Event()


def _load(model_id: str):
    with _lock:
        if _holder["model"] is not None and _holder["model_id"] == model_id:
            return
        try:
            from mlx_lm import load

            _holder["model"], _holder["tokenizer"] = load(model_id)
            _holder["model_id"] = model_id
            _holder["error"] = ""
            _loaded.set()
        except Exception as exc:
            _holder["error"] = str(exc)
            raise


def generate_text(model_id: str, messages: list[dict], max_tokens: int, temperature: float, timeout: float) -> tuple[str, str]:
    """Return (text, error)."""
    start = time.monotonic()
    result_q: queue.Queue = queue.Queue()

    def run():
        try:
            from mlx_lm import generate
            from mlx_lm.sample_utils import make_sampler

            _load(model_id)
            tokenizer = _holder["tokenizer"]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            text = generate(
                _holder["model"],
                tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=make_sampler(temp=temperature),
                verbose=False,
            )
            result_q.put((text, ""))
        except Exception as exc:
            result_q.put(("", str(exc)))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return "", "timeout"
    try:
        return result_q.get_nowait()
    except queue.Empty:
        return "", "timeout"


@dataclass
class WorkerHealth:
    importable: bool
    weights_configured: bool
    loaded: bool
    last_error: str


def worker_health(model_id: str | None) -> WorkerHealth:
    importable = False
    try:
        import mlx_lm  # noqa: F401

        importable = True
    except ImportError:
        pass
    loaded = _holder["model"] is not None and _holder["model_id"] == model_id
    return WorkerHealth(
        importable=importable,
        weights_configured=bool(model_id),
        loaded=loaded,
        last_error=_holder.get("error") or "",
    )
