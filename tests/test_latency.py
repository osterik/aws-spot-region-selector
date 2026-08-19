from unittest.mock import patch

from aws_spot_price_selector.config import LatencyConfig
from aws_spot_price_selector.latency import measure_region
from aws_spot_price_selector.models import RegionInfo


@patch("aws_spot_price_selector.latency._attempt")
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
