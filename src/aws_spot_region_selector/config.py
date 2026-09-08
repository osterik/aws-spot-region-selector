from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError


@dataclass
class RunConfig:
    mode: str = "evaluate"


@dataclass
class AwsConfig:
    profile: str | None = None
    discovery_region: str = "us-east-1"
    include_opt_in_regions: bool = False


@dataclass
class WorkloadConfig:
    instance_types: list[str] = field(default_factory=list)
    product_descriptions: list[str] = field(default_factory=lambda: ["Linux/UNIX"])
    target_capacity: int = 1
    duration_hours: float = 1.0


@dataclass
class RegionsConfig:
    included_regions: list[str] = field(default_factory=lambda: ["*"])
    excluded_regions: list[str] = field(default_factory=list)


@dataclass
class LatencyConfig:
    max_rtt_ms: float = 100.0
    warmup_attempts: int = 3
    attempts: int = 5
    timeout_ms: int = 1500
    concurrency: int = 8
    metric: str = "median"
    probe: str = "https"


@dataclass
class PricingConfig:
    history_days: int = 7
    statistic: str = "time_weighted_average"
    currency: str = "USD"


@dataclass
class PlacementConfig:
    enabled: bool = True
    min_score: int = 6
    failure_policy: str = "warn"


@dataclass
class RankingConfig:
    price_tie_relative_percent: float = 1.0
    alternatives: int = 5


@dataclass
class OutputConfig:
    format: str = "table"
    explain_exclusions: bool = True
    verbose: bool = False
    log_level: str = "info"


@dataclass
class Config:
    version: int = 1
    run: RunConfig = field(default_factory=RunConfig)
    aws: AwsConfig = field(default_factory=AwsConfig)
    workload: WorkloadConfig = field(default_factory=WorkloadConfig)
    regions: RegionsConfig = field(default_factory=RegionsConfig)
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    placement: PlacementConfig = field(default_factory=PlacementConfig)
    ranking: RankingConfig = field(default_factory=RankingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


_SECTIONS = {
    "run": RunConfig,
    "aws": AwsConfig,
    "workload": WorkloadConfig,
    "regions": RegionsConfig,
    "latency": LatencyConfig,
    "pricing": PricingConfig,
    "placement": PlacementConfig,
    "ranking": RankingConfig,
    "output": OutputConfig,
}


def _section(name: str, cls: type, data: Any):
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"Section '{name}' must be a mapping")
    allowed = set(cls.__dataclass_fields__)
    unknown = set(data) - allowed
    if unknown:
        raise ConfigError(f"Unknown fields in '{name}': {', '.join(sorted(unknown))}")
    try:
        return cls(**data)
    except TypeError as exc:
        raise ConfigError(f"Invalid section '{name}': {exc}") from exc


def load_config(path: str | Path = "config.yaml") -> Config:
    try:
        import yaml
    except ImportError as exc:
        raise ConfigError("PyYAML is required; install the project dependencies") from exc

    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot read configuration '{config_path}': {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("Configuration root must be a mapping")
    unknown = set(raw) - ({"version"} | set(_SECTIONS))
    if unknown:
        raise ConfigError(f"Unknown top-level fields: {', '.join(sorted(unknown))}")
    if raw.get("version", 1) != 1:
        raise ConfigError("Only configuration version 1 is supported")
    config = Config(version=1)
    for name, cls in _SECTIONS.items():
        setattr(config, name, _section(name, cls, raw.get(name)))
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if config.run.mode not in {"evaluate", "latency", "list-regions", "validate-config"}:
        raise ConfigError("run.mode must be evaluate, latency, list-regions, or validate-config")
    included_patterns = _validate_region_patterns(config.regions.included_regions, "included")
    excluded_patterns = _validate_region_patterns(config.regions.excluded_regions, "excluded")
    config.regions.included_regions = list(dict.fromkeys(included_patterns))
    config.regions.excluded_regions = list(dict.fromkeys(excluded_patterns))
    if not config.regions.included_regions:
        raise ConfigError("At least one included region pattern is required")
    if (
        config.latency.warmup_attempts < 0
        or config.latency.attempts < 1
        or config.latency.timeout_ms < 1
        or config.latency.concurrency < 1
    ):
        raise ConfigError(
            "latency warmup_attempts must be non-negative; attempts, timeout_ms, "
            "and concurrency must be positive"
        )
    if config.latency.max_rtt_ms < 0 or config.latency.metric not in {"median", "p95"}:
        raise ConfigError("Invalid latency threshold or metric")
    if config.latency.probe != "https":
        raise ConfigError("Only latency.probe=https is supported in version 1")
    if config.output.format not in {"table", "json"}:
        raise ConfigError("output.format must be table or json")
    config.output.log_level = str(config.output.log_level).lower()
    if config.output.log_level not in {"error", "warning", "info", "debug"}:
        raise ConfigError("output.log_level must be error, warning, info, or debug")
    if config.placement.failure_policy not in {"exclude", "warn", "ignore"}:
        raise ConfigError("placement.failure_policy must be exclude, warn, or ignore")
    if not 1 <= config.placement.min_score <= 10:
        raise ConfigError("placement.min_score must be between 1 and 10")
    if config.pricing.history_days < 1 or config.workload.duration_hours <= 0:
        raise ConfigError("history_days and duration_hours must be positive")
    if config.workload.target_capacity < 1:
        raise ConfigError("target_capacity must be positive")
    if config.ranking.price_tie_relative_percent < 0 or config.ranking.alternatives < 0:
        raise ConfigError("ranking values cannot be negative")
    if config.run.mode == "evaluate" and not config.workload.instance_types:
        raise ConfigError("workload.instance_types is required in evaluate mode")


def _validate_region_patterns(patterns: list[str], kind: str) -> list[str]:
    normalized_patterns = []
    for pattern in patterns:
        normalized = str(pattern).lower()
        if not normalized or any(char in normalized for char in "?[]{}"):
            raise ConfigError(f"Invalid {kind} region pattern: {pattern!r}")
        if not re.fullmatch(r"[a-z0-9*-]+", normalized):
            raise ConfigError(f"Invalid {kind} region pattern: {pattern!r}")
        normalized_patterns.append(normalized)
    return normalized_patterns


def included_by(region: str, config: RegionsConfig) -> list[str]:
    from fnmatch import fnmatchcase

    normalized = region.lower()
    matches = []
    for pattern in config.included_regions:
        if fnmatchcase(normalized, pattern):
            matches.append(f"pattern:{pattern}")
    return matches


def excluded_by(region: str, config: RegionsConfig) -> list[str]:
    from fnmatch import fnmatchcase

    normalized = region.lower()
    reasons = []
    for pattern in config.excluded_regions:
        if fnmatchcase(normalized, pattern):
            reasons.append(f"pattern:{pattern}")
    return reasons
