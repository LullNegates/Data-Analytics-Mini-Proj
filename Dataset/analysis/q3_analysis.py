"""
Q3 Statistical Analysis -- WR Lifetime Distribution by Genre and Decade

For each genre this module computes:
  - Descriptive stats: mean, median, std, 25th/75th percentile of WR duration
  - Gini coefficient: inequality of improvement distribution (are a few WRs responsible for most gains?)
  - Kruskal-Wallis test: are lifetime distributions significantly different across genres?
  - Mann-Whitney U pairwise tests: which genre pairs are significantly different?
  - Decade comparison: are modern WRs shorter-lived (more competitive) than older ones?

WR lifetimes follow right-skewed distributions (a few long-lived records pull the mean up),
so median and non-parametric tests are more appropriate than mean and ANOVA.

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
    Gini coefficient of a distribution (0 = perfect equality, 1 = all mass on one point).
    Applied to improvement sizes: a high Gini means a few WRs account for most time savings.
    """
    if len(values) < 2:
        return 0.0
    v = np.sort(np.abs(values))
    n = len(v)
    cumsum = np.cumsum(v)
    return float((2 * np.sum((np.arange(1, n + 1)) * v) - (n + 1) * cumsum[-1])
                 / (n * cumsum[-1])) if cumsum[-1] > 0 else 0.0


def _describe(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {}
    return {
        "n":       len(values),
        "mean":    round(float(np.mean(values)), 2),
        "median":  round(float(np.median(values)), 2),
        "std":     round(float(np.std(values)), 2),
        "p25":     round(float(np.percentile(values, 25)), 2),
        "p75":     round(float(np.percentile(values, 75)), 2),
        "min":     round(float(np.min(values)), 2),
        "max":     round(float(np.max(values)), 2),
    }


def run() -> dict:
    rows = _load_csv("q3_lifetimes.csv")

    # Keep only closed lifetimes (is_final=False) for duration analysis
    closed = [r for r in rows if r.get("is_final", "").lower() != "true"
              and r.get("duration_days") not in ("", None)]

    if not closed:
        print("  [q3] no closed lifetime data found")
        return {}

    # --- Per-genre lifetime stats ---
    by_genre: dict[str, list] = {}
    for r in closed:
        by_genre.setdefault(r["genre"], []).append(float(r["duration_days"]))

    genre_stats = {}
    for genre, durations in sorted(by_genre.items()):
        arr = np.array(durations)
        stats = _describe(arr)
        stats["gini"] = round(_gini(arr), 4)
        genre_stats[genre] = stats

    # --- Gini on improvement sizes (how unequal are improvement magnitudes?) ---
    by_genre_imp: dict[str, list] = {}
    for r in rows:
        if r.get("improvement_s") not in ("", None):
            by_genre_imp.setdefault(r["genre"], []).append(float(r["improvement_s"]))

    improvement_gini = {
        genre: round(_gini(np.array(vals)), 4)
        for genre, vals in by_genre_imp.items()
    }

    # --- Kruskal-Wallis across genres ---
    groups = {g: np.array(v) for g, v in by_genre.items() if len(v) >= 3}
    kw_result = {"stat": None, "pvalue": None}
    if len(groups) >= 2:
        try:
            stat, pval = kruskal(*groups.values())
            kw_result = {
                "stat":    round(float(stat), 4),
                "pvalue":  round(float(pval), 4),
                "significant_at_0.05": bool(pval < 0.05),
                "interpretation": (
                    "WR lifetime distributions differ significantly across genres"
                    if pval < 0.05 else
                    "No significant difference in WR lifetimes across genres"
                ),
            }
        except Exception as e:
            kw_result["note"] = str(e)

    # --- Pairwise Mann-Whitney U (only report significant pairs) ---
    genre_list = sorted(groups.keys())
    pairwise = []
    for i in range(len(genre_list)):
        for j in range(i + 1, len(genre_list)):
            g1, g2 = genre_list[i], genre_list[j]
            try:
                stat, pval = mannwhitneyu(groups[g1], groups[g2], alternative="two-sided")
                pairwise.append({
                    "genres":  f"{g1} vs {g2}",
                    "stat":    round(float(stat), 2),
                    "pvalue":  round(float(pval), 4),
                    "significant": bool(pval < 0.05),
                })
            except Exception:
                pass
    pairwise.sort(key=lambda x: x["pvalue"])

    # --- Decade comparison ---
    by_decade: dict[str, list] = {}
    for r in closed:
        by_decade.setdefault(r["decade"], []).append(float(r["duration_days"]))

    decade_stats = {
        decade: _describe(np.array(vals))
        for decade, vals in sorted(by_decade.items())
        if len(vals) >= 3
    }

    result = {
        "analysis":        "q3_lifetimes",
        "genre_stats":     genre_stats,
        "improvement_gini": improvement_gini,
        "kruskal_wallis":  kw_result,
        "pairwise_mannwhitney": pairwise,
        "decade_stats":    decade_stats,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "q3_stats.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [q3] written -> {out.name}")
    return result


def print_summary(result: dict) -> None:
    if not result:
        return
    print("\n  Q3 -- WR Lifetime by Genre (days)")
    print(f"  {'Genre':<18} {'Median':<10} {'Mean':<10} {'Gini (dur)':<12} {'Gini (imp)'}")
    print("  " + "-" * 65)
    imp_gini = result.get("improvement_gini", {})
    for genre, s in sorted(result["genre_stats"].items(), key=lambda x: -x[1]["median"]):
        print(f"  {genre:<18} {s['median']:<10.1f} {s['mean']:<10.1f} "
              f"{s['gini']:<12.4f} {imp_gini.get(genre, 'n/a')}")

    kw = result.get("kruskal_wallis", {})
    if kw.get("pvalue") is not None:
        sig = "YES" if kw["significant_at_0.05"] else "no"
        print(f"\n  Kruskal-Wallis (genres differ?): p={kw['pvalue']}  significant={sig}")

    sig_pairs = [p for p in result.get("pairwise_mannwhitney", []) if p["significant"]]
    if sig_pairs:
        print(f"\n  Significantly different genre pairs (Mann-Whitney U, p<0.05):")
        for p in sig_pairs[:5]:
            print(f"    {p['genres']:<35} p={p['pvalue']}")
