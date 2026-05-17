"""
Q3 Statistical Analysis -- WR Lifetime Distribution by Genre and Decade

For each genre this module computes:
  - True Median Lifespan via Kaplan-Meier Estimator (handles right-censored records)
  - Survival probability at 1 and 2 years per genre (durability benchmark)
  - Gini coefficient: inequality of improvement sizes per genre
  - Kruskal-Wallis & pairwise Mann-Whitney U: do genres differ in record durability?
  - Decade comparison: are modern WRs broken faster than historical ones?

F3a extension -- Post-breakthrough dynamics (per game):
  After the single biggest WR improvement, does the game continue improving or flatten?

F3b extension -- TAS proximity (per game):
  How close is the current WR to the theoretical floor (exp_decay/Gompertz asymptote)?

Right-censoring treatment
--------------------------
The current world record for each game is still standing -- it has not been broken.
Its true lifetime is unknown; we only know it has survived AT LEAST X days so far.
Dropping it from the analysis (as a simple median would require) biases the result
downward: the most durable records are the ones missing from your dataset.

clean.py now sets event=1 (broken) and event=0 (standing/censored) and computes
duration_days for all rows, including the current record. The Kaplan-Meier estimator
accounts for both: censored observations reduce the at-risk pool but do not step the
survival curve, giving an unbiased estimate of median record lifetime.

Reads:  data/clean/q3_lifetimes.csv, data/clean/wr_progression.csv
Writes: data/analysis/q3_stats.json
"""

import csv
import json
import sys
from datetime import date as _date
from pathlib import Path

import numpy as np
from scipy.stats import kruskal, mannwhitneyu, spearmanr

from models import fit_exp_decay, fit_gompertz

# shared/ lives two levels up from analysis/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.q3_dtos import (KaplanMeierResult, PostBreakthroughResult,
                                  PostTrendDTO, TasProximityResult)
from shared.utils import normalize_floats

CLEAN_DIR    = Path(__file__).parent.parent / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "data" / "analysis"


def _load_csv(name: str) -> list[dict]:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found -- run clean.py first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _gini(values: np.ndarray) -> float:
    """
    Gini coefficient (0 = perfectly equal, 1 = all mass on one entry).
    Applied to improvement sizes: a high Gini means a few WRs caused most of the
    total time reduction -- glitch-dominated improvement pattern.
    """
    if len(values) < 2:
        return 0.0
    v = np.sort(np.abs(values))
    n = len(v)
    cumsum = np.cumsum(v)
    return float((2 * np.sum((np.arange(1, n + 1)) * v) - (n + 1) * cumsum[-1])
                 / (n * cumsum[-1])) if cumsum[-1] > 0 else 0.0


def _kaplan_meier(durations: list[float], events: list[int]) -> KaplanMeierResult:
    """
    Kaplan-Meier survival estimator.

    durations: observed lifetimes in days (both broken and still-standing records).
    events:    1 if the record was broken (event observed), 0 if still standing (censored).

    Returns a KaplanMeierResult with median_days and the step curve.
    Median = first time S(t) drops to or below 0.5. Returns inf if the curve never
    reaches 0.5 (record type so dominant it outlasts all observations).

    Algorithm: at each unique event time t, S(t) = S(t-) * (1 - d/n) where d = number
    of events at t and n = number at risk just before t. Censored observations are
    removed from the at-risk pool after their observed time (standard KM convention:
    tied censored and event times -- events are processed first).
    """
    pairs = sorted(zip(durations, events), key=lambda x: (x[0], -x[1]))
    n = len(pairs)
    at_risk = n
    S = 1.0
    curve: list[tuple[float, float]] = [(0.0, 1.0)]

    i = 0
    while i < n:
        t = pairs[i][0]
        j = i
        while j < n and pairs[j][0] == t:
            j += 1
        events_at_t = sum(1 for _, e in pairs[i:j] if e == 1)
        if events_at_t > 0:
            S *= (1 - events_at_t / at_risk)
            curve.append((float(t), round(float(S), 6)))
        at_risk -= (j - i)
        i = j

    median = float("inf")
    for t, p in curve[1:]:
        if p <= 0.5:
            median = t
            break
    return KaplanMeierResult(median_days=median, curve=curve)


def _km_predict(curve: list[tuple], t: float) -> float:
    """Survival probability at time t from a KM step function (right-continuous)."""
    s = 1.0
    for ct, cp in curve:
        if ct > t:
            break
        s = cp
    return s


def _event_from_row(r: dict) -> int:
    """Read event column; fall back to is_final for CSVs from before the clean.py fix."""
    if r.get("event", "") not in ("", None):
        return int(r["event"])
    return 0 if r.get("is_final", "").lower() == "true" else 1


def _post_breakthrough_dynamics(game: str, wr_rows: list[dict]) -> PostBreakthroughResult | None:
    """
    F3a: After the single biggest WR improvement (breakthrough), does improvement
    continue or flatten?

    Splits the WR series at the largest single-step time reduction, then compares
    improvement velocity (seconds saved per day) before vs after the break.
    Also runs a Spearman rank correlation on the post-breakthrough improvements to
    detect whether the game is still accelerating or has entered a plateau.

    flattening_ratio < 0.5  -> clear plateau after the breakthrough
    flattening_ratio > 1.0  -> improvement *accelerated* after the breakthrough
    otherwise               -> gradual slowdown (common after route discoveries)
    """
    if len(wr_rows) < 6:
        return None

    times = [float(r["time_seconds"]) for r in wr_rows]
    dates = [r["date"] for r in wr_rows]

    improvements: list[tuple[int, float, str]] = []
    for i in range(1, len(wr_rows)):
        imp = times[i - 1] - times[i]
        if imp > 0:
            improvements.append((i, imp, dates[i]))

    if len(improvements) < 4:
        return None

    bt_in_imps   = max(range(len(improvements)), key=lambda i: improvements[i][1])
    bt_wr_idx    = improvements[bt_in_imps][0]
    bt_magnitude = improvements[bt_in_imps][1]
    bt_date      = improvements[bt_in_imps][2]

    pre_imps  = [imp for _, imp, _ in improvements[:bt_in_imps]]
    post_imps = [imp for _, imp, _ in improvements[bt_in_imps + 1:]]

    if len(pre_imps) < 2 or len(post_imps) < 2:
        return None

    pre_span  = max(1, (_date.fromisoformat(dates[bt_wr_idx]) - _date.fromisoformat(dates[0])).days)
    post_span = max(1, (_date.fromisoformat(dates[-1]) - _date.fromisoformat(bt_date)).days)
    pre_velocity  = sum(pre_imps)  / pre_span
    post_velocity = sum(post_imps) / post_span
    flattening_ratio = round(post_velocity / pre_velocity, 4) if pre_velocity > 0 else None

    post_trend_dto: PostTrendDTO | None = None
    post_dated = [(d, imp) for _, imp, d in improvements[bt_in_imps + 1:]]
    if len(post_dated) >= 4:
        base_d = _date.fromisoformat(post_dated[0][0])
        px = np.array([(_date.fromisoformat(d) - base_d).days for d, _ in post_dated], dtype=float)
        py = np.array([imp for _, imp in post_dated], dtype=float)
        rho, pval = spearmanr(px, py)
        if not np.isfinite(rho) or not np.isfinite(pval):
            post_trend_dto = PostTrendDTO(rho=None, pvalue=None, interpretation="stable")
        else:
            interp = "decelerating" if float(rho) < -0.2 else ("accelerating" if float(rho) > 0.2 else "stable")
            post_trend_dto = PostTrendDTO(
                rho=round(float(rho), 4), pvalue=round(float(pval), 4), interpretation=interp
            )

    threshold = 0.10 * bt_magnitude
    stability_days: int | None = None
    bt_d = _date.fromisoformat(bt_date)
    for _, imp, d_str in improvements[bt_in_imps + 1:]:
        if imp < threshold:
            stability_days = (_date.fromisoformat(d_str) - bt_d).days
            break

    total_reduction = times[0] - times[-1]
    bt_pct = round(bt_magnitude / total_reduction * 100, 1) if total_reduction > 0 else None

    if flattening_ratio is not None:
        interpretation = (
            "flattens_after_breakthrough"    if flattening_ratio < 0.5  else
            "accelerates_after_breakthrough" if flattening_ratio > 1.0  else
            "gradual_slowdown"
        )
    else:
        interpretation = "insufficient_data"

    return PostBreakthroughResult(
        game                      = game,
        breakthrough_magnitude_s  = round(bt_magnitude, 2),
        breakthrough_date         = bt_date,
        breakthrough_wr_number    = int(wr_rows[bt_wr_idx].get("wr_number", bt_wr_idx + 1)),
        breakthrough_pct_of_total = bt_pct,
        pre_velocity_s_per_day    = round(pre_velocity, 6),
        post_velocity_s_per_day   = round(post_velocity, 6),
        flattening_ratio          = flattening_ratio,
        post_trend                = post_trend_dto,
        days_to_10pct_threshold   = stability_days,
        interpretation            = interpretation,
    )


def _tas_proximity(game: str, wr_rows: list[dict]) -> TasProximityResult | None:
    """
    F3b: Estimate the theoretical lower bound (TAS floor) via exp_decay/Gompertz
    asymptote and measure how close the current WR is to it.

    TAS (Tool Assisted Speedruns) define the mathematically optimal route with
    perfect execution. The exp_decay asymptote 'c' is a mathematical proxy for this
    floor. R2 >= 0.70 is required; below this the asymptote is too uncertain.

    convergence_velocity_s_per_year: seconds closed per year from the last 5 WRs.
    estimated_years_to_floor: gap / velocity (rough forward projection).
    """
    if len(wr_rows) < 5:
        return None

    first_d = _date.fromisoformat(wr_rows[0]["date"])
    x = np.array([(_date.fromisoformat(r["date"]) - first_d).days for r in wr_rows], dtype=float)
    y = np.array([float(r["time_seconds"]) for r in wr_rows])

    first_wr_s   = float(y[0])
    current_wr_s = float(y[-1])

    ed   = fit_exp_decay(x, y)
    gomp = fit_gompertz(x, y)

    floor_s: float | None = None
    floor_model = "none_detected"

    if ed is not None and ed.r2 > 0.70 and ed.params.get("c", 0) > 0:
        floor_s, floor_model = ed.params["c"], "exp_decay"
    elif gomp is not None and gomp.r2 > 0.70 and gomp.params.get("floor", 0) > 0:
        floor_s, floor_model = gomp.params["floor"], "gompertz"

    if floor_s is None or floor_s >= current_wr_s:
        return TasProximityResult(
            game        = game,
            floor_model = "none_detected",
            note        = "no convergent floor found -- log/power_law regime (still actively improving)",
        )

    gap_to_floor_s   = current_wr_s - floor_s
    gap_to_floor_pct = round(gap_to_floor_s / first_wr_s * 100, 2)
    total_possible   = first_wr_s - floor_s
    pct_achieved     = round((first_wr_s - current_wr_s) / total_possible * 100, 1) if total_possible > 0 else None

    recent_n     = min(5, len(wr_rows) - 1)
    recent_span  = max(1, (_date.fromisoformat(wr_rows[-1]["date"]) - _date.fromisoformat(wr_rows[-1 - recent_n]["date"])).days)
    recent_gain  = float(y[-1 - recent_n]) - float(y[-1])
    conv_velocity = round(recent_gain / recent_span * 365, 4) if recent_span > 0 else None

    est_years = None
    if conv_velocity and conv_velocity > 0:
        est_years = round(gap_to_floor_s / conv_velocity, 1)

    return TasProximityResult(
        game                                  = game,
        floor_model                           = floor_model,
        theoretical_floor_s                   = round(float(floor_s), 3),
        current_wr_s                          = round(current_wr_s, 3),
        gap_to_floor_s                        = round(gap_to_floor_s, 3),
        gap_to_floor_pct_of_first_wr          = gap_to_floor_pct,
        pct_of_theoretical_reduction_achieved = pct_achieved,
        convergence_velocity_s_per_year       = conv_velocity,
        estimated_years_to_floor              = est_years,
    )


def run() -> dict:
    rows = _load_csv("q3_lifetimes.csv")
    if not rows:
        return {}

    valid = [r for r in rows if r.get("duration_days") not in ("", None)]

    by_genre: dict[str, dict] = {}
    for r in valid:
        g = r["genre"]
        if g not in by_genre:
            by_genre[g] = {"durations": [], "events": []}
        by_genre[g]["durations"].append(float(r["duration_days"]))
        by_genre[g]["events"].append(_event_from_row(r))

    # --- Kaplan-Meier per genre ---
    genre_stats = {}
    for genre, data in sorted(by_genre.items()):
        durations = data["durations"]
        events    = data["events"]
        km = _kaplan_meier(durations, events)
        genre_stats[genre] = {
            "n_records":          len(durations),
            "n_standing":         sum(1 for e in events if e == 0),
            "km_median_days":     None if km.median_days == float("inf") else round(km.median_days, 1),
            "survival_at_365":    round(_km_predict(km.curve, 365.0), 4),
            "survival_at_730":    round(_km_predict(km.curve, 730.0), 4),
            "mean_observed_days": round(float(np.mean(durations)), 1),
            "max_observed_days":  round(float(np.max(durations)), 1),
        }

    # --- Gini on improvement sizes ---
    by_genre_imp: dict[str, list] = {}
    for r in rows:
        if r.get("improvement_s") not in ("", None):
            by_genre_imp.setdefault(r["genre"], []).append(float(r["improvement_s"]))
    improvement_gini = {
        genre: round(_gini(np.array(vals)), 4)
        for genre, vals in by_genre_imp.items()
    }

    # --- Kruskal-Wallis across genres ---
    groups = {g: np.array(v["durations"]) for g, v in by_genre.items() if len(v["durations"]) >= 3}
    kw_result: dict = {"stat": None, "pvalue": None}
    if len(groups) >= 2:
        try:
            stat, pval = kruskal(*groups.values())
            kw_result = {
                "stat":                round(float(stat), 4),
                "pvalue":              round(float(pval), 4),
                "significant_at_0.05": bool(pval < 0.05),
                "interpretation": (
                    "WR lifetime distributions differ significantly across genres"
                    if pval < 0.05 else
                    "No significant difference in WR lifetimes across genres"
                ),
            }
        except Exception as e:
            kw_result["note"] = str(e)

    # --- Pairwise Mann-Whitney U ---
    genre_list = sorted(groups.keys())
    pairwise = []
    for i in range(len(genre_list)):
        for j in range(i + 1, len(genre_list)):
            g1, g2 = genre_list[i], genre_list[j]
            try:
                stat, pval = mannwhitneyu(groups[g1], groups[g2], alternative="two-sided")
                pairwise.append({
                    "genres":      f"{g1} vs {g2}",
                    "stat":        round(float(stat), 2),
                    "pvalue":      round(float(pval), 4),
                    "significant": bool(pval < 0.05),
                })
            except Exception:
                pass
    pairwise.sort(key=lambda x: x["pvalue"])

    # --- Decade comparison ---
    by_decade: dict[str, dict] = {}
    for r in valid:
        decade = r.get("decade", "unknown")
        if decade not in by_decade:
            by_decade[decade] = {"durations": [], "events": []}
        by_decade[decade]["durations"].append(float(r["duration_days"]))
        by_decade[decade]["events"].append(_event_from_row(r))

    decade_stats = {}
    for decade, data in sorted(by_decade.items()):
        if len(data["durations"]) < 3:
            continue
        arr = np.array(data["durations"])
        decade_stats[decade] = {
            "n":               len(arr),
            "mean_observed":   round(float(np.mean(arr)), 1),
            "median_observed": round(float(np.median(arr)), 1),
            "n_standing":      sum(1 for e in data["events"] if e == 0),
        }

    # --- F3a: Post-breakthrough dynamics (per game) ---
    wr_prog = _load_csv("wr_progression.csv")
    by_game_wr: dict[str, list] = {}
    for r in wr_prog:
        by_game_wr.setdefault(r["game"], []).append(r)

    post_bt_results = [
        res.to_dict()
        for game, game_rows in sorted(by_game_wr.items())
        for res in [_post_breakthrough_dynamics(game, game_rows)]
        if res is not None
    ]

    # --- F3b: TAS proximity (theoretical floor per game) ---
    tas_prox_results = [
        res.to_dict()
        for game, game_rows in sorted(by_game_wr.items())
        for res in [_tas_proximity(game, game_rows)]
        if res is not None
    ]

    result = {
        "analysis":                   "q3_lifetimes_kaplan_meier",
        "genre_stats":                genre_stats,
        "improvement_gini":           improvement_gini,
        "kruskal_wallis":             kw_result,
        "pairwise_mannwhitney":       pairwise,
        "decade_stats":               decade_stats,
        "post_breakthrough_dynamics": post_bt_results,
        "tas_proximity":              tas_prox_results,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "q3_stats.json"
    out.write_text(json.dumps(normalize_floats(result), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [q3] written -> {out.name}")
    return result


def print_summary(result: dict) -> None:
    if not result:
        return
    print("\n  Q3 -- WR Lifetime by Genre (Kaplan-Meier, right-censoring corrected)")
    print(f"  {'Genre':<18} {'KM Median':<12} {'Surv@1yr':<10} {'Surv@2yr':<10} {'Standing':<10} {'Gini(imp)'}")
    print("  " + "-" * 75)
    imp_gini = result.get("improvement_gini", {})
    for genre, s in sorted(result["genre_stats"].items(),
                           key=lambda x: -(x[1]["km_median_days"] or 0)):
        km_str = f"{s['km_median_days']:.0f}d" if s["km_median_days"] is not None else "inf"
        print(f"  {genre:<18} {km_str:<12} {s['survival_at_365']:<10.3f} "
              f"{s['survival_at_730']:<10.3f} {s['n_standing']:<10} "
              f"{imp_gini.get(genre, 'n/a')}")

    kw = result.get("kruskal_wallis", {})
    if kw.get("pvalue") is not None:
        sig = "YES" if kw.get("significant_at_0.05") else "no"
        print(f"\n  Kruskal-Wallis (genres differ?): p={kw['pvalue']}  significant={sig}")

    sig_pairs = [p for p in result.get("pairwise_mannwhitney", []) if p["significant"]]
    if sig_pairs:
        print(f"\n  Significantly different genre pairs (Mann-Whitney U, p<0.05):")
        for p in sig_pairs[:5]:
            print(f"    {p['genres']:<35} p={p['pvalue']}")

    print("\n  Decade comparison (observed durations):")
    for decade, s in result.get("decade_stats", {}).items():
        print(f"    {decade}: median={s['median_observed']:.0f}d  n={s['n']}  still_standing={s['n_standing']}")

    pbd = result.get("post_breakthrough_dynamics", [])
    if pbd:
        print("\n  F3a -- Post-Breakthrough Dynamics")
        print(f"  {'Game':<38} {'Break (s)':<12} {'Flatten?':<32} {'Ratio'}")
        print("  " + "-" * 90)
        for g in pbd:
            ratio_str = f"{g['flattening_ratio']:.3f}" if g['flattening_ratio'] is not None else "n/a"
            print(f"  {g['game']:<38} {g['breakthrough_magnitude_s']:<12.1f} "
                  f"{g['interpretation']:<32} {ratio_str}")

    tas = result.get("tas_proximity", [])
    if tas:
        print("\n  F3b -- TAS Proximity (theoretical floor)")
        print(f"  {'Game':<38} {'Floor(s)':<12} {'Gap%':<10} {'%Achieved':<12} {'Est.yrs'}")
        print("  " + "-" * 90)
        for g in tas:
            if g.get("floor_model") == "none_detected":
                print(f"  {g['game']:<38} {'no floor':<12} {'--':<10} {'--':<12} --")
            else:
                yrs = f"{g['estimated_years_to_floor']:.1f}" if g.get('estimated_years_to_floor') else "inf"
                print(f"  {g['game']:<38} {g['theoretical_floor_s']:<12.1f} "
                      f"{g['gap_to_floor_pct_of_first_wr']:<10.2f} "
                      f"{g['pct_of_theoretical_reduction_achieved']:<12} {yrs}")
