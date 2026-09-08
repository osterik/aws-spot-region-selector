from datetime import datetime, timezone

import boto3
from botocore.stub import Stubber

from aws_spot_region_selector.aws_client import AwsClient


class PaginatedSpotClient:
    def __init__(self):
        self.requests = []

    def describe_spot_price_history(self, **request):
        self.requests.append(request.copy())
        common = {
            "InstanceType": "t4g.medium",
            "ProductDescription": "Linux/UNIX",
            "AvailabilityZone": "eu-west-1a",
        }
        if "NextToken" not in request:
            return {
                "SpotPriceHistory": [
                    {
                        **common,
                        "Timestamp": datetime(2026, 8, 1, tzinfo=timezone.utc),
                        "SpotPrice": "0.0200",
                    }
                ],
                "NextToken": "page-2",
            }
        return {
            "SpotPriceHistory": [
                {
                    **common,
                    "Timestamp": datetime(2026, 8, 2, tzinfo=timezone.utc),
                    "SpotPrice": "0.0210",
                }
            ]
        }


class FakeSession:
    def __init__(self, client):
        self.client_instance = client

    def client(self, service, region_name, config):
        assert service == "ec2"
        assert region_name == "eu-west-1"
        return self.client_instance


def test_spot_price_history_follows_pagination():
    spot_client = PaginatedSpotClient()
    client = AwsClient.__new__(AwsClient)
    client.session = FakeSession(spot_client)
    client.retry_config = object()
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 3, tzinfo=timezone.utc)

    points = client.spot_price_history("eu-west-1", ["t4g.medium"], ["Linux/UNIX"], start, end)

    assert [str(point.price) for point in points] == ["0.0200", "0.0210"]
    assert len(spot_client.requests) == 2
    assert "NextToken" not in spot_client.requests[0]
    assert spot_client.requests[1]["NextToken"] == "page-2"


def test_region_discovery_uses_stubber_and_filters_not_opted_in():
    ec2 = boto3.client(
        "ec2",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    stubber = Stubber(ec2)
    stubber.add_response(
        "describe_regions",
        {
            "Regions": [
                {
                    "RegionName": "eu-west-1",
                    "Endpoint": "ec2.eu-west-1.amazonaws.com",
                    "OptInStatus": "opt-in-not-required",
                },
                {
                    "RegionName": "ap-southeast-5",
                    "Endpoint": "ec2.ap-southeast-5.amazonaws.com",
                    "OptInStatus": "not-opted-in",
                },
            ]
        },
        {"AllRegions": True},
    )
    client = AwsClient.__new__(AwsClient)
    client.discovery = ec2

    with stubber:
        regions = client.discover_regions(include_not_opted_in=False)

    assert [region.name for region in regions] == ["eu-west-1"]
