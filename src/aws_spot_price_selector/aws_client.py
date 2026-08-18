from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Iterable

from .errors import AwsAuthenticationError, SelectorError
from .models import PricePoint, RegionInfo


LOGGER = logging.getLogger(__name__)


class AwsClient:
    def __init__(self, profile: str | None, discovery_region: str):
        try:
            import boto3
            from botocore.config import Config as BotocoreConfig
        except ImportError as exc:
            raise SelectorError("boto3 is required; install the project dependencies") from exc
        try:
            self.session = boto3.Session(profile_name=profile)
            retry_config = BotocoreConfig(retries={"max_attempts": 7, "mode": "standard"})
            self.discovery = self.session.client(
                "ec2", region_name=discovery_region, config=retry_config
            )
            self.retry_config = retry_config
        except Exception as exc:
            self._raise_aws(exc)

    @staticmethod
    def _raise_aws(exc: Exception):
        name = exc.__class__.__name__
        if name in {
            "NoCredentialsError",
            "PartialCredentialsError",
            "ProfileNotFound",
            "CredentialRetrievalError",
        }:
            raise AwsAuthenticationError(f"AWS authentication failed: {exc}") from exc
        response = getattr(exc, "response", {})
        code = response.get("Error", {}).get("Code", "") if isinstance(response, dict) else ""
        if code in {"AuthFailure", "UnauthorizedOperation", "AccessDenied", "AccessDeniedException"}:
            raise AwsAuthenticationError(f"AWS authorization failed: {code}") from exc
        raise SelectorError(f"AWS request failed: {exc}") from exc

    def discover_regions(self, include_not_opted_in: bool = False) -> list[RegionInfo]:
        LOGGER.debug("Calling EC2 DescribeRegions (include_not_opted_in=%s)", include_not_opted_in)
        try:
            response = self.discovery.describe_regions(AllRegions=True)
        except Exception as exc:
            self._raise_aws(exc)
        regions = []
        for item in response.get("Regions", []):
            status = item.get("OptInStatus")
            if status == "not-opted-in" and not include_not_opted_in:
                continue
            regions.append(
                RegionInfo(
                    name=item["RegionName"],
                    endpoint=item.get("Endpoint"),
                    opt_in_status=status,
                )
            )
        return sorted(regions, key=lambda item: item.name)

    def _region_client(self, region: str):
        return self.session.client("ec2", region_name=region, config=self.retry_config)

    def spot_price_history(
        self,
        region: str,
        instance_types: list[str],
        product_descriptions: list[str],
        start: datetime,
        end: datetime,
    ) -> list[PricePoint]:
        LOGGER.debug("Requesting Spot price history in %s from %s to %s", region, start, end)
        client = self._region_client(region)
        request: dict[str, Any] = {
            "StartTime": start,
            "EndTime": end,
            "InstanceTypes": instance_types,
            "ProductDescriptions": product_descriptions,
        }
        points = []
        try:
            while True:
                response = client.describe_spot_price_history(**request)
                for item in response.get("SpotPriceHistory", []):
                    points.append(
                        PricePoint(
                            timestamp=item["Timestamp"],
                            price=Decimal(item["SpotPrice"]),
                            availability_zone=item["AvailabilityZone"],
                            instance_type=item["InstanceType"],
                            product_description=item["ProductDescription"],
                        )
                    )
                token = response.get("NextToken")
                if not token:
                    break
                request["NextToken"] = token
        except Exception as exc:
            self._raise_aws(exc)
        return points

    def placement_scores(self, instance_types: list[str], target_capacity: int) -> dict[str, int]:
        LOGGER.debug(
            "Requesting Spot Placement Scores for %s with target capacity %d",
            ",".join(instance_types),
            target_capacity,
        )
        scores: dict[str, int] = {}
        request: dict[str, Any] = {
            "InstanceTypes": instance_types,
            "TargetCapacity": target_capacity,
            "SingleAvailabilityZone": False,
            "MaxResults": 10,
        }
        try:
            while True:
                response = self.discovery.get_spot_placement_scores(**request)
                for item in response.get("SpotPlacementScores", []):
                    if "Region" in item:
                        scores[item["Region"]] = int(item["Score"])
                token = response.get("NextToken")
                if not token:
                    break
                request["NextToken"] = token
        except Exception as exc:
            self._raise_aws(exc)
        return scores
