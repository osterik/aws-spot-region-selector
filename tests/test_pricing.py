import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aws_spot_region_selector.models import PricePoint
from aws_spot_region_selector.pricing import calculate_price_stats

UTC = timezone.utc


def point(at, price):
    return PricePoint(at, Decimal(price), "eu-west-1a", "t4g.medium", "Linux/UNIX")


class PriceStatsTests(unittest.TestCase):
    def test_time_weighted_average_and_up_trend(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(hours=10)
        stats = calculate_price_stats(
            [point(start, "1"), point(start + timedelta(hours=9), "3")], start, end
        )
        self.assertEqual(stats.time_weighted_average_price, Decimal("1.2"))
        self.assertEqual(stats.latest_price, Decimal("3"))
        self.assertEqual(stats.trend.direction, "up")
        self.assertEqual(stats.trend.symbol, "↑")
        self.assertEqual(stats.trend.percent_change, Decimal("200"))

    def test_down_flat_and_unknown_trends(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(hours=2)
        down = calculate_price_stats(
            [point(start, "2"), point(start + timedelta(hours=1), "1")], start, end
        )
        self.assertEqual(down.trend.direction, "down")
        flat = calculate_price_stats(
            [point(start, "1"), point(start + timedelta(hours=1), "1")], start, end
        )
        self.assertEqual(flat.trend.direction, "flat")
        unknown = calculate_price_stats([point(start, "1")], start, end)
        self.assertEqual(unknown.trend.direction, "unknown")

    def test_incomplete_history(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(hours=10)
        stats = calculate_price_stats([point(start + timedelta(hours=5), "1")], start, end)
        self.assertTrue(stats.incomplete_history)
        self.assertEqual(stats.observed_seconds, 5 * 3600)

    def test_price_effective_before_window_covers_window_boundary(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(hours=4)

        stats = calculate_price_stats(
            [
                point(start - timedelta(hours=1), "1"),
                point(start + timedelta(hours=2), "3"),
            ],
            start,
            end,
        )

        self.assertEqual(stats.observed_seconds, 4 * 3600)
        self.assertEqual(stats.time_weighted_average_price, Decimal("2"))
        self.assertFalse(stats.incomplete_history)


if __name__ == "__main__":
    unittest.main()
