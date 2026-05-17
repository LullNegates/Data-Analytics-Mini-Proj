"""Q1 Data Transfer Objects — per-game velocity trend analysis."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class VelocityTrendResult:
    """Spearman rank correlation of improvement sizes vs time for one game.

    rho < 0  → improvements shrink over time (decelerating)
    rho > 0  → improvements grow over time (accelerating)
    |rho| < 0.2 → no clear trend
    None     → fewer than 4 data points (insufficient_data)
    """
    rho: float | None
    pvalue: float | None
    interpretation: str  # "decelerating" | "accelerating" | "no_trend" | "insufficient_data"

    def to_dict(self) -> dict:
        return {
            "rho":            self.rho,
            "pvalue":         self.pvalue,
            "interpretation": self.interpretation,
        }
