from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class RegionInfo:
    name: str
    endpoint: str | None = None
    opt_in_status: str | None = None


@dataclass(frozen=True)
class LatencyResult:
    region: str
    median_ms: float | None
    p95_ms: float | None
    successes: int
    attempts: int
    status: str
    error: str | None = None


@dataclass(frozen=True)
class PricePoint:
    timestamp: datetime
    price: Decimal
    availability_zone: str
    instance_type: str
    product_description: str


@dataclass(frozen=True)
class PriceTrend:
    direction: str
    symbol: str
    absolute_change: Decimal | None
    percent_change: Decimal | None
    latest_price_at: datetime
    previous_price_at: datetime | None


@dataclass(frozen=True)
class PriceStats:
    latest_price: Decimal
    previous_price: Decimal | None
    trend: PriceTrend
    time_weighted_average_price: Decimal
    time_weighted_p50_price: Decimal
    time_weighted_p95_price: Decimal
    max_price: Decimal
    price_change_count: int
    observed_seconds: float
    requested_seconds: float
    ranking_price: Decimal
    incomplete_history: bool


@dataclass
class Candidate:
    region: str
    availability_zone: str
    instance_type: str
    product_description: str
    latency: LatencyResult
    prices: PriceStats
    duration_hours: Decimal
    placement_score: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def estimated_compute_cost(self) -> Decimal:
        return self.prices.ranking_price * self.duration_hours


@dataclass(frozen=True)
class Exclusion:
    region: str
    reason: str
    detail: str


def jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value
