# ADR 0003: Local LLM for Stage 3 synthesis and Ask

**Status:** Accepted (2 Oct 2026)  
**Verification date:** 2026-10-02

## Context

Stage 3 requires a local, licence-checked model for evidence-grounded synthesis, campaign briefs and Ask, without paid API dependency or Chinese-owned operators (AGENTS.md D11). Hardware: **Apple M1 Pro, 16 GB RAM**, macOS 15.7.4 arm64, ~183 GB free on data volume.

## Candidates considered

| Candidate | Steward / provenance | Licence | Verdict |
| --- | --- | --- | --- |
| **Meta Llama 3.2 3B Instruct (4-bit MLX)** | Meta Platforms (US); weights via Hugging Face `mlx-community` | Llama 3.2 Community License | **Selected** |
| Google Gemma 2 2B (MLX) | Google (US) | Gemma Terms of Use | Strong alternate; smaller context headroom for briefs |
| Mistral 7B Instruct (MLX) | Mistral AI (France) | Apache-2.0 | Heavier on 16 GB unified memory |
| Qwen / DeepSeek | Excluded operators | — | **Rejected** per project constraint |

## Decision

Use **mlx-lm** (Apple MLX, Apache-2.0) with **`mlx-community/Llama-3.2-3B-Instruct-4bit`**.

- **Model ID / quantisation:** `mlx-community/Llama-3.2-3B-Instruct-4bit` (4-bit, ~2 GB download)
- **Runtime:** Python package `mlx-lm` (optional install; not hash-pinned in core `requirements.txt`)
- **Weights location:** Hugging Face cache / owner data root `models/manifest.json` (outside Git)
- **Context budget:** 4096 tokens configured in manifest; prompts are JSON-bounded
- **Generation:** temperature 0.2, max_tokens 1024 (low variance, not claimed deterministic)

## Integration

- Adapter: `intelligence/llm_adapter.py` — timeout, threading, no cloud fallback
- Fallback: `intelligence/fallback.py` — labelled deterministic templates when MLX missing, disabled, timeout or invalid JSON
- Disable switch: `SOCIALS_MANAGER_LLM_DISABLED=1`
- Qualification: `python manage.py qualify_llm` (smoke structured `activity_brief`)

## Measured qualification (this machine)

With MLX **not installed** in the default venv (core install unchanged): qualification uses **deterministic_fallback**, smoke **passed** (brief present). After optional `pip install mlx-lm` and first model download, re-run `qualify_llm` to record MLX latency in `DATA_ROOT/models/manifest.json`.

## Limitations

- Spotify-derived data: purpose checks use latest stored `SourcePolicyVersion` per provider (`sources/eligibility.py`)
- No fine-tuning; learning is via reviewed findings/experiments in SQLite
- Prompt injection from captions filtered in `validation.sanitize_retrieved_text`; citations validated server-side

## Upgrade / rollback

1. Update `model_id` in `models/manifest.json` and re-run `qualify_llm`
2. Roll back: set `SOCIALS_MANAGER_LLM_DISABLED=1` or remove `mlx-lm`; app continues on deterministic fallback

## References

- [Llama 3.2 model card](https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_2/)
- [MLX LM documentation](https://github.com/ml-explore/mlx-examples/tree/main/llms/mlx_lm)
- [Hugging Face mlx-community/Llama-3.2-3B-Instruct-4bit](https://huggingface.co/mlx-community/Llama-3.2-3B-Instruct-4bit)
