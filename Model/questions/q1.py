"""
Q1 — Prozentuale Zeitreduktion je Spielkategorie

Context layers (see docs/model-context-strategy.md):
  1. Dataset.md Q1 excerpt + q1_reduction.csv schema
  2. Full q1_reduction.csv table (17 rows, ~530 tokens — small enough verbatim)
  3. q1_stats.json (pre-computed genre comparisons, Kruskal-Wallis, velocity trends)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

from questions.context_builder import build_q1_context

SYSTEM_PROMPT = """\
Du bist ein Datenanalyst für ein Hochschulprojekt über Speedrunning-Weltrekorde an der FHDW Hannover.
Du erhältst drei Informationsschichten:
  1. Schema: Beschreibung der Forschungsfrage und der CSV-Spalten
  2. Rohdaten: die berechnete q1_reduction.csv-Tabelle (eine Zeile pro Spiel)
  3. Analyse: vorberechnete statistische Kennzahlen aus q1_stats.json

Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt — kein Text davor oder danach.
Erfinde keine Zahlen — verwende nur Werte, die in den bereitgestellten Daten stehen.
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

USER_PROMPT_TEMPLATE = """\
{context}

---

Beantworte anhand dieser drei Informationsschichten:
1. Welche Spielkategorie hat sich prozentual am stärksten verbessert und welche am wenigsten?
2. Gibt es erkennbare Muster nach Genre (z.B. verbessern sich bestimmte Genres schneller)?
3. Wie unterscheiden sich absolute Reduktion und jährliche Rate zwischen alten und neuen Spielen?
4. Welche überraschenden oder auffälligen Werte gibt es in den Daten?

Antworte nur mit dem JSON-Objekt gemäß dem vorgegebenen Schema.\
"""


def _call_ollama_streaming(url: str, model: str, system: str, user: str,
                           keep_alive: int, num_ctx: int) -> str:
    payload = {
        "model":      model,
        "messages":   [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     True,
        "keep_alive": keep_alive,
        "options":    {"temperature": 0.15, "num_predict": 3000, "num_ctx": num_ctx},
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
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip().rstrip("`").strip())


def run_q1(data_dir: Path, output_dir: Path, analysis_dir: Path, dataset_md: Path,
           model: str, ollama_url: str, keep_alive: int, num_ctx: int) -> None:
    context, tok_estimate = build_q1_context(data_dir, analysis_dir, dataset_md)

    print(f"  Modell  : {model}")
    print(f"  Kontext : ~{tok_estimate:,} Tokens  (num_ctx={num_ctx})")
    print(f"  Ollama  : {ollama_url}")

    if tok_estimate > num_ctx - 500:
        print(f"  [warn] Kontext ({tok_estimate}) nähert sich num_ctx ({num_ctx}) — Ausgabe kann abgeschnitten werden.")

    print("\n  Generiere Antwort (Streaming)...")
    print("  " + "─" * 60)

    user_prompt = USER_PROMPT_TEMPLATE.format(context=context)

    try:
        raw = _call_ollama_streaming(ollama_url, model, SYSTEM_PROMPT, user_prompt, keep_alive, num_ctx)
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
        result = {"raw_response": raw, "parse_error": str(exc)}

    output = {
        "question":      "q1",
        "title":         "Prozentuale Zeitreduktion je Spielkategorie",
        "model":         model,
        "generated_at":  datetime.now().isoformat(timespec="seconds"),
        "token_estimate": tok_estimate,
        **result,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "q1_analysis.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Gespeichert → {out_path}")
