"""Synthetic Poisson fits for the three content specs. Not owner-data qualification."""
from django.test import TestCase

from intelligence.analysis import AnalysisResolver
from intelligence.registry import sync_analysis_specs
from intelligence.stats.bayes_fit import query_draws
from tests.helpers import bootstrap


def _rows(feature_builder, n=16):
    rows = []
    for i in range(n):
        high = i >= n // 2
        rows.append(
            {
                "peer_media_id": f"row-{i}",
                "peer_id": "a" if i % 2 == 0 else "b",
                "response": 14 if high else 2,
                "response_basis": "synthetic",
                "format": "video",
                "features": feature_builder(i, high),
            }
        )
    return rows


class ContentBayesTests(TestCase):
    def setUp(self):
        bootstrap()
        sync_analysis_specs()
        self.resolver = AnalysisResolver()
        self.ctx_base = {
            "dataset_hash": "synthetic-content-1",
            "cohort": {"fingerprint": "synthetic-cohort"},
            "policy_versions": {},
            "primary_metric_id": "public_like_count",
        }

    def test_owner_minimum_does_not_sample(self):
        from intelligence.models import AnalysisSpec
        from intelligence.stats.post_response import run

        spec = AnalysisSpec.objects.get(key="content_subject_purpose_v1")
        outcome = run(spec, {"intent": "fit"}, {"post_rows": _rows(lambda i, high: {"reviewed_purpose": 1.0 if high else 0.0}, n=4)})
        self.assertEqual(outcome["status"], "insufficient_data")
        self.assertFalse(outcome["sampler_invoked"])

    def test_one_fit_answers_two_queries(self):
        ctx = {
            **self.ctx_base,
            "post_rows": _rows(lambda i, high: {"mean_luminance": 0.85 if high else 0.15, "mean_saturation": 0.2 if i % 2 == 0 else 0.8}),
        }
        fit = self.resolver.resolve_or_queue(
            {
                "analysis_key": "palette_association_v1",
                "intent": "fit",
                "synthetic": True,
                "draws": 40,
                "tune": 40,
                "metric_id": "public_like_count",
            },
            ctx,
        )
        self.assertEqual(fit["status"], "exploratory", fit)
        self.assertTrue(fit["result"]["sampler_invoked"])
        self.assertIn("mean_luminance", fit["result"]["draws"])
        self.assertIn("mean_saturation", fit["result"]["draws"])
        self.assertFalse(fit["result"]["qualified_on_owner_data"])
        q1 = self.resolver.resolve_or_queue(
            {
                "analysis_key": "palette_association_v1",
                "intent": "query",
                "contrast": "mean_luminance",
                "fit_run_id": fit["run_id"],
                "metric_id": "public_like_count",
            },
            ctx,
        )
        q2 = self.resolver.resolve_or_queue(
            {
                "analysis_key": "palette_association_v1",
                "intent": "query",
                "contrast": "mean_saturation",
                "fit_run_id": fit["run_id"],
                "metric_id": "public_like_count",
            },
            ctx,
        )
        self.assertFalse(q1["result"]["sampler_invoked"])
        self.assertFalse(q2["result"]["sampler_invoked"])
        self.assertFalse(q1["result"]["refit"])
        self.assertNotEqual(q1["result"]["feature"], q2["result"]["feature"])
        self.assertGreater(q1["result"]["posterior_mean_log_response_ratio"], 0)
        direct = query_draws(fit["result"], "mean_luminance")
        self.assertEqual(direct["n_draws"], q1["result"]["n_draws"])
        self.assertEqual(fit["result"]["dataset"]["source"], "synthetic_supplied")
        holdout = _rows(
            lambda i, high: {"mean_luminance": 0.9 if high else 0.1, "mean_saturation": 0.3 if i % 2 == 0 else 0.7},
            n=8,
        )
        for i, row in enumerate(holdout):
            row["peer_media_id"] = f"hold-{i}"
        evaluation = self.resolver.resolve_or_queue(
            {
                "analysis_key": "palette_association_v1",
                "intent": "evaluate",
                "fit_run_id": fit["run_id"],
                "metric_id": "public_like_count",
            },
            {**ctx, "holdout_rows": holdout},
        )
        self.assertEqual(evaluation["status"], "exploratory", evaluation)
        self.assertFalse(evaluation["result"]["sampler_invoked"])
        self.assertFalse(evaluation["result"]["refit"])
        self.assertFalse(evaluation["result"]["qualified_on_owner_data"])
        self.assertIsInstance(evaluation["result"]["posterior_mean_loglik"], float)
        self.assertIsInstance(evaluation["result"]["baseline_mean_loglik"], float)
        self.assertEqual(evaluation["result"]["search_budget"]["contrasts_searched_after_fit"], 0)

    def test_dataset_builder_does_not_sample_without_owner_minimum(self):
        outcome = self.resolver.resolve_or_queue(
            {"analysis_key": "content_subject_purpose_v1", "intent": "fit", "metric_id": "public_like_count"},
            self.ctx_base,
        )
        self.assertEqual(outcome["status"], "insufficient_data")
        self.assertFalse(outcome["result"]["sampler_invoked"])
        self.assertEqual(outcome["result"]["dataset"]["source"], "peer-posts-v1")

    def test_purpose_and_opening_specs_sample(self):
        for key, feature in (
            ("content_subject_purpose_v1", "reviewed_purpose"),
            ("opening_text_association_v1", "visible_opening_text"),
        ):
            ctx = {**self.ctx_base, "post_rows": _rows(lambda i, high, feature=feature: {feature: 1.0 if high else 0.0})}
            fit = self.resolver.resolve_or_queue(
                {
                    "analysis_key": key,
                    "intent": "fit",
                    "synthetic": True,
                    "draws": 30,
                    "tune": 30,
                    "metric_id": "public_like_count",
                },
                ctx,
            )
            self.assertEqual(fit["status"], "exploratory", fit)
            self.assertTrue(fit["result"]["sampler_invoked"])
            query = self.resolver.resolve_or_queue(
                {
                    "analysis_key": key,
                    "intent": "query",
                    "contrast": feature,
                    "fit_run_id": fit["run_id"],
                    "metric_id": "public_like_count",
                },
                ctx,
            )
            self.assertFalse(query["result"]["refit"])
            self.assertGreater(query["result"]["posterior_mean_log_response_ratio"], 0)
            holdout = _rows(lambda i, high, feature=feature: {feature: 1.0 if high else 0.0}, n=8)
            for i, row in enumerate(holdout):
                row["peer_media_id"] = f"hold-{key}-{i}"
            evaluation = self.resolver.resolve_or_queue(
                {
                    "analysis_key": key,
                    "intent": "evaluate",
                    "fit_run_id": fit["run_id"],
                    "metric_id": "public_like_count",
                },
                {**ctx, "holdout_rows": holdout},
            )
            self.assertFalse(evaluation["result"]["sampler_invoked"])
            self.assertFalse(evaluation["result"]["qualified_on_owner_data"])
            self.assertIn(feature, evaluation["result"]["feature_set"])
