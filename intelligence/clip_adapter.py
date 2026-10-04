"""CLIP ViT-B/32 retrieval adapter. No remote inference."""
import math

ENCODER_ID = "ViT-B-32"
PRETRAINED = "openai"
DIMENSIONS = 512

_MODEL = None
_TOKENIZER = None


def status() -> dict:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
    except Exception as exc:
        return {
            "state": "unavailable",
            "encoder": ENCODER_ID,
            "pretrained": PRETRAINED,
            "reason": f"{type(exc).__name__}: {exc}",
            "owner_action": "Install open-clip-torch in this venv (Python 3.14, Apple Silicon). Do not use a CUDA wheel.",
        }
    return {
        "state": "importable",
        "encoder": ENCODER_ID,
        "pretrained": PRETRAINED,
        "dimensions": DIMENSIONS,
        "loaded": _MODEL is not None,
        "reason": "Weights load on the first encode call from the OpenAI CLIP checkpoint.",
    }


def _load():
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return _MODEL
    import open_clip
    import torch

    model, _, preprocess = open_clip.create_model_and_transforms(ENCODER_ID, pretrained=PRETRAINED)
    model.eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = model.to(device)
    _MODEL = (model, preprocess, device)
    _TOKENIZER = open_clip.get_tokenizer(ENCODER_ID)
    return _MODEL


def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def encode_text(text: str) -> dict:
    import torch

    model, _preprocess, device = _load()
    tokens = _TOKENIZER([text[:300]]).to(device)
    with torch.no_grad():
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    vec = _l2([float(v) for v in features[0].detach().cpu().tolist()])
    return {"encoder": ENCODER_ID, "dimensions": len(vec), "vector": vec, "query": text[:300]}


def encode_rgb(pixels: list[tuple[int, int, int]], width: int, height: int) -> dict:
    import torch
    from PIL import Image

    model, preprocess, device = _load()
    image = Image.new("RGB", (width, height))
    image.putdata([(int(r), int(g), int(b)) for r, g, b in pixels])
    batch = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        features = model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)
    vec = _l2([float(v) for v in features[0].detach().cpu().tolist()])
    if len(vec) != DIMENSIONS:
        raise ValueError(f"encoder_dimension_mismatch:{len(vec)}")
    if not all(math.isfinite(v) for v in vec):
        raise ValueError("non_finite_embedding")
    return {"encoder": ENCODER_ID, "dimensions": len(vec), "vector": vec}


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("incompatible_embedding_space")
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))


def rank_vectors(query: list[float], items: list[dict]) -> list[dict]:
    ranked = []
    for item in items:
        vec = item.get("vector")
        if not vec:
            continue
        ranked.append({**item, "cosine": cosine(query, vec)})
    ranked.sort(key=lambda row: (-row["cosine"], str(row.get("id"))))
    return ranked
