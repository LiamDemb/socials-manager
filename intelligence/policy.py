from sources.eligibility import metric_allows_purpose


def metric_allows_llm(metric_id: str) -> bool:
    return metric_allows_purpose(metric_id, "llm_ingest")
