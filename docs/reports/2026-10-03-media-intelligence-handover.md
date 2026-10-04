# Media intelligence handover

**Contract:** `temp/Socials_Manager_Media_Intelligence_Implementation_Plan.md`  
**Ledger:** `docs/execution/MEDIA-INTELLIGENCE-LEDGER.json`  
**Date:** 3 October 2026

This note separates verified software, local runs that are not yet qualified, and source or data gates. Optional OCR and speech adapters are the remaining unimplemented extractors. They are not required for the owner-image path below.

## 1. Mappings

| Responsibility | Code |
| --- | --- |
| Library, save, attach | `context/library.py`, `context/inspiration_services.py` |
| Capability | `context/media_capability.py` (`purpose_state`, `resolve_media_capability`) |
| Live Meta probe | `sources/meta_graph.py` `probe_media_fields` |
| Quotas and blobs | `context/media_config.py` (`media-compact-v1`), `context/media_storage.py` |
| Sampling and descriptors | `context/visual_descriptors.py` (`visual-descriptors-v1`) |
| Owner-created images | `context/owner_asset.py` `ingest_owner_image` |
| Features and review | `intelligence/content_registry.py`, `context/content_features.py` |
| Gemma | `intelligence/gemma_adapter.py` |
| CLIP | `intelligence/clip_adapter.py` |
| Dataset, fit, query, evaluation | `intelligence/peer_dataset.py`, `intelligence/stats/post_response.py`, `intelligence/stats/bayes_fit.py` |
| Request, retrieve, rank | `intelligence/inspiration_request.py`, `inspiration_retrieve.py`, `inspiration_rank.py` |

### Commands

| Command | Exit |
| --- | --- |
| `manage.py qualify_extraction` | 2 until a reviewed corpus exists |
| `manage.py qualify_retrieval` | 2 until graded briefs exist; the report names the CLIP adapter state and does not say `embedding_pending` |
| `manage.py qualify_statistics` | descriptive summary for the older post spec; content specs use the resolver intents below |

## 2. Local models

Installed in `.venv`, not in the hash-pinned `requirements.txt`:

- `mlx-vlm==0.7.4` with `mlx-community/gemma-4-e2b-it-4bit` (Gemma 4 E2B, 3.55 GB weights).
- `open-clip-torch==3.3.0`, `torch==2.14.1`, CLIP `ViT-B-32` / `openai`, 512 dimensions.
- `pymc==6.3.2`.

Gemma must be called through its chat template with `num_images=1`. A raw prompt does not insert image tokens. On this machine the chat-template path described a red rectangle labelled RED and a blue rectangle labelled BLUE. Peak memory was about 4.25 GB. Those sentences are a smoke test, not a qualified field model.

CLIP retrieval is in `tests/test_clip_retrieval.py`. An unavailable import is reported as `embedding_unavailable` plus the exception.

## 3. Content specifications

`content_subject_purpose_v1`, `opening_text_association_v1`, and `palette_association_v1` use the `post_response` family.

| Intent | Behaviour |
| --- | --- |
| `fit` | Builds rows with `observation_frame`. Owner data comes from `build_peer_post_dataset`. Below 50 posts the sampler is not called. `synthetic: true` fits a Poisson log-link and stores coefficient and intercept draws. |
| `query` | Reads one stored coefficient. `sampler_invoked` and `refit` are false. |
| `evaluate` | Scores stored draws on `holdout_rows` against an intercept baseline. It does not sample and does not set `qualified_on_owner_data`. |

`tests/test_content_bayes.py` covers the owner-minimum gate, one palette fit answering two queries, and evaluation for all three specs. Real-data qualification stays blocked until the corpus and holdout gates in the ledger are met.

## 4. Browser navigation

`tests/test_browser.py::Browser.test_t16_reference_navigation_preserves_edits` passed at 360×640. It checks Inspiration overflow, focus, dialog scroll, Back from a reference to Find examples and then to the activity, and an unsaved note that is still present.

## 5. Meta source-use, 3 October 2026

`probe_media_fields` against the configured account:

- Instagram Login lists own media for @opalseason_ (`MEDIA_CREATOR`). The sampled item is a `CAROUSEL_ALBUM` with `id`, `media_type`, `media_url`, `permalink`, and `caption`. `thumbnail_url` was absent. No URL was stored.
- `META_ACCESS_TOKEN` failed with OAuth code 190: the session expired Friday, 02-Oct-26 12:00:00 PDT.
- Business Discovery for a stored peer username is `blocked` because the route is `instagram_login_basic`.
- Stored purposes: `collect`, `store`, `display`, `descriptive_derive`, and `export` are `unresolved` (treated as unknown). `statistical_fit`, `model_infer`, and `llm_ingest` are `denied`.

Owner-created local images were processed without that policy. Instagram bytes were not sent to Gemma or CLIP.

## 6. Connected owner-image path

`tests/test_owner_asset_workflow.py` creates two local PNGs, stores them, measures luminance and saturation, stores CLIP vectors, accepts a caption-supported `teaser` purpose, retrieves the red image first for “a red square”, recommends it at tier 1, and attaches it to an activity. The peer role is `reference_only`, so the image is not an analysis-cohort row and no public likes were invented.

## 7. Owner actions

1. Renew a Page-linked `META_ACCESS_TOKEN` if peer discovery or peer video is required, then call `probe_media_fields` with the peer username.
2. Set Instagram purposes to `allowed` before caching, embedding, or inference on Instagram media. A working `media_url` is not that permission.
3. Review at least 50 diverse posts, with ten positive and ten negative examples per field, before treating Gemma labels as qualified.
4. Grade 30–50 activity briefs before changing `inspiration-rank-v1` weights.
5. Reach 50 posts from five artists, or 30 own posts, with reviewed features and 7-day public-like snapshots before requesting an owner-data content finding. The fit can run after that; qualification still needs the evaluation gates.
