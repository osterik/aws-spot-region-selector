from __future__ import annotations

import argparse
import logging

from . import __version__
from .aws_client import AwsClient
from .config import Config, load_config, validate_config
from .errors import SelectorError
from .logging_config import configure_logging
from .output import render
from .pipeline import evaluate, latency_only


COMMANDS = {"evaluate", "latency", "list-regions", "validate-config"}
LOGGER = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="spot-region-selector")
    result.add_argument("command", nargs="?", choices=sorted(COMMANDS))
    result.add_argument("--config", default="config.yml")
    result.add_argument("--profile")
    result.add_argument("--instance-types")
    result.add_argument("--max-rtt-ms", type=float)
    result.add_argument("--history-days", type=int)
    result.add_argument("--duration-hours", type=float)
    result.add_argument("--output", choices=["table", "json"])
    result.add_argument("--log-level", choices=["error", "warning", "info", "debug"])
    result.add_argument("--verbose", action="store_true", default=None)
    result.add_argument("--version", action="version", version=__version__)
    return result


def apply_overrides(config: Config, args: argparse.Namespace) -> str:
    if args.profile is not None:
        config.aws.profile = args.profile
    if args.instance_types is not None:
        config.workload.instance_types = [item.strip() for item in args.instance_types.split(",") if item.strip()]
    if args.max_rtt_ms is not None:
        config.latency.max_rtt_ms = args.max_rtt_ms
    if args.history_days is not None:
        config.pricing.history_days = args.history_days
    if args.duration_hours is not None:
        config.workload.duration_hours = args.duration_hours
    if args.output is not None:
        config.output.format = args.output
    if args.log_level is not None:
        config.output.log_level = args.log_level
    if args.verbose is not None:
        config.output.verbose = args.verbose
        if args.verbose and args.log_level is None:
            config.output.log_level = "debug"
    mode = args.command or config.run.mode
    config.run.mode = mode
    validate_config(config)
    return mode


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    configure_logging(args.log_level or "info")
    try:
        config = load_config(args.config)
        mode = apply_overrides(config, args)
        configure_logging(config.output.log_level)
        LOGGER.info("Configuration loaded; selected mode: %s", mode)
        if mode == "validate-config":
            LOGGER.info("Configuration validation completed")
            print(f"Configuration is valid: {args.config}")
            return 0
        LOGGER.info("Initializing AWS client")
        client = AwsClient(config.aws.profile, config.aws.discovery_region)
        if mode == "list-regions":
            from .config import excluded_by, included_by

            LOGGER.info("Discovering AWS regions available to the account")
            regions = client.discover_regions(config.aws.include_opt_in_regions)
            LOGGER.info("Discovered %d AWS regions", len(regions))
            for region in regions:
                reasons = excluded_by(region.name, config.regions)
                include_matches = included_by(region.name, config.regions)
                if reasons:
                    status = "excluded " + ",".join(reasons)
                elif include_matches:
                    status = "included " + ",".join(include_matches)
                else:
                    status = "not-included"
                print(f"{region.name}\t{status}")
            return 0
        result = latency_only(client, config) if mode == "latency" else evaluate(client, config)
        print(render(result, config))
        return 0
    except SelectorError as exc:
        LOGGER.error("%s", exc)
        return exc.exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
