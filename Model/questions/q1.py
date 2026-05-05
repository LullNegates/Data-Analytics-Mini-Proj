"""
Q1 — Prozentuale Zeitreduktion je Spielkategorie

Loads q1_reduction.csv, builds a prompt, calls Ollama (streaming),
and saves the structured JSON response to output/q1_analysis.json.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

SYSTEM_PROMPT = """\
Du bist ein Datenanalyst für ein Hochschulprojekt über Speedrunning-Weltrekorde an der FHDW Hannover.
Du erhältst eine bereits berechnete Datentabelle und sollst die Ergebnisse interpretieren.

Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt — kein Text davor oder danach.
Halte dich exakt an dieses Schema:

{
  "findings": [
    { "id": "F1", "title": "<kurzer Titel>", "text": "<Befund in 2-3 Sätzen, konkrete Zahlen nennen>" }
  ],
  "genre_patterns": [
    { "genre": "<Genrename>", "observation": "<Beobachtung in 1-2 Sätzen>" }
  ],
  "summary": "<Gesamtzusammenfassung in 3-4 Sätzen für eine wissenschaftliche Ausarbeitung>"
}

Regeln:
- Antworte auf Deutsch.
- Nenne immer konkrete Prozentzahlen aus den Daten.
- Unterscheide zwischen absoluter Reduktion und jährlicher Rate.
- Korrelation ≠ Kausalität — weise darauf hin, falls relevant.
- Mindestens 4 Findings, mindestens ein Genre-Muster pro Genre in den Daten.\
"""


def _fmt_seconds(s: float) -> str:
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _build_table(rows: list[dict]) -> str:
    header = (
        f"{'Rang':<5} {'Spiel':<42} {'Genre':<18} {'Kat.':<22} "
        f"{'% Red.':<8} {'Jahre':<7} {'Jährl.%':<9} {'WRs':<5} "
        f"{'Erste Zeit':<12} {'Aktuelle Zeit'}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i:<5} {r['game']:<42} {r['genre']:<18} {r['category']:<22} "
            f"{float(r['pct_reduction']):<8.2f} {float(r['years_span']):<7.1f} "
            f"{float(r['annual_rate_pct']):<9.3f} {r['wr_count']:<5} "
            f"{_fmt_seconds(float(r['first_time_s'])):<12} "
            f"{_fmt_seconds(float(r['last_time_s']))}"
        )
    return "\n".join(lines)


def _call_ollama_streaming(url: str, model: str, system: str, user: str, keep_alive: int = 0) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     True,
        "keep_alive": keep_alive,
        "options":    {"temperature": 0.15, "num_predict": 3000},
    }
    resp = requests.post(url, json=payload, stream=True, timeout=300)
    resp.raise_for_status()

    full = []
    print()
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
        full.append(token)
        if chunk.get("done"):
            break
    print("\n")
    return "".join(full)


def _parse_json(raw: str) -> dict:
    # strip possible markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("`").strip()
    return json.loads(text)


def run_q1(data_dir: Path, output_dir: Path, model: str, ollama_url: str, keep_alive: int) -> None:
    csv_path = data_dir / "q1_reduction.csv"
    if not csv_path.exists():
        print(f"[error] Not found: {csv_path}")
        print("        Run Dataset/clean.py first.")
        return

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("[error] q1_reduction.csv is empty.")
        return

    table = _build_table(rows)
    user_prompt = f"""\
Hier sind die berechneten Speedrunning-Weltrekord-Daten für Forschungsfrage 1.
Die Tabelle ist nach prozentualer Zeitreduktion absteigend sortiert.

{table}

Beantworte anhand dieser Daten:
1. Welche Spielkategorie hat sich prozentual am stärksten verbessert und welche am wenigsten?
2. Gibt es erkennbare Muster nach Genre (z.B. verbessern sich bestimmte Genres schneller)?
3. Wie unterscheiden sich absolute Reduktion und jährliche Rate zwischen alten und neuen Spielen?
4. Welche überraschenden oder auffälligen Werte gibt es in den Daten?

Antworte nur mit dem JSON-Objekt gemäß dem vorgegebenen Schema.\
"""

    print(f"  Modell : {model}")
    print(f"  Daten  : {csv_path.name}  ({len(rows)} Zeilen)")
    print(f"  Ollama : {ollama_url}")
    print("\n  Generiere Antwort (Streaming)...")
    print("  " + "─" * 60)

    try:
        raw = _call_ollama_streaming(ollama_url, model, SYSTEM_PROMPT, user_prompt, keep_alive)
    except requests.ConnectionError:
        print("[error] Ollama nicht erreichbar. Ist 'ollama serve' gestartet?")
        return
    except requests.HTTPError as exc:
        print(f"[error] Ollama HTTP-Fehler: {exc}")
        return

    try:
        result = _parse_json(raw)
    except json.JSONDecodeError as exc:
        print(f"[warn] Antwort ist kein valides JSON ({exc})")
        print("       Rohantwort wird als Fallback gespeichert.")
        result = {"raw_response": raw, "parse_error": str(exc)}

    output = {
        "question":     "q1",
        "title":        "Prozentuale Zeitreduktion je Spielkategorie",
        "model":        model,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_rows":    len(rows),
        **result,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "q1_analysis.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Gespeichert → {out_path}")
