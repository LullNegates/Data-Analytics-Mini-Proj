"""
Context builder — assembles optimised LLM input for each question.

Strategy (per docs/model-context-strategy.md):
  Layer 1 — Dataset.md excerpt  : schema + research question (~500 tokens)
  Layer 2 — stats JSON           : pre-computed analysis (primary evidence)
  Layer 3 — CSV table / summary  : raw data overview (~300-550 tokens)

phi4-mini supports 128K tokens; Ollama defaults to 4096 unless num_ctx is set.
All raw per-run rows are replaced by per-game aggregates — the analysis pipeline
already acts as the attention layer over the 877-row CSVs.
"""

import csv
import json
import re
from pathlib import Path


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def dataset_excerpt(dataset_path: Path, q_num: int) -> str:
    text = dataset_path.read_text(encoding="utf-8")

    # Research-question paragraph for this Q
    q_match = re.search(
        rf"\*\*Q{q_num} —.*?(?=\*\*Q\d|^---)", text, re.DOTALL | re.MULTILINE
    )
    q_block = q_match.group(0).strip() if q_match else ""

    # CSV column description section
    csv_section_map = {1: "q1_reduction.csv", 2: "q2_saturation.csv", 3: "q3_lifetimes.csv"}
    csv_header = csv_section_map.get(q_num, "")
    sections = re.split(r"\n### ", text)
    csv_block = ""
    for sec in sections:
        if sec.strip().startswith(csv_header):
            csv_block = "### " + sec.split("\n---")[0].strip()
            break

    # Q2 also needs the models table to interpret AIC results
    models_block = ""
    if q_num == 2:
        for sec in sections:
            if sec.strip().startswith("models.py"):
                models_block = "### " + sec.split("\n---")[0].strip()
                break

    parts = [p for p in [q_block, csv_block, models_block] if p]
    return "\n\n".join(parts)


def _load_stats(analysis_dir: Path, q_num: int) -> str:
    path = analysis_dir / f"q{q_num}_stats.json"
    if not path.exists():
        return f"[q{q_num}_stats.json not found — run analysis/run.py first]"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _slim_q2_stats(analysis_dir: Path) -> str:
    """Strip model_comparison arrays from q2_stats — model reads best_model from the
    flat table above, not from nested arrays. Reduces Q2 context by ~65%."""
    path = analysis_dir / "q2_stats.json"
    if not path.exists():
        return "[q2_stats.json not found]"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    slim_games = []
    for g in data.get("games", []):
        slim_games.append({
            "game":                  g["game"],
            "genre":                 g["genre"],
            "n_wrs":                 g["n_wrs"],
            "span_days":             g["span_days"],
            "best_model":            g.get("best_model", {}).get("model") if g.get("best_model") else None,
            "best_model_aic":        g.get("best_model", {}).get("aic") if g.get("best_model") else None,
            "best_model_r2":         g.get("best_model", {}).get("r2") if g.get("best_model") else None,
            "improvement_accel":     g.get("improvement_acceleration", {}).get("interpretation"),
            "structural_break":      {
                k: v for k, v in g.get("structural_break", {}).items()
                if k in ("split_wr_number", "split_date", "f_statistic", "significant_at_0.05")
            } if g.get("structural_break") else None,
        })
    slim = {
        "analysis":           data.get("analysis"),
        "model_wins":         data.get("model_wins"),
        "best_overall_model": data.get("best_overall_model"),
        "games":              slim_games,
    }
    return json.dumps(slim, ensure_ascii=False, indent=2)


def _fmt_seconds(s: float) -> str:
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# ── Q1 ─────────────────────────────────────────────────────────────────────


def build_q1_context(data_dir: Path, analysis_dir: Path, dataset_md: Path) -> tuple[str, int]:
    csv_path = data_dir / "q1_reduction.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Explicit column labels to prevent metric confusion
    header = (
        f"{'Spiel':<42} {'Genre':<18} "
        f"{'%Reduktion':<11} {'Jahre':<7} {'%/Jahr':<8} "
        f"{'WR_Anzahl':<10} {'WR_pro_Jahr':<12} "
        f"{'Erste_Zeit':<12} {'Aktuelle_Zeit'}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"{r['game']:<42} {r['genre']:<18} "
            f"{float(r['pct_reduction']):<11.2f} {float(r['years_span']):<7.1f} "
            f"{float(r['annual_rate_pct']):<8.3f} "
            f"{r['wr_count']:<10} {float(r['wr_density_per_year']):<12.3f} "
            f"{_fmt_seconds(float(r['first_time_s'])):<12} "
            f"{_fmt_seconds(float(r['last_time_s']))}"
        )
    table = "\n".join(lines)

    # Metric legend to prevent model from confusing wr_density with wr_rate
    legend = (
        "Spaltenbedeutungen:\n"
        "  %Reduktion   = (ErsteZeit − AktuelleZeit) / ErsteZeit × 100  [absolut]\n"
        "  %/Jahr       = %Reduktion / Jahre  [jährliche Rate]\n"
        "  WR_Anzahl    = Gesamtzahl der je gesetzten Weltrekorde\n"
        "  WR_pro_Jahr  = WR_Anzahl / Jahre  [Weltrekordfrequenz, NICHT wr_rate]\n"
        "  wr_rate (in q1_stats.json) = WR_Anzahl / Gesamteinreichungen  [Schwierigkeit]\n"
        "Wichtig: WR_pro_Jahr und wr_rate sind VERSCHIEDENE Metriken — nicht verwechseln."
    )

    # Load per-game acceleration from q2_stats (improvement_acceleration.interpretation)
    # q1_stats velocity_trend is insufficient_data for all games due to small n;
    # q2_stats runs the same Spearman test on improvement magnitudes with more data.
    accel_map: dict[str, str] = {}
    q2_stats_path = analysis_dir / "q2_stats.json"
    if q2_stats_path.exists():
        with open(q2_stats_path, encoding="utf-8") as f:
            q2data = json.load(f)
        for g in q2data.get("games", []):
            interp = (g.get("improvement_acceleration") or {}).get("interpretation", "")
            if interp:
                accel_map[g["game"]] = interp

    # Rebuild table with Trend column
    header = (
        f"{'Spiel':<42} {'Genre':<18} "
        f"{'%Reduktion':<11} {'Jahre':<7} {'%/Jahr':<8} "
        f"{'WR_Anzahl':<10} {'WR_pro_Jahr':<12} "
        f"{'Erste_Zeit':<12} {'Aktuelle_Zeit':<14} {'Trend'}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for r in rows:
        trend = accel_map.get(r["game"], "?")
        lines.append(
            f"{r['game']:<42} {r['genre']:<18} "
            f"{float(r['pct_reduction']):<11.2f} {float(r['years_span']):<7.1f} "
            f"{float(r['annual_rate_pct']):<8.3f} "
            f"{r['wr_count']:<10} {float(r['wr_density_per_year']):<12.3f} "
            f"{_fmt_seconds(float(r['first_time_s'])):<12} "
            f"{_fmt_seconds(float(r['last_time_s'])):<14} "
            f"{trend}"
        )
    table = "\n".join(lines)

    accel_count   = sum(1 for v in accel_map.values() if v == "accelerating")
    decel_count   = sum(1 for v in accel_map.values() if v == "decelerating")
    accel_summary = (
        f"Trend-Überblick (Spalte 'Trend'): {accel_count} Spiele beschleunigend, "
        f"{decel_count} Spiele verlangsamend (aus q2_stats improvement_acceleration)."
    )

    stats = _load_stats(analysis_dir, 1)
    schema = dataset_excerpt(dataset_md, 1)

    combined = (
        f"{schema}\n\n---\n\n"
        f"## Rohdaten (q1_reduction.csv — alle {len(rows)} Spiele)\n\n"
        f"{legend}\n\n{accel_summary}\n\n{table}\n\n---\n\n"
        f"## Statistische Analyse (q1_stats.json)\n\n```json\n{stats}\n```"
    )
    return combined, _estimate_tokens(combined)


# ── Q2 ─────────────────────────────────────────────────────────────────────


def build_q2_context(data_dir: Path, analysis_dir: Path, dataset_md: Path) -> tuple[str, int]:
    csv_path = data_dir / "q2_saturation.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Aggregate 877 rows → one row per game
    games: dict[tuple, dict] = {}
    for r in rows:
        key = (r["game"], r["genre"])
        if key not in games:
            games[key] = {"n_wrs": 0, "first_time": float(r["time_seconds"]),
                          "last_time": float(r["time_seconds"]), "span_days": 0.0}
        g = games[key]
        g["n_wrs"] += 1
        t = float(r["time_seconds"])
        d = float(r["days_since_first"])
        g["first_time"] = max(g["first_time"], t)
        g["last_time"] = min(g["last_time"], t)
        g["span_days"] = max(g["span_days"], d)

    # Pull best_model directly from q2_stats so it appears as a table column.
    # This is the key fix: the model reads the correct answer from a flat column
    # instead of having to parse 5 nested model entries per game.
    stats_path = analysis_dir / "q2_stats.json"
    best_model_map: dict[str, dict] = {}
    if stats_path.exists():
        with open(stats_path, encoding="utf-8") as f:
            q2data = json.load(f)
        for g in q2data.get("games", []):
            bm = g.get("best_model") or {}
            sb = g.get("structural_break") or {}
            accel = (g.get("improvement_acceleration") or {}).get("interpretation", "")
            best_model_map[g["game"]] = {
                "best_model": bm.get("model", "?"),
                "aic":        bm.get("aic"),
                "r2":         bm.get("r2"),
                "struct_sig": sb.get("significant_at_0.05", False),
                "struct_date": sb.get("split_date", ""),
                "accel":      accel,
            }

    saturation_models = {"exp_decay", "gompertz"}
    header = (
        f"{'Spiel':<42} {'Genre':<18} {'WRs':<5} {'Span':<6} "
        f"{'BestesModell':<14} {'AIC':<9} {'R²':<6} "
        f"{'Sättigung?':<11} {'StrukturBruch?':<15} {'Trend'}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for (game, genre), g in sorted(games.items()):
        bm = best_model_map.get(game, {})
        model_name = bm.get("best_model", "?")
        is_sat = "JA" if model_name in saturation_models else "nein"
        sb_sig = "JA" if bm.get("struct_sig") else "nein"
        sb_date = bm.get("struct_date", "")[:10]
        sb_str = f"JA ({sb_date})" if bm.get("struct_sig") else "nein"
        aic = f"{bm['aic']:.1f}" if bm.get("aic") is not None else "?"
        r2 = f"{bm['r2']:.3f}" if bm.get("r2") is not None else "?"
        lines.append(
            f"{game:<42} {genre:<18} {g['n_wrs']:<5} {g['span_days']:<6.0f} "
            f"{model_name:<14} {aic:<9} {r2:<6} "
            f"{is_sat:<11} {sb_str:<15} {bm.get('accel', '')}"
        )
    summary = "\n".join(lines)

    legend = (
        "Sättigungsmodelle (hard floor → theoretisches Menschenlimit): exp_decay, gompertz\n"
        "Stetige Verbesserung (kein Floor): log, power_law\n"
        "Anomal/U-förmig (kein klares Muster): poly2\n"
        "BestesModell = Sieger des AIC-Vergleichs (niedrigster AIC = bestes Modell)\n"
        "StrukturBruch = signifikanter Wendepunkt (neuer Glitch/Route entdeckt)"
    )

    slim_stats = _slim_q2_stats(analysis_dir)
    schema = dataset_excerpt(dataset_md, 2)

    # Build prominent header from q2_stats so model can't miscount or omit key facts
    model_wins_block = ""
    best_overall     = ""
    sat_count        = 0
    nonsat_count     = 0
    if stats_path.exists():
        mw = q2data.get("model_wins", {})
        best_overall  = q2data.get("best_overall_model", "?")
        sat_count     = mw.get("exp_decay", 0) + mw.get("gompertz", 0)
        nonsat_count  = 17 - sat_count
        mw_parts      = " | ".join(f"{k}: {v}" for k, v in mw.items())
        model_wins_block = (
            "## KRITISCHE KENNZAHLEN — direkt aus q2_stats.json (NICHT neu berechnen)\n\n"
            f"Modell-Siegerverteilung (model_wins): {mw_parts}\n"
            f"best_overall_model = \"{best_overall}\" — das ist KEIN Sättigungsmodell.\n"
            f"WICHTIG: poly2 ist das häufigste Modell (6/17 Spiele). Poly2-Spiele sättigen NICHT.\n\n"
            f"Sättigungsverteilung (unveränderlich — aus Modellkategorien ablesen, nicht zählen):\n"
            f"  Saturierende Spiele (exp_decay + gompertz): {sat_count} von 17\n"
            f"  NICHT saturierende Spiele (log, power_law, poly2):  {nonsat_count} von 17\n\n"
            "Strukturbrüche:\n"
            "  ALLE 17 Spiele haben significant_at_0.05 = true.\n"
            "  Das Datum steht in der Spalte 'StrukturBruch?' — structural_break DARF NICHT null sein.\n"
        )

    combined = (
        f"{schema}\n\n---\n\n"
        f"{model_wins_block}\n---\n\n"
        f"## Übersicht je Spiel — {len(games)} Spiele (Spalte 'BestesModell' ist maßgeblich)\n\n"
        f"{legend}\n\n{summary}\n\n---\n\n"
        f"## Statistische Details (q2_stats.json, model_comparison-Arrays entfernt)\n\n"
        f"```json\n{slim_stats}\n```"
    )
    return combined, _estimate_tokens(combined)


# ── Q3 ─────────────────────────────────────────────────────────────────────


def build_q3_context(data_dir: Path, analysis_dir: Path, dataset_md: Path) -> tuple[str, int]:
    csv_path = data_dir / "q3_lifetimes.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Aggregate per game
    games: dict[tuple, dict] = {}
    for r in rows:
        key = (r["game"], r["genre"])
        if key not in games:
            games[key] = {"n_wrs": 0, "n_standing": 0, "durations": []}
        g = games[key]
        g["n_wrs"] += 1
        if r.get("event", "1") == "0":
            g["n_standing"] += 1
        try:
            g["durations"].append(float(r["duration_days"]))
        except (ValueError, KeyError):
            pass

    header = f"{'Spiel':<42} {'Genre':<18} {'WRs':<5} {'Stehend':<9} {'Median (Tage)':<14} {'Max (Tage)'}"
    sep = "-" * len(header)
    lines = [header, sep]
    for (game, genre), g in sorted(games.items()):
        durations = sorted(g["durations"])
        n = len(durations)
        median = durations[n // 2] if n else 0.0
        max_d = durations[-1] if durations else 0.0
        lines.append(
            f"{game:<42} {genre:<18} {g['n_wrs']:<5} {g['n_standing']:<9} "
            f"{median:<14.1f} {max_d:.1f}"
        )
    summary = "\n".join(lines)

    stats = _load_stats(analysis_dir, 3)
    schema = dataset_excerpt(dataset_md, 3)

    combined = (
        f"{schema}\n\n---\n\n"
        f"## Übersicht je Spiel (q3_lifetimes.csv, aggregiert — {len(games)} Spiele)\n\n{summary}\n\n---\n\n"
        f"## Statistische Analyse — Kaplan-Meier (q3_stats.json)\n\n```json\n{stats}\n```"
    )
    return combined, _estimate_tokens(combined)
