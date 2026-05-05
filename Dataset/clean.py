"""
Load raw JSON files from data/raw/ and export 5 clean CSVs to data/clean/.

  all_runs.csv            every valid run for every game (date, time, is_wr flag)
  wr_progression.csv      WR-only master: every run that set a new record
  q1_reduction.csv        one row per game — % time reduction summary (Q1)
  q2_saturation.csv       time-series rows for games with long WR history (Q2)
  q3_lifetimes.csv        one row per WR duration, tagged by genre + decade (Q3)

Run: python clean.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data" / "raw"
CLEAN_DIR = Path(__file__).parent / "data" / "clean"

# Q2 filter thresholds
Q2_MIN_WR_ENTRIES = 5
Q2_MIN_YEARS = 2.0


def load_raw() -> list[dict]:
    records = []
    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"  [warn] could not read {path.name}: {exc}")
    return records


# ---------- builders ----------

def build_all_runs(records: list[dict]) -> list[dict]:
    """Every valid run across all games, with an is_wr flag."""
    rows = []
    for rec in records:
        if "all_runs" not in rec:
            print(f"  [warn] {rec['game']} has no all_runs — run fetch.py to upgrade")
            continue
        wr_ids = {e["run_id"] for e in rec["wr_progression"]}
        for entry in rec["all_runs"]:
            rows.append({
                "game":         rec["game"],
                "genre":        rec["genre"],
                "category":     rec["category"],
                "date":         entry["date"],
                "time_seconds": entry["time_seconds"],
                "run_id":       entry["run_id"],
                "is_wr":        entry["run_id"] in wr_ids,
            })
    return rows


def build_wr_master(records: list[dict]) -> list[dict]:
    """WR-only master: every run that set a new world record."""
    rows = []
    for rec in records:
        for i, entry in enumerate(rec["wr_progression"], 1):
            rows.append({
                "game":         rec["game"],
                "genre":        rec["genre"],
                "category":     rec["category"],
                "wr_number":    i,
                "date":         entry["date"],
                "time_seconds": entry["time_seconds"],
            })
    return rows


def build_q1_reduction(records: list[dict]) -> list[dict]:
    """One summary row per game/category — sorted by % reduction descending."""
    rows = []
    for rec in records:
        prog = rec["wr_progression"]
        if len(prog) < 2:
            continue
        first, last = prog[0], prog[-1]
        d0 = datetime.fromisoformat(first["date"])
        d1 = datetime.fromisoformat(last["date"])
        years = max((d1 - d0).days / 365.25, 0.01)
        pct = (first["time_seconds"] - last["time_seconds"]) / first["time_seconds"] * 100
        rows.append({
            "game":            rec["game"],
            "genre":           rec["genre"],
            "category":        rec["category"],
            "wr_count":        len(prog),
            "total_runs":      rec["total_runs"],
            "first_date":      first["date"],
            "last_date":       last["date"],
            "first_time_s":    round(first["time_seconds"], 3),
            "last_time_s":     round(last["time_seconds"], 3),
            "pct_reduction":   round(pct, 4),
            "years_span":      round(years, 2),
            "annual_rate_pct": round(pct / years, 4),
        })
    rows.sort(key=lambda r: r["pct_reduction"], reverse=True)
    return rows


def build_q2_saturation(records: list[dict]) -> list[dict]:
    """
    Time-series rows for log-regression saturation analysis.
    Only includes game/category combos with >= 5 WR entries spanning >= 2 years.
    Adds days_since_first so the analyst can directly fit log(x+1) vs time_seconds.
    """
    rows = []
    for rec in records:
        prog = rec["wr_progression"]
        if len(prog) < Q2_MIN_WR_ENTRIES:
            continue
        d0 = datetime.fromisoformat(prog[0]["date"])
        d1 = datetime.fromisoformat(prog[-1]["date"])
        if (d1 - d0).days < Q2_MIN_YEARS * 365:
            continue
        for i, entry in enumerate(prog, 1):
            d = datetime.fromisoformat(entry["date"])
            rows.append({
                "game":             rec["game"],
                "genre":            rec["genre"],
                "category":         rec["category"],
                "wr_number":        i,
                "date":             entry["date"],
                "days_since_first": (d - d0).days,
                "time_seconds":     entry["time_seconds"],
            })
    return rows


def build_q3_lifetimes(records: list[dict]) -> list[dict]:
    """
    One row per consecutive WR pair — how long each record stood.
    Tagged by genre and decade for cross-genre and cross-era comparison.
    """
    rows = []
    for rec in records:
        prog = rec["wr_progression"]
        if len(prog) < 3:
            continue
        for i in range(len(prog) - 1):
            d_set    = datetime.fromisoformat(prog[i]["date"])
            d_broken = datetime.fromisoformat(prog[i + 1]["date"])
            rows.append({
                "game":           rec["game"],
                "genre":          rec["genre"],
                "category":       rec["category"],
                "wr_number":      i + 1,
                "wr_set_date":    prog[i]["date"],
                "wr_broken_date": prog[i + 1]["date"],
                "duration_days":  (d_broken - d_set).days,
                "decade":         f"{(d_set.year // 10) * 10}s",
                "time_seconds":   prog[i]["time_seconds"],
            })
    return rows


# ---------- output ----------

def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        print(f"  [skip]  {path.name} — no data")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [ok]    {path.name}  ({len(rows)} rows)")


def main() -> None:
    records = load_raw()
    if not records:
        print("No raw files found. Run fetch.py first.")
        return

    print(f"Loaded {len(records)} raw files\n")

    all_runs   = build_all_runs(records)
    wr_master  = build_wr_master(records)
    q1         = build_q1_reduction(records)
    q2         = build_q2_saturation(records)
    q3         = build_q3_lifetimes(records)

    write_csv(all_runs,  CLEAN_DIR / "all_runs.csv")
    write_csv(wr_master, CLEAN_DIR / "wr_progression.csv")
    write_csv(q1,        CLEAN_DIR / "q1_reduction.csv")
    write_csv(q2,        CLEAN_DIR / "q2_saturation.csv")
    write_csv(q3,        CLEAN_DIR / "q3_lifetimes.csv")

    print(f"\nClean datasets written to: {CLEAN_DIR}")

    if q1:
        print("\nQ1 reduction ranking (top 5):")
        print(f"  {'Game':<45} {'%':<8} {'Years'}")
        print(f"  {'-'*45} {'-'*8} {'-'*5}")
        for r in q1[:5]:
            print(f"  {r['game']:<45} {r['pct_reduction']:<8.2f} {r['years_span']}")


if __name__ == "__main__":
    main()
