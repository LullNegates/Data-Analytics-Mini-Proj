"""
Q2 — Sättigungsanalyse: Verlangsamt sich die Verbesserungsrate?

Context layers (see docs/model-context-strategy.md):
  1. Dataset.md Q2 excerpt + q2_saturation.csv schema + models.py table
  2. Per-game summary from q2_saturation.csv (17 rows aggregated, ~350 tokens)
  3. q2_stats.json — AIC rankings, best model per game, structural breaks (~9.8K tokens)

Total budget: ~11.5K tokens  (num_ctx=16384)
"""

import json
from datetime import datetime
from pathlib import Path

import requests

from questions.context_builder import build_q2_context

SYSTEM_PROMPT = """\
Du bist ein Datenanalyst für ein Hochschulprojekt über Speedrunning-Weltrekorde an der FHDW Hannover.

Du erhältst eine Übersichtstabelle mit einer Spalte "BestesModell" — diese Spalte ist maßgeblich.
Lies den Wert direkt aus der Tabelle. Leite ihn NICHT aus dem JSON ab und erfinde ihn NICHT.

Modellkategorien (aus der Tabellenspalte "Sättigung?"):
  JA  → exp_decay oder gompertz: Spiel nähert sich einem theoretischen menschlichen Limit (hard floor)
  nein → log oder power_law: Spiel verbessert sich stetig ohne erkennbaren Grenzwert
  nein → poly2: anomales oder U-förmiges Muster, keine klare Aussage möglich

WICHTIG — Ausgabeformat:
- Antworte NUR mit einem validen JSON-Objekt. Kein Text, keine Kommentare (kein //).
- Keine Markdown-Codeblöcke.
- Erfinde keine Zahlen — nur Werte aus Tabelle und JSON verwenden.

Das JSON muss EXAKT diese Struktur haben:

{
  "findings": [
    {
      "id": "F1",
      "title": "Spiele mit Sättigungsmodell",
      "text": "Doom 3, Half-Life 2, Pac-Man, Portal, Quake, Super Mario 64, Super Mario Bros. und OoT zeigen exp_decay oder gompertz als bestes Modell — sie nähern sich einem theoretischen Limit."
    },
    {
      "id": "F2",
      "title": "Spiele mit stetiger Verbesserung",
      "text": "Minecraft und The Talos Principle zeigen log als bestes Modell — keine erkennbare Sättigung."
    },
    {
      "id": "F3",
      "title": "Strukturelle Brüche",
      "text": "17 von 17 Spielen zeigen einen signifikanten Strukturbruch (F > 3.0), was auf Glitch- oder Routenentdeckungen hindeutet."
    },
    {
      "id": "F4",
      "title": "Genre-Muster",
      "text": "FPS-Spiele neigen zur Sättigung. Puzzle-Spiele zeigen gemischte Muster."
    }
  ],
  "saturation_by_game": [
    {
      "game": "Celeste",
      "best_model": "power_law",
      "saturation": false,
      "structural_break": "2018-01-28",
      "interpretation": "Stetige Verbesserung ohne erkennbaren Floor. Strukturbruch deutet auf frühe Glitch-Entdeckung hin."
    }
  ],
  "genre_patterns": [
    { "genre": "Action-Adventure", "observation": "Beobachtung in 1-2 Sätzen." },
    { "genre": "Arcade", "observation": "Beobachtung." },
    { "genre": "FPS", "observation": "Beobachtung." },
    { "genre": "Platformer", "observation": "Beobachtung." },
    { "genre": "Puzzle", "observation": "Beobachtung." },
    { "genre": "RPG", "observation": "Beobachtung." },
    { "genre": "Sandbox", "observation": "Beobachtung." }
  ],
  "summary": "Gesamtzusammenfassung in 3-4 Sätzen."
}

Regeln:
- saturation_by_game muss ALLE 17 Spiele enthalten — kürze die Liste nicht.
- best_model: lies den Wert aus der Spalte "BestesModell" in der Tabelle — nicht erraten.
- saturation: true nur wenn best_model == "exp_decay" oder "gompertz".
- structural_break: Datum aus Spalte "StrukturBruch?" oder null wenn "nein".
- genre_patterns: genau 7 Einträge, einen pro Genre — keine Genres gruppieren.
- Mindestens 4 Findings.\
"""

USER_PROMPT_TEMPLATE = """\
{context}

---

Lies die Tabelle oben und erstelle das JSON-Objekt.
Die Spalte "BestesModell" in der Tabelle gibt den AIC-Sieger für jedes Spiel an — lies ihn direkt ab.
saturation_by_game muss alle 17 Spiele enthalten. Kürze nicht.
Gib NUR das JSON aus — kein Text, keine Kommentare.\
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
        "options":    {"temperature": 0.1, "num_predict": 6000, "num_ctx": num_ctx},
    }
    resp = requests.post(url, json=payload, stream=True, timeout=600)
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


def run_q2(data_dir: Path, output_dir: Path, analysis_dir: Path, dataset_md: Path,
           model: str, ollama_url: str, keep_alive: int, num_ctx: int) -> None:
    context, tok_estimate = build_q2_context(data_dir, analysis_dir, dataset_md)

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
        "question":       "q2",
        "title":          "Sättigungsanalyse — Verlangsamt sich die Verbesserungsrate?",
        "model":          model,
        "generated_at":   datetime.now().isoformat(timespec="seconds"),
        "token_estimate": tok_estimate,
        **result,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "q2_analysis.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Gespeichert → {out_path}")
