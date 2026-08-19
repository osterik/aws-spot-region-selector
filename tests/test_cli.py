import logging

from aws_spot_price_selector.cli import apply_overrides, log_run_parameters, parser
from aws_spot_price_selector.config import Config


def test_product_description_and_alternatives_overrides():
    args = parser().parse_args(
        [
            "evaluate",
            "--product-descriptions",
            "Linux/UNIX (Amazon VPC)",
            "--alternatives",
            "1000",
        ]
    )
    config = Config()
    config.workload.instance_types = ["t4g.medium"]

    apply_overrides(config, args)

    assert config.workload.product_descriptions == ["Linux/UNIX (Amazon VPC)"]
    assert config.ranking.alternatives == 1000


def test_effective_parameters_are_logged(caplog):
    config = Config()
    config.workload.product_descriptions = ["Linux/UNIX (Amazon VPC)"]

    with caplog.at_level(logging.INFO):
        log_run_parameters(config)

    assert "Effective run parameters" in caplog.text
    assert '"product_descriptions": [' in caplog.text
    assert '"Linux/UNIX (Amazon VPC)"' in caplog.text
