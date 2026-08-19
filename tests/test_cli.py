import logging

from aws_spot_price_selector.cli import apply_overrides, log_run_parameters, parser, run
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


def test_short_options_match_long_options():
    args = parser().parse_args(
        [
            "evaluate",
            "-c",
            "custom.yml",
            "-p",
            "production",
            "-i",
            "t4g.medium",
            "-P",
            "Linux/UNIX",
            "-r",
            "100",
            "-H",
            "14",
            "-t",
            "2.5",
            "-a",
            "10",
            "-o",
            "json",
            "-l",
            "debug",
            "-v",
        ]
    )

    assert args.config == "custom.yml"
    assert args.profile == "production"
    assert args.instance_types == "t4g.medium"
    assert args.product_descriptions == "Linux/UNIX"
    assert args.max_rtt_ms == 100
    assert args.history_days == 14
    assert args.duration_hours == 2.5
    assert args.alternatives == 10
    assert args.output == "json"
    assert args.log_level == "debug"
    assert args.verbose is True


def test_help_describes_every_option(capsys):
    try:
        parser().parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    help_text = capsys.readouterr().out
    for option in (
        "-h, --help",
        "-c, --config CONFIG",
        "-p, --profile PROFILE",
        "-i, --instance-types TYPES",
        "-P, --product-descriptions PRODUCTS",
        "-r, --max-rtt-ms MS",
        "-H, --history-days DAYS",
        "-t, --duration-hours HOURS",
        "-a, --alternatives COUNT",
        "-o, --output FORMAT",
        "-l, --log-level LEVEL",
        "-v, --verbose",
        "-V, --version",
    ):
        assert option in help_text


def test_effective_parameters_are_logged(caplog):
    config = Config()
    config.workload.product_descriptions = ["Linux/UNIX (Amazon VPC)"]

    with caplog.at_level(logging.INFO):
        log_run_parameters(config)

    assert "Effective run parameters" in caplog.text
    assert '"product_descriptions": [' in caplog.text
    assert '"Linux/UNIX (Amazon VPC)"' in caplog.text


def test_no_arguments_without_default_config_prints_help(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = run([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage: spot-region-selector" in captured.out
    assert "--config CONFIG" in captured.out
    assert captured.err == ""
