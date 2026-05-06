"""
Q3 Statistical Analysis -- WR Lifetime Distribution by Genre and Decade

For each genre this module computes:
  - True Median Lifespan via Kaplan-Meier Estimator (handles right-censored records)
  - Survival probability at 1 and 2 years per genre (durability benchmark)
  - Gini coefficient: inequality of improvement sizes per genre
  - Kruskal-Wallis & pairwise Mann-Whitney U: do genres differ in record durability?
  - Decade comparison: are modern WRs broken faster than historical ones?

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

Reads:  data/clean/q3_lifetimes.csv
Writes: data/analysis/q3_stats.json
"""

import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import kruskal, mannwhitneyu

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


def _kaplan_meier(durations: list[float], events: list[int]) -> tuple[float, list[tuple]]:
    """
    Kaplan-Meier survival estimator.

    durations: observed lifetimes in days (both broken and still-standing records).
    events:    1 if the record was broken (event observed), 0 if still standing (censored).

    Returns (median_survival_days, [(time, S(t)), ...]).
    Median = first time S(t) drops to or below 0.5. Returns inf if the curve never
    reaches 0.5 (record type so dominant it outlasts all observations).

    Algorithm: at each unique event time t, S(t) = S(t-) * (1 - d/n) where d = number
    of events at t and n = number at risk just before t. Censored observations are
    removed from the at-risk pool after their observed time (standard KM convention:
    tied censored and event times -- events are processed first).
    """
    # At tied times: events (1) before censored (0) so censored stay in at-risk pool
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
    return median, curve


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


def run() -> dict:
    rows = _load_csv("q3_lifetimes.csv")
    if not rows:
        return {}

    valid = [r for r in rows if r.get("duration_days") not in ("", None)]

    # Group durations and events by genre
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
        median_d, curve = _kaplan_meier(durations, events)
        genre_stats[genre] = {
            "n_records":          len(durations),
            "n_standing":         sum(1 for e in events if e == 0),
            "km_median_days":     None if median_d == float("inf") else round(median_d, 1),
            "survival_at_365":    round(_km_predict(curve, 365.0), 4),
            "survival_at_730":    round(_km_predict(curve, 730.0), 4),
            "mean_observed_days": round(float(np.mean(durations)), 1),
            "max_observed_days":  round(float(np.max(durations)), 1),
        }

    # --- Gini on improvement sizes (inequality of how much each WR saved) ---
    by_genre_imp: dict[str, list] = {}
    for r in rows:
        if r.get("improvement_s") not in ("", None):
            by_genre_imp.setdefault(r["genre"], []).append(float(r["improvement_s"]))
    improvement_gini = {
        genre: round(_gini(np.array(vals)), 4)
        for genre, vals in by_genre_imp.items()
    }

    # --- Kruskal-Wallis across genres (raw durations, includes censored) ---
    groups = {g: np.array(v["durations"]) for g, v in by_genre.items() if len(v["durations"]) >= 3}
    kw_result: dict = {"stat": None, "pvalue": None}
    if len(groups) >= 2:
        try:
            stat, pval = kruskal(*groups.values())
            kw_result = {
                "stat":               round(float(stat), 4),
                "pvalue":             round(float(pval), 4),
                "significant_at_0.05": bool(pval < 0.05),
                "interpretation": (
                    "WR lifetime distributions differ significantly across genres"
                    if pval < 0.05 else
                    "No significant difference in WR lifetimes across genres"
                ),
            }
        except Exception as e:
            kw_result["note"] = str(e)

    # --- Pairwise Mann-Whitney U (which specific genre pairs differ?) ---
    genre_list = sorted(groups.keys())
    pairwise = []
    for i in range(len(genre_list)):
        for j in range(i + 1, len(genre_list)):
            g1, g2 = genre_list[i], genre_list[j]
            try:
                stat, pval = mannwhitneyu(groups[g1], groups[g2], alternative="two-sided")
                pairwise.append({
                    "genres":    f"{g1} vs {g2}",
                    "stat":      round(float(stat), 2),
                    "pvalue":    round(float(pval), 4),
                    "significant": bool(pval < 0.05),
                })
            except Exception:
                pass
    pairwise.sort(key=lambda x: x["pvalue"])

    # --- Decade comparison (descriptive; raw observed durations including censored) ---
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

    result = {
        "analysis":             "q3_lifetimes_kaplan_meier",
        "genre_stats":          genre_stats,
        "improvement_gini":     improvement_gini,
        "kruskal_wallis":       kw_result,
        "pairwise_mannwhitney": pairwise,
        "decade_stats":         decade_stats,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "q3_stats.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
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
