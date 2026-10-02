"""AC07 metric algebra and coverage. Pure rules, frozen dates."""
from datetime import date, timedelta

from django.test import SimpleTestCase

from campaigns.measurement import aggregate, compute, net_tickets, ratio

D = date(2026, 10, 1)


def pts(values, start=D):
    return [(start + timedelta(days=i), v, f"v{i}") for i, v in enumerate(values) if v is not None]


class FlowTotals(SimpleTestCase):
    def test_sum_within_window_and_partial_coverage(self):
        p = compute("flow", "total", 100, D, D + timedelta(days=10), D + timedelta(days=5), pts([10, 10, None, 10, 10]))
        self.assertEqual(p.value, 40)
        self.assertEqual(p.status, "partial", "Gap inside the window")
        self.assertEqual(p.missing_days, [D + timedelta(days=2)])

    def test_trailing_delay_is_in_progress(self):
        p = compute("flow", "total", 100, D, D + timedelta(days=10), D + timedelta(days=4), pts([10, 10, 10]))
        self.assertEqual(p.status, "in_progress")
        self.assertAlmostEqual(p.pace_guide, 40.0)

    def test_window_ended_with_gap_is_not_failure(self):
        p = compute("flow", "total", 100, D, D + timedelta(days=3), D + timedelta(days=10), pts([1, None, 1]))
        self.assertEqual(p.status, "partial")

    def test_complete_window_not_met(self):
        p = compute("flow", "total", 100, D, D + timedelta(days=3), D + timedelta(days=10), pts([1, 0, 1]))
        self.assertEqual((p.status, p.value), ("not_met", 2))

    def test_zero_is_observed_value_and_no_data_is_unknown(self):
        self.assertEqual(compute("flow", "total", 5, D, D + timedelta(days=2), D + timedelta(days=2), pts([0, 0])).value, 0)
        p = compute("flow", "total", 5, D, D + timedelta(days=2), D + timedelta(days=2), [])
        self.assertEqual((p.status, p.value), ("unknown", None))

    def test_met_early(self):
        self.assertEqual(compute("flow", "total", 15, D, D + timedelta(days=10), D + timedelta(days=3), pts([10, 10])).status, "met")


class Stocks(SimpleTestCase):
    def test_gain_needs_baseline(self):
        p = compute("stock", "gain", 100, D, D + timedelta(days=30), D + timedelta(days=5), pts([22, 25], start=D + timedelta(days=1)))
        self.assertEqual((p.status, p.value), ("unknown", None))

    def test_gain_from_compatible_baseline_not_sum(self):
        points = pts([20, 21, 23, 26], start=D - timedelta(days=1))
        p = compute("stock", "gain", 100, D, D + timedelta(days=30), D + timedelta(days=3), points)
        self.assertEqual((p.baseline, p.value, p.status), (20, 6, "in_progress"))

    def test_baseline_too_old(self):
        points = pts([20], start=D - timedelta(days=30)) + pts([30], start=D + timedelta(days=1))
        self.assertEqual(compute("stock", "gain", 5, D, D + timedelta(days=30), D + timedelta(days=3), points, baseline_max_gap_days=7).status, "unknown")

    def test_level_latest_snapshot(self):
        p = compute("rolling_stock", "level", 100, D, D + timedelta(days=5), D + timedelta(days=3), pts([90, 94, 93]))
        self.assertEqual(p.value, 93)

    def test_needs_source(self):
        self.assertEqual(compute("stock", "gain", 100, D, D + timedelta(days=5), D, [], has_source=False).status, "needs_source")

    def test_daily_unique_is_not_an_outcome(self):
        self.assertEqual(compute("daily_unique", "total", 5, D, D + timedelta(days=5), D + timedelta(days=2), pts([1, 2])).status, "unknown")


class Algebra(SimpleTestCase):
    def test_aggregation_by_kind(self):
        series = [(D, 3), (D + timedelta(days=1), 5)]
        self.assertEqual(aggregate("flow", series)[0], 8)
        self.assertEqual(aggregate("stock", series)[0], 5)
        self.assertEqual(aggregate("nested_stock", series)[0], 5)
        self.assertEqual(aggregate("daily_unique", series)[0], 5, "Daily unique counts are shown per day, never summed")
        self.assertEqual(aggregate("flow", []), (None, "none"))

    def test_ratio_undefined_not_zero(self):
        self.assertIsNone(ratio(5, 0))
        self.assertIsNone(ratio(None, 3))
        self.assertEqual(ratio(1, 4), 0.25)

    def test_cumulative_tickets_replace_and_net_refunds(self):
        snaps = [{"at": 1, "paid": 10, "refunded": 0}, {"at": 2, "paid": 30, "issued": 4, "refunded": 3}]
        self.assertEqual(net_tickets(snaps), 31, "Latest snapshot net of refunds; successive totals are not summed")
        self.assertIsNone(net_tickets([]))
