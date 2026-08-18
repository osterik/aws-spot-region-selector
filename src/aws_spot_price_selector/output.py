from __future__ import annotations

import json
from typing import Iterable

from .config import Config
from .models import Candidate, Exclusion, LatencyResult, jsonable
from .pipeline import EvaluationResult


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    lines = ["  ".join(header.ljust(width) for header, width in zip(headers, widths))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend("  ".join(cell.ljust(width) for cell, width in zip(row, widths)) for row in rows)
    return "\n".join(lines)


def _money(value) -> str:
    sign = "-" if value < 0 else ""
    amount = f"{abs(value):.6f}".rstrip("0").rstrip(".")
    return f"{sign}${amount}"


def _trend(candidate: Candidate) -> str:
    trend = candidate.prices.trend
    if trend.absolute_change is None:
        return "?"
    sign = "+" if trend.absolute_change > 0 else ""
    percent = "?" if trend.percent_change is None else f"{sign}{trend.percent_change:.1f}%"
    return f"{trend.symbol} {sign}{_money(trend.absolute_change)} ({percent})"


def render_latency(result: EvaluationResult, config: Config) -> str:
    rows = []
    for item in result.latencies:
        rows.append(
            [
                item.region,
                "-" if item.median_ms is None else f"{item.median_ms:.1f} ms",
                "-" if item.p95_ms is None else f"{item.p95_ms:.1f} ms",
                f"{item.successes}/{item.attempts}",
                item.status,
            ]
        )
    text = _table(["REGION", "RTT_MED", "RTT_P95", "SUCCESS", "STATUS"], rows)
    if config.output.explain_exclusions and result.exclusions:
        text += "\n\nExcluded by config:\n" + "\n".join(
            f"- {item.region}: {item.detail}" for item in result.exclusions
        )
    return text


def render_evaluation(result: EvaluationResult, config: Config) -> str:
    candidates = [result.recommendation] + result.alternatives
    rows = []
    for item in candidates:
        if item is None:
            continue
        rows.append(
            [
                item.region,
                item.availability_zone,
                item.instance_type,
                f"{item.latency.median_ms:.1f} ms",
                _money(item.prices.latest_price),
                _trend(item),
                _money(item.prices.time_weighted_average_price),
                _money(item.prices.time_weighted_p95_price),
                _money(item.estimated_compute_cost),
                "-" if item.placement_score is None else str(item.placement_score),
            ]
        )
    text = _table(
        ["REGION", "AZ", "TYPE", "RTT_MED", "LATEST", "TREND", "AVG", "P95", "EST_COST", "SPS"],
        rows,
    )
    selected = result.recommendation
    if selected:
        text += (
            f"\n\nRecommended: {selected.region} / {selected.availability_zone} / "
            f"{selected.instance_type}\n"
            "Reason: lowest estimated compute cost within the configured constraints; "
            "price ties prefer lower RTT."
        )
    if result.warnings:
        text += "\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings)
    if config.output.explain_exclusions and result.exclusions:
        text += "\nExcluded:\n" + "\n".join(
            f"- {item.region}: {item.reason} ({item.detail})" for item in result.exclusions
        )
    return text


def render_json(result: EvaluationResult, config: Config) -> str:
    payload = {
        "schema_version": 1,
        "generated_at": result.generated_at,
        "measurement_origin": "local",
        "mode": result.mode,
        "criteria": {
            "max_rtt_ms": config.latency.max_rtt_ms,
            "history_days": config.pricing.history_days,
            "duration_hours": config.workload.duration_hours,
            "min_placement_score": config.placement.min_score,
            "ranking_price_weights": {"latest": "0.5", "average": "0.3", "p95": "0.2"},
        },
        "recommendation": result.recommendation,
        "alternatives": result.alternatives,
        "latencies": result.latencies,
        "excluded_regions": result.exclusions,
        "warnings": result.warnings,
    }
    return json.dumps(jsonable(payload), indent=2, ensure_ascii=False, sort_keys=True)


def render(result: EvaluationResult, config: Config) -> str:
    if config.output.format == "json":
        return render_json(result, config)
    if result.mode == "latency":
        return render_latency(result, config)
    return render_evaluation(result, config)
