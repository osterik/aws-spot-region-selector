from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aws_spot_region_selector.aggregation import summarize_regions
from aws_spot_region_selector.models import Candidate, LatencyResult, PricePoint
from aws_spot_region_selector.pricing import calculate_price_stats


def make_candidate(az: str, previous: str, latest: str) -> Candidate:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    stats = calculate_price_stats(
        [
            PricePoint(start, Decimal(previous), az, "t4g.medium", "Linux/UNIX"),
            PricePoint(
                start + timedelta(hours=1),
                Decimal(latest),
                az,
                "t4g.medium",
                "Linux/UNIX",
            ),
        ],
        start,
        end,
    )
    return Candidate(
        region="eu-west-1",
        availability_zone=az,
        instance_type="t4g.medium",
        product_description="Linux/UNIX",
        latency=LatencyResult("eu-west-1", 20, 25, 7, 7, "eligible"),
        prices=stats,
        duration_hours=Decimal("1"),
        placement_score=8,
    )


def test_regional_summary_averages_availability_zones():
    summaries = summarize_regions(
        [
            make_candidate("eu-west-1a", "1", "2"),
            make_candidate("eu-west-1b", "3", "4"),
        ]
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.availability_zone_count == 2
    assert summary.average_latest_price == Decimal("3")
    assert summary.average_historical_price == Decimal("2.5")
    assert summary.average_p95_price == Decimal("3")
    assert summary.trend_direction == "up"
    assert summary.trend_absolute_change == Decimal("1")
    assert summary.trend_percent_change == Decimal("50")
