from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .config import Config, excluded_by, included_by
from .errors import NoCandidatesError
from .latency import measure_regions
from .models import Candidate, Exclusion, LatencyResult, RegionInfo
from .pricing import calculate_price_stats, group_price_points
from .ranking import rank_candidates

LOGGER = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    generated_at: datetime
    mode: str
    latencies: list[LatencyResult] = field(default_factory=list)
    recommendation: Candidate | None = None
    alternatives: list[Candidate] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def discover_and_filter(client, config: Config) -> tuple[list[RegionInfo], list[Exclusion]]:
    LOGGER.info("Discovering AWS regions available to the account")
    regions = client.discover_regions(config.aws.include_opt_in_regions)
    LOGGER.info("Discovered %d AWS regions", len(regions))
    included = []
    exclusions = []
    for region in regions:
        included_matches = included_by(region.name, config.regions)
        matches = excluded_by(region.name, config.regions)
        if matches:
            exclusions.append(Exclusion(region.name, "configured_exclusion", ", ".join(matches)))
        elif not included_matches:
            exclusions.append(Exclusion(region.name, "not_included", "no include rule matched"))
        else:
            included.append(region)
    LOGGER.info(
        "Region filters selected %d regions and excluded %d",
        len(included),
        len(exclusions),
    )
    return included, exclusions


def latency_only(client, config: Config, now: datetime | None = None) -> EvaluationResult:
    LOGGER.info("Starting latency-only evaluation")
    regions, exclusions = discover_and_filter(client, config)
    latencies = measure_regions(regions, config.latency)
    LOGGER.info("Latency-only evaluation completed")
    return EvaluationResult(
        generated_at=now or datetime.now(timezone.utc),
        mode="latency",
        latencies=latencies,
        exclusions=exclusions,
    )


def evaluate(client, config: Config, now: datetime | None = None) -> EvaluationResult:
    LOGGER.info("Starting full region evaluation")
    generated_at = now or datetime.now(timezone.utc)
    regions, exclusions = discover_and_filter(client, config)
    latencies = measure_regions(regions, config.latency)
    eligible_latency = {item.region: item for item in latencies if item.status == "eligible"}
    for item in latencies:
        if item.status != "eligible":
            exclusions.append(Exclusion(item.region, item.status, item.error or "RTT above limit"))
    if not eligible_latency:
        raise NoCandidatesError("No region passed the latency filter")

    scores: dict[str, int] = {}
    score_error: str | None = None
    if config.placement.enabled:
        LOGGER.info("Requesting Spot Placement Scores")
        try:
            scores = client.placement_scores(
                config.workload.instance_types, config.workload.target_capacity
            )
        except Exception as exc:
            if config.placement.failure_policy == "exclude":
                raise NoCandidatesError(f"Spot Placement Score unavailable: {exc}") from exc
            score_error = str(exc)
            LOGGER.warning("Spot Placement Score is unavailable: %s", score_error)

    start = generated_at - timedelta(days=config.pricing.history_days)
    candidates = []
    warnings = []
    if score_error and config.placement.failure_policy == "warn":
        warnings.append(f"Spot Placement Score unavailable: {score_error}")

    region_count = len(eligible_latency)
    for region_index, (region_name, latency) in enumerate(eligible_latency.items(), start=1):
        LOGGER.info(
            "Pricing progress: %d/%d, requesting Spot history for %s",
            region_index,
            region_count,
            region_name,
        )
        score = scores.get(region_name) if config.placement.enabled else None
        if score is not None and score < config.placement.min_score:
            exclusions.append(Exclusion(region_name, "placement_score_below_minimum", str(score)))
            continue
        if (
            config.placement.enabled
            and score is None
            and config.placement.failure_policy == "exclude"
        ):
            exclusions.append(Exclusion(region_name, "placement_score_unavailable", "no score"))
            continue
        try:
            points = client.spot_price_history(
                region_name,
                config.workload.instance_types,
                config.workload.product_descriptions,
                start,
                generated_at,
            )
        except Exception as exc:
            LOGGER.warning("Spot pricing unavailable for %s: %s", region_name, exc)
            exclusions.append(Exclusion(region_name, "pricing_unavailable", str(exc)))
            continue
        grouped = group_price_points(points)
        for (az, instance_type, product), group in grouped.items():
            stats = calculate_price_stats(group, start, generated_at)
            if stats is None:
                continue
            candidate_warnings = []
            if stats.incomplete_history:
                candidate_warnings.append("incomplete_price_history")
            if (
                config.placement.enabled
                and score is None
                and config.placement.failure_policy == "warn"
            ):
                candidate_warnings.append("placement_score_unavailable")
            candidates.append(
                Candidate(
                    region=region_name,
                    availability_zone=az,
                    instance_type=instance_type,
                    product_description=product,
                    latency=latency,
                    prices=stats,
                    duration_hours=Decimal(str(config.workload.duration_hours)),
                    placement_score=score,
                    warnings=candidate_warnings,
                )
            )
        if not grouped:
            exclusions.append(Exclusion(region_name, "price_unavailable", "no Spot history"))
    if not candidates:
        raise NoCandidatesError("No candidate has usable Spot pricing data")
    ranked = rank_candidates(candidates, config.ranking.price_tie_relative_percent)
    LOGGER.info(
        "Evaluation completed: %d candidates, recommended region %s",
        len(ranked),
        ranked[0].region,
    )
    return EvaluationResult(
        generated_at=generated_at,
        mode="evaluate",
        latencies=latencies,
        recommendation=ranked[0],
        alternatives=ranked[1 : 1 + config.ranking.alternatives],
        exclusions=exclusions,
        warnings=warnings,
    )
