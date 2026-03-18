from __future__ import annotations

import statistics
import time
from dataclasses import dataclass

import requests

BASE_URL = "http://127.0.0.1:8000"
ITERATIONS = 100
TIMEOUT_SECONDS = 5
TARGET_ID = 1


@dataclass
class BenchmarkResult:
    name: str
    average_ms: float
    min_ms: float
    max_ms: float
    success_count: int
    failure_count: int


def _measure_endpoint(path: str, *, iterations: int = ITERATIONS) -> BenchmarkResult:
    latencies_ms: list[float] = []
    success_count = 0
    failure_count = 0

    with requests.Session() as session:
        for _ in range(iterations):
            started = time.perf_counter()
            try:
                response = session.get(
                    f"{BASE_URL}{path}",
                    params={"id": TARGET_ID},
                    timeout=TIMEOUT_SECONDS,
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies_ms.append(elapsed_ms)
                response.raise_for_status()
                success_count += 1
            except requests.RequestException as exc:
                failure_count += 1
                print(f"[WARN] {path} request failed: {exc}")

    if not latencies_ms:
        raise RuntimeError(f"No successful timing samples were recorded for {path}.")

    return BenchmarkResult(
        name=path,
        average_ms=statistics.fmean(latencies_ms),
        min_ms=min(latencies_ms),
        max_ms=max(latencies_ms),
        success_count=success_count,
        failure_count=failure_count,
    )


def _print_result(result: BenchmarkResult) -> None:
    print(f"Endpoint: {result.name}")
    print(f"  Average response time: {result.average_ms:.2f} ms")
    print(f"  Min response time: {result.min_ms:.2f} ms")
    print(f"  Max response time: {result.max_ms:.2f} ms")
    print(f"  Success count: {result.success_count}")
    print(f"  Failure count: {result.failure_count}")


def main() -> None:
    print(
        f"Benchmarking {ITERATIONS} requests each against "
        f"{BASE_URL}/db-direct and {BASE_URL}/cache"
    )

    db_result = _measure_endpoint("/db-direct")
    cache_result = _measure_endpoint("/cache")

    print()
    _print_result(db_result)
    print()
    _print_result(cache_result)
    print()

    speedup_ratio = db_result.average_ms / cache_result.average_ms
    improvement_percent = (
        (db_result.average_ms - cache_result.average_ms) / db_result.average_ms
    ) * 100

    print("Summary")
    print(f"  Average /db-direct response time: {db_result.average_ms:.2f} ms")
    print(f"  Average /cache response time: {cache_result.average_ms:.2f} ms")
    print(f"  Speedup ratio: {speedup_ratio:.2f}x")
    print(f"  Response time improvement: {improvement_percent:.2f}%")


if __name__ == "__main__":
    main()
