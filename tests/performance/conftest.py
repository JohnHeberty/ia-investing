"""Performance test fixtures, helpers, and baseline management.

Provides:
- Mock database sessions and service layers for API endpoint benchmarking
- Custom ``@pytest.mark.performance`` marker (registered in pyproject.toml)
- Baseline recording / comparison for regression detection
- Memory usage tracking via ``tracemalloc``
"""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

performance = pytest.mark.performance

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERF_BASELINE_DIR = Path(__file__).resolve().parent
PERF_BASELINE_FILE = PERF_BASELINE_DIR / "baselines.json"

DEFAULT_RESPONSE_TIME_MS = 500.0
DEFAULT_MEMORY_LIMIT_MB = 50.0
WARMUP_ROUNDS = 3
BENCHMARK_ROUNDS = 10

# ---------------------------------------------------------------------------
# Baseline recording / comparison
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Stores timing and memory results for a single benchmark."""

    name: str
    times_ms: list[float] = field(default_factory=list)
    memory_bytes: int | None = None
    status: str = "ok"

    @property
    def median_ms(self) -> float:
        return statistics.median(self.times_ms) if self.times_ms else 0.0

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.times_ms:
            return 0.0
        sorted_times = sorted(self.times_ms)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0.0

    def print_summary(self) -> None:
        mem_str = f"{self.memory_bytes / 1024 / 1024:.1f}MB" if self.memory_bytes else "n/a"
        print(
            f"\n  {self.name}\n"
            f"    median: {self.median_ms:.1f}ms  p95: {self.p95_ms:.1f}ms  "
            f"min: {self.min_ms:.1f}ms  max: {self.max_ms:.1f}ms  "
            f"mem: {mem_str}  status: {self.status}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "median_ms": round(self.median_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "memory_bytes": self.memory_bytes,
            "status": self.status,
        }


class BaselineStore:
    """Load/save performance baselines for regression detection."""

    def __init__(self, path: Path = PERF_BASELINE_FILE) -> None:
        self._path = path
        self._data: dict[str, dict[str, Any]] = {}
        if self._path.exists():
            with open(self._path) as f:
                self._data = json.load(f)

    def get(self, name: str) -> dict[str, Any] | None:
        return self._data.get(name)

    def save(self, result: BenchmarkResult) -> None:
        self._data[result.name] = result.to_dict()
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    def check_regression(self, result: BenchmarkResult, threshold: float = 1.2) -> list[str]:
        """Return list of regression warnings if result exceeds baseline * threshold."""
        warnings: list[str] = []
        baseline = self.get(result.name)
        if baseline is None:
            return warnings
        baseline_p95 = baseline.get("p95_ms", 0)
        if baseline_p95 > 0 and result.p95_ms > baseline_p95 * threshold:
            pct = (result.p95_ms / baseline_p95 - 1) * 100
            warnings.append(
                f"{result.name}: p95 {result.p95_ms:.1f}ms is {pct:.0f}% slower than baseline {baseline_p95:.1f}ms"
            )
        if result.memory_bytes is not None:
            baseline_mem = baseline.get("memory_bytes")
            if baseline_mem and baseline_mem > 0:
                mem_ratio = result.memory_bytes / baseline_mem
                if mem_ratio > threshold:
                    pct = (mem_ratio - 1) * 100
                    warnings.append(
                        f"{result.name}: memory {result.memory_bytes / 1024 / 1024:.1f}MB is "
                        f"{pct:.0f}% higher than baseline {baseline_mem / 1024 / 1024:.1f}MB"
                    )
        return warnings


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------


class Timer:
    """Context manager that records elapsed time in milliseconds."""

    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


class MemoryTracker:
    """Context manager that tracks peak memory usage via tracemalloc."""

    def __init__(self) -> None:
        self.peak_bytes: int = 0
        self._was_tracing = False

    def __enter__(self) -> MemoryTracker:
        self._was_tracing = tracemalloc.is_tracing()
        if not self._was_tracing:
            tracemalloc.start()
        tracemalloc.clear_traces()
        return self

    def __exit__(self, *_: object) -> None:
        if tracemalloc.is_tracing():
            self.peak_bytes = tracemalloc.get_traced_memory()[1]
            if not self._was_tracing:
                tracemalloc.stop()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def baseline_store() -> BaselineStore:
    return BaselineStore()


@pytest.fixture()
def timer() -> Timer:
    return Timer()


@pytest.fixture()
def memory_tracker() -> MemoryTracker:
    return MemoryTracker()


def _make_mock_auth_context(
    subject: str = "perf-test-user",
    org_id: Any | None = None,
    permissions: frozenset[str] | None = None,
) -> Any:
    from apps.api.security import AuthContext

    return AuthContext(
        subject=subject,
        permissions=permissions or frozenset({"*:*"}),
        authentication_method="test",
        organization_id=org_id or uuid4(),
        roles=frozenset({"admin"}),
    )


@pytest.fixture()
def mock_auth_context() -> Any:
    return _make_mock_auth_context()


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.merge = AsyncMock()
    return session


@pytest.fixture()
def mock_session() -> MagicMock:
    return _make_mock_session()


def _build_candidate_detail_mock() -> MagicMock:
    """Return a MagicMock mimicking CandidateDetail for investment candidate endpoints."""
    detail = MagicMock()
    detail.candidate.id = uuid4()
    detail.candidate.organization_id = uuid4()
    detail.candidate.origin = "manual"
    detail.candidate.status = "source_validation"
    detail.candidate.ticker = "PETR4"
    detail.candidate.exchange = "B3"
    detail.candidate.legal_name = "Petróleo Brasileiro S.A."
    detail.candidate.trading_name = "Petrobras"
    detail.candidate.cnpj = "33.000.167/0001-01"
    detail.candidate.cvm_code = "21094"
    detail.candidate.issuer_id = uuid4()
    detail.candidate.instrument_id = uuid4()
    detail.candidate.rationale = "Test candidate"
    detail.candidate.final_decision = None
    detail.candidate.final_decision_reason = None
    detail.candidate.approved_portfolio_eligible = False
    detail.candidate.created_by = "test"
    detail.candidate.created_at = MagicMock()
    detail.candidate.updated_at = MagicMock()
    detail.candidate.lock_version = 1

    source = MagicMock()
    source.kind = "b3_filing"
    source.status = "verified"
    source.official = True
    source.confidence = __import__("decimal").Decimal("0.95")

    gap = MagicMock()
    gap.code = "MISSING_CVM_FILING"
    gap.status = "open"
    gap.level = "blocking"

    run = MagicMock()
    run.id = uuid4()
    run.candidate_id = detail.candidate.id
    run.run_number = 1
    run.trigger = "manual"
    run.status = "completed"
    run.requested_by = "test"
    run.requested_at = MagicMock()
    run.data_as_of = MagicMock()
    run.workflow_id = None
    run.started_at = MagicMock()
    run.completed_at = MagicMock()
    run.decision = None
    run.summary = None
    run.blocker_codes = []
    run.research_case_id = None
    run.thesis_version_id = None
    run.committee_decision_id = None
    run.error_code = None
    run.error_detail = None

    event = MagicMock()
    event.id = uuid4()
    event.candidate_id = detail.candidate.id
    event.event_type = "candidate.created"
    event.actor_type = "user"
    event.actor_id = "test"
    event.occurred_at = MagicMock()
    event.aggregate_version = 1
    event.payload = {}

    detail.sources = [source]
    detail.gaps = [gap]
    detail.runs = [run]
    detail.events = [event]
    return detail


def _build_candidate_list_mock(count: int = 50) -> list[Any]:
    """Return a list of candidate-like mocks for list endpoint benchmarking."""
    candidates = []
    for i in range(count):
        c = MagicMock()
        c.id = uuid4()
        c.organization_id = uuid4()
        c.origin = "manual"
        c.status = "source_validation"
        c.ticker = f"TICK{i:03d}"
        c.exchange = "B3"
        c.legal_name = f"Company {i} S.A."
        c.trading_name = f"Company {i}"
        c.cnpj = f"33.000.{i:04d}/0001-01"
        c.cvm_code = f"{i:05d}"
        c.issuer_id = uuid4()
        c.instrument_id = uuid4()
        c.rationale = f"Test candidate {i}"
        c.final_decision = None
        c.final_decision_reason = None
        c.approved_portfolio_eligible = False
        c.created_by = "test"
        c.created_at = MagicMock()
        c.updated_at = MagicMock()
        c.lock_version = 1
        candidates.append(c)
    return candidates


@pytest.fixture()
def candidate_detail() -> Any:
    return _build_candidate_detail_mock()


@pytest.fixture()
def candidate_list() -> list[Any]:
    return _build_candidate_list_mock()


@pytest.fixture()
def mock_rebalance_service() -> MagicMock:
    svc = MagicMock()
    svc.propose_rebalance = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "state": "proposed",
            "portfolio_id": str(uuid4()),
            "target_allocations": {"PETR4": 0.4, "VALE3": 0.3, "ITUB4": 0.3},
            "rationale": "Performance test rebalance",
            "created_by": "perf-test",
        }
    )
    return svc


@pytest.fixture()
def mock_recommendations_deps() -> dict[str, Any]:
    """Mocks for portfolio recommendations endpoint."""
    return {
        "session_execute_result": MagicMock(),
        "get_current_prices": {},
        "compute_scores": AsyncMock(
            return_value={
                "quality": 0.8,
                "valuation": 0.6,
                "growth": 0.7,
                "leverage": 0.5,
                "momentum": 0.4,
                "dividend": 0.3,
            }
        ),
        "build_portfolio_recommendation": MagicMock(),
        "generate_llm_analysis": AsyncMock(return_value=None),
    }


# ---------------------------------------------------------------------------
# Benchmark runner (used by tests when pytest-benchmark is unavailable)
# ---------------------------------------------------------------------------


def run_benchmark(
    name: str,
    func: Any,
    rounds: int = BENCHMARK_ROUNDS,
    warmup: int = WARMUP_ROUNDS,
    memory_limit_mb: float = DEFAULT_MEMORY_LIMIT_MB,
    response_time_limit_ms: float = DEFAULT_RESPONSE_TIME_MS,
    *,
    track_memory: bool = True,
) -> BenchmarkResult:
    """Execute *func* repeatedly and collect timing/memory stats."""
    result = BenchmarkResult(name=name)

    # Warm-up
    for _ in range(warmup):
        func()

    # Timed iterations
    for _ in range(rounds):
        timer = Timer()
        with timer:
            func()
        result.times_ms.append(timer.elapsed_ms)

    # Memory tracking
    if track_memory:
        tracker = MemoryTracker()
        with tracker:
            func()
        result.memory_bytes = tracker.peak_bytes
        mem_mb = tracker.peak_bytes / 1024 / 1024
        if mem_mb > memory_limit_mb:
            result.status = "memory_exceeded"

    # Response time check
    if result.p95_ms > response_time_limit_ms:
        result.status = "slow"

    return result


async def run_async_benchmark(
    name: str,
    func: Any,
    rounds: int = BENCHMARK_ROUNDS,
    warmup: int = WARMUP_ROUNDS,
    memory_limit_mb: float = DEFAULT_MEMORY_LIMIT_MB,
    response_time_limit_ms: float = DEFAULT_RESPONSE_TIME_MS,
    *,
    track_memory: bool = True,
) -> BenchmarkResult:
    """Async version of run_benchmark for async endpoint functions."""
    result = BenchmarkResult(name=name)

    # Warm-up
    for _ in range(warmup):
        await func()

    # Timed iterations
    for _ in range(rounds):
        timer = Timer()
        with timer:
            await func()
        result.times_ms.append(timer.elapsed_ms)

    # Memory tracking
    if track_memory:
        tracker = MemoryTracker()
        with tracker:
            await func()
        result.memory_bytes = tracker.peak_bytes
        mem_mb = tracker.peak_bytes / 1024 / 1024
        if mem_mb > memory_limit_mb:
            result.status = "memory_exceeded"

    if result.p95_ms > response_time_limit_ms:
        result.status = "slow"

    return result
