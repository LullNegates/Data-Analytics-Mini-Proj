"""
Chart registry — maps CSV stem names to their graph functions.

To add a new chart (e.g. for model output):
  1. Create visualise/charts/my_output.py  with  def graph_my_output(path): ...
  2. Import it below and add one entry to CHART_REGISTRY.
  3. Done — main.py picks it up automatically.
"""

from charts.all_runs       import graph_all_runs
from charts.generic        import graph_generic
from charts.q1_reduction   import graph_q1_reduction
from charts.q2_saturation  import graph_q2_saturation
from charts.q3_lifetimes   import graph_q3_lifetimes
from charts.wr_progression import graph_wr_progression

# ── registry ──────────────────────────────────────────────────────────────────
# key   = CSV filename stem (without .csv)
# value = function(path: Path) -> None

CHART_REGISTRY: dict[str, callable] = {
    "all_runs":       graph_all_runs,
    "wr_progression": graph_wr_progression,
    "q1_reduction":   graph_q1_reduction,
    "q2_saturation":  graph_q2_saturation,
    "q3_lifetimes":   graph_q3_lifetimes,
    # ── add future charts below this line ──────────────────────────────────
}

FALLBACK = graph_generic
