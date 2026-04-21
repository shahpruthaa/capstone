from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from statistics import mean
from time import perf_counter
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.schemas.observability import (
    EngineeringHealthKpiModel,
    MlRobustnessKpiModel,
    ObservabilityKpiResponse,
    PhaseGateModel,
    QualityKpiModel,
    ReliabilityKpiModel,
)
from app.schemas.portfolio import GeneratePortfolioRequest
from app.schemas.portfolio import BenchmarkSummaryResponse
from app.services.db_quant_engine import generate_portfolio, get_benchmark_summary
from app.services.mandate import build_default_mandate
from app.services.model_runtime import get_model_runtime_status
from app.services.news_signal import build_market_news_context


T = TypeVar("T")


@dataclass(frozen=True)
class SampleResult:
    result: object | None
    latency_ms: float | None
    succeeded: bool


def _sample_once(func: Callable[[], T]) -> SampleResult:
    started = perf_counter()
    try:
        result = func()
    except Exception:
        return SampleResult(result=None, latency_ms=None, succeeded=False)
    ended = perf_counter()
    return SampleResult(result=result, latency_ms=(ended - started) * 1000.0, succeeded=True)


def _safe_p95(samples: list[float]) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * len(ordered) + 0.0001)) - 1))
    return round(ordered[index], 2)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _compute_news_precision_proxy() -> float | None:
    context = build_market_news_context()
    if not context.articles:
        return None
    coherent_articles = [
        article
        for article in context.articles
        if article.affected_sectors and article.impact_score > 0 and article.summary.strip()
    ]
    return round((len(coherent_articles) / len(context.articles)) * 100.0, 2)


def _compute_tracking_error_proxy(strategy_rows: list[dict[str, float]]) -> float | None:
    if not strategy_rows:
        return None
    ai_row = next((row for row in strategy_rows if row.get("name") == "NSE Atlas AI Portfolio"), None)
    if not ai_row:
        return None
    ai_return = float(ai_row.get("annual_return_pct") or 0.0)
    proxy_gaps = [float(row.get("annual_return_pct") or 0.0) - ai_return for row in strategy_rows if row.get("is_proxy")]
    if not proxy_gaps:
        return 0.0
    root_mean_square = sqrt(mean(gap * gap for gap in proxy_gaps))
    return round(root_mean_square, 2)


def _compute_stability_proxy(runtime_status: dict[str, object]) -> float | None:
    validation_summary = runtime_status.get("validation_summary") if isinstance(runtime_status, dict) else {}
    if not isinstance(validation_summary, dict):
        validation_summary = {}
    best_ic = validation_summary.get("best_avg_spearman_ic")
    spread = validation_summary.get("avg_top_bottom_spread")
    score = 0.0
    if isinstance(best_ic, (int, float)):
        score += max(0.0, min(100.0, (float(best_ic) + 1.0) * 45.0))
    if isinstance(spread, (int, float)):
        score += max(0.0, min(20.0, float(spread) * 10.0))
    if score == 0.0:
        return None
    return round(min(100.0, score), 2)


def _compute_fallback_rates(runtime_status: dict[str, object]) -> tuple[float | None, dict[str, float]]:
    if not runtime_status:
        return None, {}
    active_mode = str(runtime_status.get("active_mode") or "unknown")
    variant = str(runtime_status.get("variant") or "RULES")
    reason = str(runtime_status.get("reason") or "none")

    fallback_rate_pct = 0.0 if variant == "LIGHTGBM_HYBRID" else 100.0
    if active_mode == "degraded_ensemble":
        fallback_rate_pct = 25.0

    fallback_rate_by_cause = {
        "rules_only": 100.0 if variant == "RULES" else 0.0,
        "non_core_components_missing": 25.0 if active_mode == "degraded_ensemble" else 0.0,
        reason: 100.0 if reason not in {"none", "unknown"} and active_mode == "rules_only" else 0.0,
    }
    fallback_rate_by_cause = {key: value for key, value in fallback_rate_by_cause.items() if key}
    return fallback_rate_pct, fallback_rate_by_cause


def get_observability_kpis(db: Session) -> ObservabilityKpiResponse:
    generate_samples: list[float] = []
    generate_failures = 0
    benchmark_samples: list[float] = []
    benchmark_failures = 0

    default_request = GeneratePortfolioRequest(
        capital_amount=500_000,
        mandate=build_default_mandate(),
        model_variant="LIGHTGBM_HYBRID",
    )

    sampled_generate = _sample_once(lambda: generate_portfolio(db, default_request))
    if sampled_generate.succeeded and sampled_generate.latency_ms is not None:
        generate_samples.append(sampled_generate.latency_ms)
    else:
        generate_failures += 1

    sampled_benchmark = _sample_once(lambda: get_benchmark_summary(db))
    if sampled_benchmark.succeeded and sampled_benchmark.latency_ms is not None:
        benchmark_samples.append(sampled_benchmark.latency_ms)
    else:
        benchmark_failures += 1

    benchmark_response: BenchmarkSummaryResponse | None = sampled_benchmark.result if isinstance(sampled_benchmark.result, BenchmarkSummaryResponse) else None
    if benchmark_response is None:
        benchmark_response = get_benchmark_summary(db)
    benchmark_rows = [strategy.model_dump() for strategy in benchmark_response.strategies]
    runtime_status = get_model_runtime_status()

    reliability = ReliabilityKpiModel(
        generate_latency_ms_p95=_safe_p95(generate_samples),
        generate_error_rate_pct=round((generate_failures / max(len(generate_samples) + generate_failures, 1)) * 100.0, 2),
        benchmark_latency_ms_p95=_safe_p95(benchmark_samples),
        benchmark_error_rate_pct=round((benchmark_failures / max(len(benchmark_samples) + benchmark_failures, 1)) * 100.0, 2),
        sample_window="single_live_sample",
        sample_size=max(len(generate_samples) + generate_failures, len(benchmark_samples) + benchmark_failures),
        measurement_method="in_process service sampling over the active database session",
        notes=[
            "Latency is sampled once per endpoint to keep the observability check lightweight.",
            "Move this metric to time-series storage before using it for hard SLO enforcement.",
        ],
    )

    quality = QualityKpiModel(
        news_impact_precision_proxy_pct=_compute_news_precision_proxy(),
        benchmark_tracking_error_proxy_pct=_compute_tracking_error_proxy(benchmark_rows),
        sample_window="current_runtime_snapshot",
        measurement_method="news semantics and benchmark dispersion proxy",
        notes=[
            "News precision is a proxy based on the current deterministic semantic feed.",
            "Tracking error is approximated from the active benchmark basket versus the AI portfolio row.",
        ],
    )

    fallback_rate_pct, fallback_rate_by_cause = _compute_fallback_rates(runtime_status)
    ml_robustness = MlRobustnessKpiModel(
        out_of_sample_stability_pct=_compute_stability_proxy(runtime_status),
        fallback_rate_pct=fallback_rate_pct,
        fallback_rate_by_cause=fallback_rate_by_cause,
        sample_window="current_model_runtime",
        measurement_method="model runtime summary and validation artifact metadata",
        notes=[
            "Out-of-sample stability is scaled from the LightGBM validation summary when it is available.",
            "Fallback rates currently reflect the active runtime mode, not a longitudinal production history.",
        ],
    )

    engineering_health = EngineeringHealthKpiModel(
        pr_pass_rate_pct=None,
        flaky_test_rate_pct=None,
        mean_time_to_detect_regressions_minutes=None,
        sample_window="ci_history_not_yet_wired",
        measurement_method="requires Git history, CI runs, and regression alert telemetry",
        notes=[
            "PR pass rate, flaky test rate, and mean time to detect regressions need CI telemetry.",
            "The repository currently exposes the smoke harness, but not longitudinal PR/test history.",
        ],
    )

    phase_gates = PhaseGateModel(
        phase_0_data_contracts=True,
        phase_1_benchmark_fidelity=bool(benchmark_rows and any(row.get("relative_accuracy_score_pct", 0.0) for row in benchmark_rows)),
        phase_2_test_harness=True,
        phase_3_engineering_health=False,
        phase_4_stable_baseline=bool(benchmark_rows and reliability.generate_error_rate_pct == 0.0 and reliability.benchmark_error_rate_pct == 0.0),
    )

    return ObservabilityKpiResponse(
        generated_at=datetime.now(timezone.utc),
        phase_gates=phase_gates,
        reliability=reliability,
        quality=quality,
        ml_robustness=ml_robustness,
        engineering_health=engineering_health,
        notes=[
            "This endpoint provides a typed baseline for Phase 0, then Phase 1/3 can harden the live measurements.",
            "The engineering-health metrics are intentionally explicit about missing CI history rather than inventing data.",
        ],
    )