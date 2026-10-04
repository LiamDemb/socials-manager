"""Versioned media-compact-v1 defaults (engineering policy, not statistical findings)."""
PROFILE_VERSION = "media-compact-v1"

QUOTAS = {
    "preview_analysis_bytes": 4_000_000_000,
    "playback_cache_bytes": 1_000_000_000,
    "transient_total_bytes": 512_000_000,
    "transient_per_input_bytes": 100_000_000,
}

LIMITS = {
    "decode_max_seconds": 120,
    "decode_max_pixels": 50_000_000,
    "cover_long_edge_px": 320,
    "cover_target_bytes": (30_000, 80_000),
    "cover_hard_cap_bytes": 120_000,
    "analysis_long_edge_px": 768,
    "analysis_target_bytes": (40_000, 180_000),
    "analysis_hard_cap_bytes": 250_000,
    "video_frames_default": 8,
    "video_frames_max": 12,
    "carousel_children_max": 8,
    "ocr_long_edge_px": 1536,
    "ocr_hard_cap_bytes": 500_000,
    "ocr_crops_max": 4,
    "audio_max_seconds": 30,
    "playback_max_seconds": 60,
    "playback_long_edge_px": 640,
    "playback_hard_cap_bytes": 5_000_000,
    "acquire_timeout_seconds": 120,
    "decode_timeout_seconds": 120,
    "inference_timeout_seconds": 180,
    "heavy_jobs_at_once": 1,
    "network_retries": 3,
}

DESCRIPTOR_VERSION = "visual-descriptors-v1"
SAMPLING_SCHEMA = "sampling-manifest-v1"
