"""
F3b Data Transfer Objects -- TAS vs WR comparison analysis.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TasGapSnapshot:
    """Gap between human WR and TAS time at a single point in the WR progression."""
    wr_number: int
    date: str
    wr_time_s: float
    gap_to_tas_s: float
    gap_pct: float      # gap / first_wr_time * 100

    def to_dict(self) -> dict:
        return {
            "wr_number":    self.wr_number,
            "date":         self.date,
            "wr_time_s":    self.wr_time_s,
            "gap_to_tas_s": self.gap_to_tas_s,
            "gap_pct":      self.gap_pct,
        }


@dataclass
class TasComparisonResult:
    """
    F3b: Comparison between human WR progression and a known TAS reference time.

    Fields
    ------
    game                   : game name
    tas_time_s             : known TAS time in seconds (from tas_known.json)
    tas_source             : citation string
    first_wr_time_s        : first ever human WR in seconds
    current_wr_time_s      : most recent human WR in seconds
    current_gap_s          : current_wr - tas_time
    current_gap_pct        : current_gap / first_wr * 100
    pct_closed             : (first_wr - current_wr) / (first_wr - tas_time) * 100
                             -- how much of the human-to-TAS gap has been closed
    gap_velocity_s_per_year: pace at which the gap is closing (last 5 WRs)
    est_years_to_match_tas : gap / velocity (forward projection)
    gap_history            : list[TasGapSnapshot] -- gap over WR progression timeline
    model_floor_s          : asymptote from exp_decay/Gompertz if available (None if not)
    model_vs_tas_delta_s   : model_floor - tas_time (positive = model overestimates floor)
    """
    game: str
    tas_time_s: float
    tas_source: str
    first_wr_time_s: float
    current_wr_time_s: float
    current_gap_s: float
    current_gap_pct: float
    pct_closed: float | None
    gap_velocity_s_per_year: float | None
    est_years_to_match_tas: float | None
    gap_history: list[TasGapSnapshot]
    model_floor_s: float | None
    model_vs_tas_delta_s: float | None
    # New fields (default-valued so existing call-sites keep compiling)
    date_surpassed: str | None = None       # date human WR first matched/beat TAS
    category_mismatch: bool = False         # TAS branch ≠ human Any% category
    tas_source_type: str = "tasvideos"      # "tasvideos" | "external" | "proxy"

    def to_dict(self) -> dict:
        return {
            "game":                    self.game,
            "tas_time_s":              self.tas_time_s,
            "tas_source":              self.tas_source,
            "first_wr_time_s":         self.first_wr_time_s,
            "current_wr_time_s":       self.current_wr_time_s,
            "current_gap_s":           self.current_gap_s,
            "current_gap_pct":         self.current_gap_pct,
            "pct_closed":              self.pct_closed,
            "gap_velocity_s_per_year": self.gap_velocity_s_per_year,
            "est_years_to_match_tas":  self.est_years_to_match_tas,
            "gap_history":             [s.to_dict() for s in self.gap_history],
            "model_floor_s":           self.model_floor_s,
            "model_vs_tas_delta_s":    self.model_vs_tas_delta_s,
            "date_surpassed":          self.date_surpassed,
            "category_mismatch":       self.category_mismatch,
            "tas_source_type":         self.tas_source_type,
        }


@dataclass
class TasImpactWindow:
    """
    F3b+: Measures the impact of one TAS release on the human WR trajectory.

    For a single TAS publication date, records the human WR velocity in the
    N days before and after the TAS came out. A velocity_ratio > 1 means the
    community improved faster after the TAS (Bannister Effect).

    Fields
    ------
    game                : game name
    tas_date            : publication date of this TAS record
    tas_time_s          : TAS time in seconds
    wr_at_tas_s         : human WR time active on/just before tas_date (None if TAS predates WR data)
    wr_post_s           : best human WR within window_days after tas_date (None if no WR in window)
    improvement_s       : wr_at_tas - wr_post (seconds improved; 0 if no WR in window)
    improvement_pct     : improvement_s / wr_at_tas * 100
    n_wrs_in_window     : number of new WRs set in (tas_date, tas_date + window_days]
    vel_pre_s_per_year  : WR improvement rate in [tas_date - window_days, tas_date]
    vel_post_s_per_year : WR improvement rate in (tas_date, tas_date + window_days]
    velocity_ratio      : vel_post / vel_pre (> 1 = TAS accelerated WR improvement)
    window_days         : the window size used
    """
    game: str
    tas_date: str
    tas_time_s: float
    wr_at_tas_s: float | None
    wr_post_s: float | None
    improvement_s: float
    improvement_pct: float
    n_wrs_in_window: int
    vel_pre_s_per_year: float | None
    vel_post_s_per_year: float | None
    velocity_ratio: float | None
    window_days: int

    def to_dict(self) -> dict:
        return {
            "game":               self.game,
            "tas_date":           self.tas_date,
            "tas_time_s":         self.tas_time_s,
            "wr_at_tas_s":        self.wr_at_tas_s,
            "wr_post_s":          self.wr_post_s,
            "improvement_s":      self.improvement_s,
            "improvement_pct":    self.improvement_pct,
            "n_wrs_in_window":    self.n_wrs_in_window,
            "vel_pre_s_per_year": self.vel_pre_s_per_year,
            "vel_post_s_per_year":self.vel_post_s_per_year,
            "velocity_ratio":     self.velocity_ratio,
            "window_days":        self.window_days,
        }
