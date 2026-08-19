from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .aws_client import AwsClient
from .config import Config, load_config, validate_config
from .errors import SelectorError
from .logging_config import configure_logging
from .models import jsonable
from .output import render
from .pipeline import evaluate, latency_only

COMMANDS = {"evaluate", "latency", "list-regions", "validate-config"}
DEFAULT_CONFIG = "./config.yml"
LOGGER = logging.getLogger(__name__)


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)

        default = self._get_default_metavar_for_optional(action)
        arguments = self._format_args(action, default)
        options = [
            f"{option} {arguments}" if option.startswith("--") else option
            for option in action.option_strings
        ]
        return ", ".join(options)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="spot-region-selector",
        description=(
            "Выбирает AWS-регион для Spot-нагрузки по задержке, цене и Spot Placement Score."
        ),
        epilog=(
            "Примеры:\n"
            "  spot-region-selector evaluate\n"
            "  spot-region-selector latency -c ./config.yml\n"
            "  spot-region-selector evaluate -i t4g.medium,c7g.large -o json\n\n"
            "Параметры CLI переопределяют значения из файла конфигурации."
        ),
        formatter_class=HelpFormatter,
        add_help=False,
    )
    result._positionals.title = "команды"
    result._optionals.title = "опции"
    result.add_argument(
        "-h",
        "--help",
        action="help",
        help="показать эту справку и завершить работу",
    )
    result.add_argument(
        "command",
        nargs="?",
        choices=sorted(COMMANDS),
        help=(
            "режим работы: evaluate — полная оценка; latency — только RTT; "
            "list-regions — список регионов; validate-config — проверка конфигурации"
        ),
    )
    result.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        metavar="CONFIG",
        help="путь к файлу конфигурации, ./config.yml по умолчанию",
    )
    result.add_argument(
        "-p",
        "--profile",
        metavar="PROFILE",
        help="имя AWS-профиля; переопределяет aws.profile из конфигурации",
    )
    result.add_argument(
        "-i",
        "--instance-types",
        metavar="TYPES",
        help="типы EC2 через запятую, например t4g.medium,c7g.large",
    )
    result.add_argument(
        "-P",
        "--product-descriptions",
        metavar="PRODUCTS",
        help='описания продуктов Spot API через запятую, например "Linux/UNIX"',
    )
    result.add_argument(
        "-r",
        "--max-rtt-ms",
        type=float,
        metavar="MS",
        help="максимально допустимый RTT в миллисекундах",
    )
    result.add_argument(
        "-H",
        "--history-days",
        type=int,
        metavar="DAYS",
        help="глубина анализа Spot Price History в днях",
    )
    result.add_argument(
        "-t",
        "--duration-hours",
        type=float,
        metavar="HOURS",
        help="ожидаемая продолжительность нагрузки в часах",
    )
    result.add_argument(
        "-a",
        "--alternatives",
        type=int,
        metavar="COUNT",
        help="максимальное число альтернатив после основной рекомендации",
    )
    result.add_argument(
        "-o",
        "--output",
        choices=["table", "json"],
        metavar="FORMAT",
        help="формат итогового stdout: table или json",
    )
    result.add_argument(
        "-l",
        "--log-level",
        choices=["error", "warning", "info", "debug"],
        metavar="LEVEL",
        help="уровень сообщений в stderr: error, warning, info или debug",
    )
    result.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="включить подробные debug-сообщения; эквивалент --log-level debug",
    )
    result.add_argument(
        "-V",
        "--version",
        action="version",
        version=__version__,
        help="показать версию приложения и завершить работу",
    )
    return result


def apply_overrides(config: Config, args: argparse.Namespace) -> str:
    if args.profile is not None:
        config.aws.profile = args.profile
    if args.instance_types is not None:
        config.workload.instance_types = [
            item.strip() for item in args.instance_types.split(",") if item.strip()
        ]
    if args.product_descriptions is not None:
        config.workload.product_descriptions = [
            item.strip() for item in args.product_descriptions.split(",") if item.strip()
        ]
    if args.max_rtt_ms is not None:
        config.latency.max_rtt_ms = args.max_rtt_ms
    if args.history_days is not None:
        config.pricing.history_days = args.history_days
    if args.duration_hours is not None:
        config.workload.duration_hours = args.duration_hours
    if args.alternatives is not None:
        config.ranking.alternatives = args.alternatives
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


def log_run_parameters(config: Config) -> None:
    """Log the effective, validated configuration without AWS credentials."""
    safe_config = asdict(config)
    # The profile name is useful for diagnostics; credentials are never part of Config.
    LOGGER.info(
        "Effective run parameters:\n%s",
        json.dumps(jsonable(safe_config), ensure_ascii=False, indent=2, sort_keys=True),
    )


def run(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv
    argument_parser = parser()
    if not effective_argv and not Path(DEFAULT_CONFIG).is_file():
        argument_parser.print_help()
        return 0
    args = argument_parser.parse_args(effective_argv)
    configure_logging(args.log_level or "info")
    try:
        config = load_config(args.config)
        mode = apply_overrides(config, args)
        configure_logging(config.output.log_level)
        LOGGER.info("Configuration loaded; selected mode: %s", mode)
        log_run_parameters(config)
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
