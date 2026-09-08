import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from aws_spot_region_selector.config import Config
from aws_spot_region_selector.models import LatencyResult, PricePoint, RegionInfo
from aws_spot_region_selector.output import render_evaluation, render_json
from aws_spot_region_selector.pipeline import evaluate, latency_only


class FakeClient:
    def __init__(self):
        self.pricing_calls = 0
        self.placement_calls = 0

    def discover_regions(self, include_not_opted_in=False):
        return [RegionInfo("eu-west-1"), RegionInfo("us-east-1")]

    def spot_price_history(self, *args, **kwargs):
        self.pricing_calls += 1
        raise AssertionError("latency mode must not request pricing")

    def placement_scores(self, *args, **kwargs):
        self.placement_calls += 1
        raise AssertionError("latency mode must not request placement scores")


class EvaluationClient:
    def discover_regions(self, include_not_opted_in=False):
        return [RegionInfo("eu-central-1"), RegionInfo("eu-west-1"), RegionInfo("us-east-1")]

    def placement_scores(self, instance_types, target_capacity):
        return {"eu-central-1": 8, "eu-west-1": 8}

    def spot_price_history(self, region, instance_types, products, start, end):
        base = Decimal("0.020") if region == "eu-west-1" else Decimal("0.021")
        return [
            PricePoint(
                start, base + Decimal("0.002"), region + "a", instance_types[0], products[0]
            ),
            PricePoint(
                end - timedelta(hours=1), base, region + "a", instance_types[0], products[0]
            ),
        ]


class PartiallyFailingEvaluationClient(EvaluationClient):
    def spot_price_history(self, region, instance_types, products, start, end):
        if region == "eu-central-1":
            raise RuntimeError("simulated regional failure")
        return super().spot_price_history(region, instance_types, products, start, end)


class PlacementFailingEvaluationClient(EvaluationClient):
    def placement_scores(self, instance_types, target_capacity):
        raise RuntimeError("simulated placement failure")


class LatencyPipelineTests(unittest.TestCase):
    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_latency_mode_does_not_request_price_or_placement(self, measure):
        measure.return_value = [LatencyResult("eu-west-1", 20, 25, 7, 7, "eligible")]
        config = Config()
        config.run.mode = "latency"
        config.regions.excluded_regions = ["us-*"]
        client = FakeClient()

        result = latency_only(client, config)

        self.assertEqual(result.mode, "latency")
        self.assertEqual(client.pricing_calls, 0)
        self.assertEqual(client.placement_calls, 0)
        self.assertEqual([item.region for item in result.exclusions], ["us-east-1"])
        measured_regions = measure.call_args.args[0]
        self.assertEqual([item.name for item in measured_regions], ["eu-west-1"])

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_only_explicitly_included_regions_are_measured(self, measure):
        measure.return_value = [LatencyResult("eu-west-1", 20, 25, 7, 7, "eligible")]
        config = Config()
        config.run.mode = "latency"
        config.regions.included_regions = ["eu-*"]

        result = latency_only(FakeClient(), config)

        measured_regions = measure.call_args.args[0]
        self.assertEqual([item.name for item in measured_regions], ["eu-west-1"])
        self.assertEqual(result.exclusions[0].region, "us-east-1")
        self.assertEqual(result.exclusions[0].reason, "not_included")

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_rtt_exclusion_includes_measured_value(self, measure):
        measure.return_value = [
            LatencyResult("eu-central-1", 120.25, 145.75, 5, 5, "above_limit"),
            LatencyResult("eu-west-1", 40, 45, 5, 5, "eligible"),
        ]
        config = Config()
        config.workload.instance_types = ["t4g.medium"]
        config.regions.excluded_regions = ["us-*"]

        result = evaluate(EvaluationClient(), config)

        exclusion = next(item for item in result.exclusions if item.region == "eu-central-1")
        self.assertEqual(exclusion.reason, "above_limit")
        self.assertEqual(exclusion.detail, "RTT 120.2 ms above limit 100.0 ms (median)")
        self.assertIn(
            "eu-central-1: above_limit (RTT 120.2 ms above limit 100.0 ms (median))",
            render_evaluation(result, config),
        )

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_p95_rtt_exclusion_reports_selected_metric(self, measure):
        measure.return_value = [
            LatencyResult("eu-central-1", 80, 120.25, 5, 5, "above_limit"),
            LatencyResult("eu-west-1", 40, 45, 5, 5, "eligible"),
        ]
        config = Config()
        config.workload.instance_types = ["t4g.medium"]
        config.regions.excluded_regions = ["us-*"]
        config.latency.metric = "p95"

        result = evaluate(EvaluationClient(), config)

        exclusion = next(item for item in result.exclusions if item.region == "eu-central-1")
        self.assertEqual(exclusion.detail, "RTT 120.2 ms above limit 100.0 ms (p95)")

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_failure_in_one_region_preserves_other_results(self, measure):
        measure.return_value = [
            LatencyResult("eu-central-1", 20, 25, 5, 5, "eligible"),
            LatencyResult("eu-west-1", 40, 45, 5, 5, "eligible"),
        ]
        config = Config()
        config.workload.instance_types = ["t4g.medium"]
        config.regions.excluded_regions = ["us-*"]

        result = evaluate(PartiallyFailingEvaluationClient(), config)

        self.assertEqual(result.recommendation.region, "eu-west-1")
        exclusion = next(item for item in result.exclusions if item.region == "eu-central-1")
        self.assertEqual(exclusion.reason, "pricing_unavailable")

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_ignored_placement_failure_remains_in_json_diagnostics(self, measure):
        measure.return_value = [
            LatencyResult("eu-central-1", 20, 25, 5, 5, "eligible"),
            LatencyResult("eu-west-1", 40, 45, 5, 5, "eligible"),
        ]
        config = Config()
        config.workload.instance_types = ["t4g.medium"]
        config.regions.excluded_regions = ["us-*"]
        config.placement.failure_policy = "ignore"

        result = evaluate(PlacementFailingEvaluationClient(), config)
        payload = json.loads(render_json(result, config))

        self.assertEqual(
            payload["diagnostics"]["placement_score_error"],
            "simulated placement failure",
        )
        self.assertEqual(payload["warnings"], [])

    @patch("aws_spot_region_selector.pipeline.measure_regions")
    def test_full_evaluation_includes_latest_price_trend_and_json(self, measure):
        measure.return_value = [
            LatencyResult("eu-central-1", 20, 25, 7, 7, "eligible"),
            LatencyResult("eu-west-1", 40, 45, 7, 7, "eligible"),
        ]
        config = Config()
        config.workload.instance_types = ["t4g.medium"]
        config.regions.excluded_regions = ["us-*"]
        now = datetime(2026, 8, 18, tzinfo=timezone.utc)

        result = evaluate(EvaluationClient(), config, now=now)

        self.assertEqual(result.recommendation.region, "eu-west-1")
        self.assertEqual(result.recommendation.prices.latest_price, Decimal("0.020"))
        self.assertEqual(result.recommendation.prices.trend.symbol, "↓")
        self.assertEqual(len(result.regional_summaries), 2)
        rendered = render_json(result, config)
        payload = json.loads(rendered)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["mode"], "evaluate")
        self.assertEqual(payload["recommendation"]["prices"]["latest_price"], "0.020")
        self.assertEqual(payload["recommendation"]["prices"]["trend"]["direction"], "down")
        self.assertIsInstance(payload["alternatives"], list)
        self.assertIsInstance(payload["regional_summaries"], list)
        self.assertIsInstance(payload["latencies"], list)
        self.assertIsInstance(payload["excluded_regions"], list)
        self.assertIsInstance(payload["warnings"], list)
        self.assertEqual(payload["diagnostics"], {})
        self.assertEqual(payload["recommendation"]["availability_zone"], "eu-west-1a")
        table = render_evaluation(result, config)
        self.assertIn("Regional averages across Availability Zones:", table)
        self.assertIn("AVG_LATEST", table)
        self.assertIn("AVG_HIST", table)
        self.assertIn("AVG_EST", table)
        self.assertNotIn("AVG_HISTORY", table)
        self.assertNotIn("AVG_EST_COST", table)
        self.assertIn("$0.0200", table)
        self.assertRegex(table, r"(?m)^eu-west-1\s+a\s+t4g\.medium")
        self.assertIn("Recommended: eu-west-1 / a / t4g.medium", table)
        self.assertNotIn("eu-west-1a", table)


if __name__ == "__main__":
    unittest.main()
