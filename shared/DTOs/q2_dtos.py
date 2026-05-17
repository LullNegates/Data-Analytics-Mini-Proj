"""Q2 Data Transfer Objects — saturation / curve-fitting analysis per game."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ImprovementAccelerationResult:
    """Linear slope of per-WR improvement sizes over time for one game.

    A negative slope means each successive WR saves less time than the previous
    one — the classic saturation signature. A positive slope signals an active
    discovery or optimisation phase.
    """
    slope_s_per_day: float
    interpretation: str  # "decelerating" | "accelerating"

    def to_dict(self) -> dict:
        return {
            "slope_s_per_day": self.slope_s_per_day,
            "interpretation":  self.interpretation,
        }


@dataclass
class StructuralBreakResult:
    """Chow Test structural break for one game's WR time series.

    A significant break indicates a paradigm shift: a new glitch, route
    discovery, or tool/technique change that reset the improvement trajectory.
    Field name uses 'significant_at_005' to avoid the dot in the Python
    identifier; to_dict() exposes it as "significant_at_0.05" for JSON.
    """
    split_wr_number: int
    split_date: str
    f_statistic: float
    significant_at_005: bool  # JSON key: "significant_at_0.05"

    def to_dict(self) -> dict:
        return {
            "split_wr_number":     self.split_wr_number,
            "split_date":          self.split_date,
            "f_statistic":         self.f_statistic,
            "significant_at_0.05": self.significant_at_005,
        }


@dataclass
class GameQ2Result:
    """Full saturation analysis result for one game.

    model_comparison and best_model are plain dicts (from FitResult.to_dict())
    because FitResult lives in models.py and is serialised at the analysis layer.
    """
    game: str
    genre: str
    n_wrs: int
    span_days: int
    pct_of_reduction_in_dataset: float
    model_comparison: list           # list[dict] — one entry per fitted model
    best_model: dict | None          # lowest-AIC model dict, or None
    lowess_r2: float | None
    improvement_acceleration: ImprovementAccelerationResult | None
    structural_break: StructuralBreakResult | None

    def to_dict(self) -> dict:
        return {
            "game":                        self.game,
            "genre":                       self.genre,
            "n_wrs":                       self.n_wrs,
            "span_days":                   self.span_days,
            "pct_of_reduction_in_dataset": self.pct_of_reduction_in_dataset,
            "model_comparison":            self.model_comparison,
            "best_model":                  self.best_model,
            "lowess_r2":                   self.lowess_r2,
            "improvement_acceleration":    self.improvement_acceleration.to_dict()
                                           if self.improvement_acceleration else None,
            "structural_break":            self.structural_break.to_dict()
                                           if self.structural_break else None,
        }
