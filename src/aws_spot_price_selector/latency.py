from __future__ import annotations

import logging
import math
import ssl
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import LatencyConfig
from .models import LatencyResult, RegionInfo

LOGGER = logging.getLogger(__name__)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = math.ceil(percentile * len(ordered)) - 1
    return ordered[max(0, min(rank, len(ordered) - 1))]


def endpoint_for(region: RegionInfo) -> str:
    if region.endpoint:
        return f"https://{region.endpoint}/"
    return f"https://ec2.{region.name}.amazonaws.com/"


def _attempt(url: str, timeout_seconds: float) -> float:
    request = Request(url, method="HEAD", headers={"User-Agent": "spot-region-selector/0.1"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl.create_default_context()):
            pass
    except HTTPError:
        # An AWS HTTP error still proves that DNS, TCP, TLS, and HTTP completed.
        pass
    elapsed = time.perf_counter() - started
    return elapsed * 1000


def measure_region(region: RegionInfo, config: LatencyConfig) -> LatencyResult:
    LOGGER.debug("Starting RTT probe for %s", region.name)
    url = endpoint_for(region)
    timeout = config.timeout_ms / 1000
    with suppress(OSError, URLError, TimeoutError):
        _attempt(url, timeout)  # warm-up; excluded from statistics
    values = []
    errors = []
    for _ in range(config.attempts):
        try:
            values.append(_attempt(url, timeout))
        except (OSError, URLError, TimeoutError) as exc:
            errors.append(exc.__class__.__name__)
    required = math.ceil(config.attempts / 2)
    if len(values) < required:
        result = LatencyResult(
            region=region.name,
            median_ms=None,
            p95_ms=None,
            successes=len(values),
            attempts=config.attempts,
            status="latency_unavailable",
            error=", ".join(sorted(set(errors))) or "insufficient successful attempts",
        )
        LOGGER.debug("RTT probe for %s failed: %s", region.name, result.error)
        return result
    median = statistics.median(values)
    p95 = _percentile(values, 0.95)
    metric = median if config.metric == "median" else p95
    status = "eligible" if metric <= config.max_rtt_ms else "above_limit"
    result = LatencyResult(
        region=region.name,
        median_ms=median,
        p95_ms=p95,
        successes=len(values),
        attempts=config.attempts,
        status=status,
        error=None,
    )
    LOGGER.debug(
        "RTT probe completed for %s: median=%.1fms p95=%.1fms status=%s",
        region.name,
        median,
        p95,
        status,
    )
    return result


def measure_regions(regions: list[RegionInfo], config: LatencyConfig) -> list[LatencyResult]:
    LOGGER.info(
        "Measuring RTT to %d regions (%d attempts each, concurrency %d)",
        len(regions),
        config.attempts,
        config.concurrency,
    )
    results = []
    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = {pool.submit(measure_region, region, config): region for region in regions}
        for future in as_completed(futures):
            region = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    LatencyResult(
                        region=region.name,
                        median_ms=None,
                        p95_ms=None,
                        successes=0,
                        attempts=config.attempts,
                        status="latency_unavailable",
                        error=exc.__class__.__name__,
                    )
                )
            completed = len(results)
            LOGGER.info("RTT progress: %d/%d regions completed", completed, len(regions))
    return sorted(
        results,
        key=lambda result: (
            result.median_ms is None,
            result.median_ms if result.median_ms is not None else float("inf"),
            result.region,
        ),
    )
