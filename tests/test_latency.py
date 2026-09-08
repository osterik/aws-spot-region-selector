from unittest.mock import patch

from aws_spot_region_selector.config import LatencyConfig
from aws_spot_region_selector.latency import measure_region
from aws_spot_region_selector.models import RegionInfo


@patch("aws_spot_region_selector.latency._attempt")
def test_three_warmups_are_excluded_from_five_measurements(attempt):
    attempt.side_effect = [1000, 1000, 1000, 10, 20, 30, 40, 50]
    config = LatencyConfig(max_rtt_ms=100)

    result = measure_region(RegionInfo("eu-west-1"), config)

    assert attempt.call_count == 8
    assert result.attempts == 5
    assert result.successes == 5
    assert result.median_ms == 30
    assert result.p95_ms == 50
    assert result.status == "eligible"


@patch("aws_spot_region_selector.latency._attempt")
def test_rtt_equal_to_limit_is_eligible(attempt):
    attempt.side_effect = [80, 100, 120]
    config = LatencyConfig(
        max_rtt_ms=100,
        warmup_attempts=0,
        attempts=3,
        metric="median",
    )

    result = measure_region(RegionInfo("eu-west-1"), config)

    assert result.median_ms == 100
    assert result.status == "eligible"


@patch("aws_spot_region_selector.latency._attempt")
def test_insufficient_successful_requests_report_latency_unavailable(attempt):
    attempt.side_effect = [TimeoutError(), TimeoutError(), 20, OSError(), 30]
    config = LatencyConfig(warmup_attempts=0, attempts=5)

    result = measure_region(RegionInfo("eu-west-1"), config)

    assert result.status == "latency_unavailable"
    assert result.successes == 2
    assert result.error == "OSError, TimeoutError"
