from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from aws_spot_price_selector.models import Candidate, LatencyResult, PricePoint
from aws_spot_price_selector.pricing import calculate_price_stats
from aws_spot_price_selector.ranking import rank_candidates


def candidate(region, latency, price):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    stats = calculate_price_stats(
        [PricePoint(start, Decimal(price), region + "a", "t4g.medium", "Linux/UNIX")],
        start,
        end,
    )
    return Candidate(
        region,
        region + "a",
        "t4g.medium",
        "Linux/UNIX",
        LatencyResult(region, latency, latency, 7, 7, "eligible"),
        stats,
        Decimal("1"),
        8,
    )


class RankingTests(unittest.TestCase):
    def test_price_wins_outside_tolerance(self):
        cheap = candidate("eu-west-1", 70, "1")
        fast = candidate("eu-central-1", 20, "2")
        self.assertIs(rank_candidates([fast, cheap], 1)[0], cheap)

    def test_latency_breaks_price_tie(self):
        slow = candidate("eu-west-1", 70, "1")
        fast = candidate("eu-central-1", 20, "1.005")
        self.assertIs(rank_candidates([slow, fast], 1)[0], fast)


if __name__ == "__main__":
    unittest.main()
