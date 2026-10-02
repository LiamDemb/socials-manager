"""AC30 early evaluation ledger. Synthetic fixtures only; the real Spotify gate must report Blocked/Insufficient data."""
import unittest
from datetime import date, timedelta

from django.test import TestCase

from core import clock
from core.errors import DomainError, PolicyDenied
from evaluation import baselines, synthetic
from evaluation.models import ForecastRecord
from evaluation.services import (
    as_of_series,
    evaluate_development,
    freeze_manifest,
    gate_report,
    open_holdout,
    record_prospective,
    score_prospective,
    utc_midnight,
)

from .helpers import bootstrap, import_file, real_fixture, recording_csv, utc

METRIC = "spotify.artist.streams.v1"
CRITERIA = {"max_mae_ratio_vs_best_baseline": 0.9, "note": "Synthetic mechanics test"}


class AsOfMechanics(TestCase):
    def setUp(self):
        bootstrap()
        self.entity = synthetic.synthetic_entity()

    def test_as_of_excludes_later_availability_and_revisions(self):
        d = date(2026, 6, 1)
        synthetic.deliver(self.entity, METRIC, [(d, 10)], utc(2026, 6, 2, 6))
        synthetic.deliver(self.entity, METRIC, [(d, 12)], utc(2026, 6, 10, 6), revision_reason="restated")
        self.assertEqual(as_of_series(self.entity, METRIC, utc(2026, 6, 1, 23), "statistical_fit"), [])
        self.assertEqual([v for _, v, _ in as_of_series(self.entity, METRIC, utc(2026, 6, 5), "statistical_fit")], [10])
        self.assertEqual([v for _, v, _ in as_of_series(self.entity, METRIC, utc(2026, 6, 11), "statistical_fit")], [12])

    def test_full_rolling_evaluation_and_single_holdout(self):
        start = date(2026, 1, 1)
        series = synthetic.generate_series(start, 200)
        synthetic.deliver_daily(self.entity, METRIC, series)
        cutoff = utc_midnight(start + timedelta(days=201))
        gates = gate_report(self.entity, METRIC)
        self.assertEqual(gates["policy"]["status"], "Passed")
        self.assertEqual(gates["history"]["status"], "Passed")
        manifest = freeze_manifest(self.entity, METRIC, cutoff, CRITERIA)
        self.assertEqual(manifest.fixture_class, "synthetic")
        holdout_start = date.fromisoformat(manifest.splits["holdout"]["start"])
        self.assertTrue(all(date.fromisoformat(o) + timedelta(days=7) <= holdout_start for o in manifest.splits["development_origins"]))
        run = evaluate_development(manifest)
        for ref in ("recent_mean_7", "seasonal_naive_7"):
            self.assertGreaterEqual(run.report[ref]["n"], 4)
            self.assertIsNotNone(run.report[ref]["mae"])
        open_holdout(manifest, "seasonal_naive_7")
        with self.assertRaises(DomainError) as err:
            open_holdout(manifest, "recent_mean_7")
        self.assertEqual(err.exception.code, "holdout_used")

    def test_manifest_requires_predeclared_criteria(self):
        synthetic.deliver_daily(self.entity, METRIC, synthetic.generate_series(date(2026, 1, 1), 200))
        with self.assertRaises(DomainError) as err:
            freeze_manifest(self.entity, METRIC, utc(2026, 8, 1), {})
        self.assertEqual(err.exception.code, "criteria_required")

    def test_prospective_ledger_saved_before_outcome_then_scored(self):
        start = date(2026, 1, 1)
        synthetic.deliver_daily(self.entity, METRIC, synthetic.generate_series(start, 30))
        with clock.frozen(utc(2026, 2, 1, 12)):
            with self.assertRaises(DomainError):
                record_prospective(self.entity, METRIC, "recent_mean_7", date(2026, 2, 1))
            rec = record_prospective(self.entity, METRIC, "recent_mean_7", date(2026, 2, 2))
        self.assertEqual(rec.state, "pending")
        future = synthetic.generate_series(date(2026, 2, 2), 7, seed=99)
        synthetic.deliver_daily(self.entity, METRIC, future)
        rec = score_prospective(ForecastRecord.objects.get(pk=rec.pk))
        self.assertEqual(rec.state, "scored")
        self.assertEqual(rec.actual["value"], sum(v for _, v in future))
        with clock.frozen(utc(2026, 1, 20)):
            with self.assertRaises(DomainError) as err:
                record_prospective(self.entity, METRIC, "recent_mean_7", date(2026, 1, 25))
        self.assertEqual(err.exception.code, "outcome_known")

    def test_baselines(self):
        hist = [(date(2026, 1, 1) + timedelta(days=i), i) for i in range(14)]
        self.assertEqual(baselines.predict("seasonal_naive_7", hist, 7), sum(range(7, 14)))
        self.assertEqual(baselines.predict("recent_mean_7", hist, 7), round(sum(range(7, 14)) / 7 * 7))
        self.assertEqual(baselines.score([])["mae"], None)


class SpotifyGate(TestCase):
    def test_spotify_fit_is_blocked_by_policy(self):
        bootstrap()
        from catalogue.services import create_object

        song = create_object("recording", "S")
        import_file(recording_csv([("2026-09-24", 50), ("2026-09-25", 60)]), "s.csv", recording=song)
        gates = gate_report(song.entity, "spotify.recording.streams.v1")
        self.assertEqual(gates["policy"]["status"], "Blocked")
        self.assertEqual(gates["history"]["status"], "Insufficient data")
        self.assertFalse(gates["fit_allowed"])
        with self.assertRaises(PolicyDenied):
            freeze_manifest(song.entity, "spotify.recording.streams.v1", utc(2026, 10, 1), CRITERIA)
        with self.assertRaises(PolicyDenied):
            as_of_series(song.entity, "spotify.recording.streams.v1", utc(2026, 10, 1), "statistical_fit")
        with clock.frozen(utc(2026, 10, 1)), self.assertRaises(PolicyDenied):
            record_prospective(song.entity, "spotify.recording.streams.v1", "recent_mean_7", date(2026, 10, 5))

    @unittest.skipUnless(real_fixture("better-man-streams.csv"), "Not run: real fixtures not configured")
    def test_real_five_active_days_are_insufficient(self):
        bootstrap()
        batch, _ = import_file(real_fixture("better-man-streams.csv"), "song.csv", new_recording_label="Real song")
        gates = gate_report(batch.mapped_entity, "spotify.recording.streams.v1")
        self.assertEqual(gates["history"]["status"], "Insufficient data")
        self.assertIn("5 active days of 1002", gates["history"]["detail"])
        self.assertEqual(gates["policy"]["status"], "Blocked")
