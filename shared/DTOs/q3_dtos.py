"""
Q3 Data Transfer Objects -- F3a (post-breakthrough) and F3b (TAS proximity).
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PostTrendDTO:
    rho: float | None
    pvalue: float | None
    interpretation: str

    def to_dict(self) -> dict:
        return {"rho": self.rho, "pvalue": self.pvalue, "interpretation": self.interpretation}


@dataclass
class PostBreakthroughResult:
    """F3a: what happens after the biggest single WR improvement."""
    game: str
    breakthrough_magnitude_s: float
    breakthrough_date: str
    breakthrough_wr_number: int
    breakthrough_pct_of_total: float | None
    pre_velocity_s_per_day: float
    post_velocity_s_per_day: float
    flattening_ratio: float | None
    post_trend: PostTrendDTO | None
    days_to_10pct_threshold: int | None
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "game":                              self.game,
            "breakthrough_magnitude_s":          self.breakthrough_magnitude_s,
            "breakthrough_date":                 self.breakthrough_date,
            "breakthrough_wr_number":            self.breakthrough_wr_number,
            "breakthrough_pct_of_total":         self.breakthrough_pct_of_total,
            "pre_velocity_s_per_day":            self.pre_velocity_s_per_day,
            "post_velocity_s_per_day":           self.post_velocity_s_per_day,
            "flattening_ratio":                  self.flattening_ratio,
            "post_trend":                        self.post_trend.to_dict() if self.post_trend else None,
            "days_to_10pct_threshold":           self.days_to_10pct_threshold,
            "interpretation":                    self.interpretation,
        }


@dataclass
class TasProximityResult:
    """F3b: proximity to the theoretical TAS floor (exp_decay/Gompertz asymptote)."""
    game: str
    floor_model: str
    theoretical_floor_s: float | None = None
    current_wr_s: float | None = None
    gap_to_floor_s: float | None = None
    gap_to_floor_pct_of_first_wr: float | None = None
    pct_of_theoretical_reduction_achieved: float | None = None
    convergence_velocity_s_per_year: float | None = None
    estimated_years_to_floor: float | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"game": self.game, "floor_model": self.floor_model}
        if self.floor_model == "none_detected":
            d["note"] = self.note
            return d
        d.update({
            "theoretical_floor_s":                   self.theoretical_floor_s,
            "current_wr_s":                          self.current_wr_s,
            "gap_to_floor_s":                        self.gap_to_floor_s,
            "gap_to_floor_pct_of_first_wr":          self.gap_to_floor_pct_of_first_wr,
            "pct_of_theoretical_reduction_achieved": self.pct_of_theoretical_reduction_achieved,
            "convergence_velocity_s_per_year":       self.convergence_velocity_s_per_year,
            "estimated_years_to_floor":              self.estimated_years_to_floor,
        })
        return d
