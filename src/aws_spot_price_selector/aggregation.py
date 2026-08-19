from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import Candidate, RegionalSummary


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def summarize_regions(candidates: list[Candidate]) -> list[RegionalSummary]:
    grouped: dict[tuple[str, str, str], list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        key = (candidate.region, candidate.instance_type, candidate.product_description)
        grouped[key].append(candidate)

    summaries = []
    for (region, instance_type, product), group in grouped.items():
        average_latest = _mean([item.prices.latest_price for item in group])
        previous_prices = [item.prices.previous_price for item in group]
        if all(price is not None for price in previous_prices):
            average_previous = _mean([price for price in previous_prices if price is not None])
            delta = average_latest - average_previous
            percent = delta / average_previous * Decimal("100") if average_previous else None
            if delta > 0:
                direction, symbol = "up", "↑"
            elif delta < 0:
                direction, symbol = "down", "↓"
            else:
                direction, symbol = "flat", "→"
        else:
            delta = None
            percent = None
            direction, symbol = "unknown", "?"
        summaries.append(
            RegionalSummary(
                region=region,
                instance_type=instance_type,
                product_description=product,
                availability_zone_count=len(group),
                latency_median_ms=group[0].latency.median_ms,
                placement_score=group[0].placement_score,
                average_latest_price=average_latest,
                average_historical_price=_mean(
                    [item.prices.time_weighted_average_price for item in group]
                ),
                average_p95_price=_mean([item.prices.time_weighted_p95_price for item in group]),
                average_estimated_compute_cost=_mean(
                    [item.estimated_compute_cost for item in group]
                ),
                trend_direction=direction,
                trend_symbol=symbol,
                trend_absolute_change=delta,
                trend_percent_change=percent,
            )
        )
    return sorted(
        summaries,
        key=lambda item: (
            item.average_estimated_compute_cost,
            item.latency_median_ms if item.latency_median_ms is not None else float("inf"),
            item.region,
            item.instance_type,
            item.product_description,
        ),
    )
