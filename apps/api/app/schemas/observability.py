from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PhaseGateModel(BaseModel):
    phase_0_data_contracts: bool
    phase_1_benchmark_fidelity: bool
    phase_2_test_harness: bool
    phase_3_engineering_health: bool
    phase_4_stable_baseline: bool


class ReliabilityKpiModel(BaseModel):
    generate_latency_ms_p95: float | None = None
    generate_error_rate_pct: float | None = None
    benchmark_latency_ms_p95: float | None = None
    benchmark_error_rate_pct: float | None = None
    sample_window: str
    sample_size: int
    measurement_method: str
    notes: list[str] = Field(default_factory=list)


class QualityKpiModel(BaseModel):
    news_impact_precision_proxy_pct: float | None = None
    benchmark_tracking_error_proxy_pct: float | None = None
    sample_window: str
    measurement_method: str
    notes: list[str] = Field(default_factory=list)


class MlRobustnessKpiModel(BaseModel):
    out_of_sample_stability_pct: float | None = None
    fallback_rate_pct: float | None = None
    fallback_rate_by_cause: dict[str, float] = Field(default_factory=dict)
    sample_window: str
    measurement_method: str
    notes: list[str] = Field(default_factory=list)


class EngineeringHealthKpiModel(BaseModel):
    pr_pass_rate_pct: float | None = None
    flaky_test_rate_pct: float | None = None
    mean_time_to_detect_regressions_minutes: float | None = None
    sample_window: str
    measurement_method: str
    notes: list[str] = Field(default_factory=list)


class ObservabilityKpiResponse(BaseModel):
    generated_at: datetime
    phase_gates: PhaseGateModel
    reliability: ReliabilityKpiModel
    quality: QualityKpiModel
    ml_robustness: MlRobustnessKpiModel
    engineering_health: EngineeringHealthKpiModel
    notes: list[str] = Field(default_factory=list)