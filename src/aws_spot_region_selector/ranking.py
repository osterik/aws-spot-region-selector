from __future__ import annotations

from decimal import Decimal

from .models import Candidate


def _tie_key(candidate: Candidate):
    return (
        candidate.latency.median_ms if candidate.latency.median_ms is not None else float("inf"),
        -(candidate.placement_score if candidate.placement_score is not None else -1),
        candidate.prices.time_weighted_p95_price,
        candidate.region,
        candidate.availability_zone,
        candidate.instance_type,
    )


def rank_candidates(candidates: list[Candidate], tie_percent: float) -> list[Candidate]:
    by_price = sorted(
        candidates,
        key=lambda candidate: (
            candidate.estimated_compute_cost,
            candidate.region,
            candidate.availability_zone,
            candidate.instance_type,
        ),
    )
    tolerance = Decimal(str(tie_percent)) / Decimal("100")
    ranked = []
    index = 0
    while index < len(by_price):
        minimum = by_price[index].estimated_compute_cost
        limit = minimum * (Decimal("1") + tolerance)
        end = index + 1
        while end < len(by_price) and by_price[end].estimated_compute_cost <= limit:
            end += 1
        ranked.extend(sorted(by_price[index:end], key=_tie_key))
        index = end
    return ranked
