from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from .models import PricePoint, PriceStats, PriceTrend


def group_price_points(
    points: Iterable[PricePoint],
) -> dict[tuple[str, str, str], list[PricePoint]]:
    grouped: dict[tuple[str, str, str], list[PricePoint]] = defaultdict(list)
    for point in points:
        key = (point.availability_zone, point.instance_type, point.product_description)
        grouped[key].append(point)
    return dict(grouped)


def _weighted_quantile(intervals: list[tuple[Decimal, float]], quantile: float) -> Decimal:
    total = sum(duration for _, duration in intervals)
    threshold = total * quantile
    accumulated = 0.0
    for price, duration in sorted(intervals, key=lambda item: item[0]):
        accumulated += duration
        if accumulated >= threshold:
            return price
    return max(intervals, key=lambda item: item[0])[0]


def calculate_price_stats(
    points: list[PricePoint], start: datetime, end: datetime
) -> PriceStats | None:
    if not points or end <= start:
        return None
    ordered = sorted(points, key=lambda point: point.timestamp)
    # Keep the final value for duplicate timestamps returned at page boundaries.
    deduped: list[PricePoint] = []
    for point in ordered:
        if deduped and point.timestamp == deduped[-1].timestamp:
            deduped[-1] = point
        else:
            deduped.append(point)
    intervals: list[tuple[Decimal, float]] = []
    for index, point in enumerate(deduped):
        interval_start = max(start, point.timestamp)
        interval_end = end if index + 1 == len(deduped) else min(end, deduped[index + 1].timestamp)
        seconds = max(0.0, (interval_end - interval_start).total_seconds())
        if seconds:
            intervals.append((point.price, seconds))
    if not intervals:
        return None
    observed = sum(duration for _, duration in intervals)
    requested = (end - start).total_seconds()
    weighted_sum = sum(price * Decimal(str(duration)) for price, duration in intervals)
    average = weighted_sum / Decimal(str(observed))
    latest = deduped[-1]
    previous = deduped[-2] if len(deduped) > 1 else None
    if previous is None:
        trend = PriceTrend("unknown", "?", None, None, latest.timestamp, None)
    else:
        delta = latest.price - previous.price
        if delta > 0:
            direction, symbol = "up", "↑"
        elif delta < 0:
            direction, symbol = "down", "↓"
        else:
            direction, symbol = "flat", "→"
        percent = (delta / previous.price * Decimal("100")) if previous.price else None
        trend = PriceTrend(direction, symbol, delta, percent, latest.timestamp, previous.timestamp)
    p50 = _weighted_quantile(intervals, 0.50)
    p95 = _weighted_quantile(intervals, 0.95)
    ranking = latest.price * Decimal("0.5") + average * Decimal("0.3") + p95 * Decimal("0.2")
    return PriceStats(
        latest_price=latest.price,
        previous_price=previous.price if previous else None,
        trend=trend,
        time_weighted_average_price=average,
        time_weighted_p50_price=p50,
        time_weighted_p95_price=p95,
        max_price=max(price for price, _ in intervals),
        price_change_count=max(0, len(deduped) - 1),
        observed_seconds=observed,
        requested_seconds=requested,
        ranking_price=ranking,
        incomplete_history=observed < requested * 0.90,
    )
