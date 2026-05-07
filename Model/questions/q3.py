"""
Q3 — WR-Lebensdauer: Wie lange halten Weltrekorde?

Context layers (see docs/model-context-strategy.md):
  1. Dataset.md Q3 excerpt + q3_lifetimes.csv schema (right-censoring explanation)
  2. Per-game summary from q3_lifetimes.csv (17 rows aggregated, ~350 tokens)
  3. q3_stats.json — Kaplan-Meier medians, survival probabilities, Gini, Mann-Whitney (~1.4K tokens)

Total budget: ~3K tokens  (num_ctx=16384)
"""

import json
from datetime import datetime
from pathlib import Path

import requests

from questions.context_builder import build_q3_context

SYSTEM_PROMPT = """\
Du bist ein Datenanalyst für ein Hochschulprojekt über Speedrunning-Weltrekorde an der FHDW Hannover.
Du erhältst drei Informationsschichten:
  1. Schema: Forschungsfrage, CSV-Spaltenbeschreibung, Erklärung von Right-Censoring und Kaplan-Meier
  2. Übersicht: aggregierte Kennzahlen je Spiel aus q3_lifetimes.csv
  3. Analyse: vorberechnete Kaplan-Meier-Ergebnisse aus q3_stats.json

WICHTIG — Ausgabeformat:
- Antworte NUR mit einem validen JSON-Objekt. Kein Text, keine Erklärungen davor oder danach.
- Keine JavaScript-Kommentare (kein // oder /* */).
- Keine Markdown-Codeblöcke (kein ```).
- Erfinde keine Zahlen — nur Werte aus den bereitgestellten Daten verwenden.

Das JSON muss EXAKT diese Struktur haben (Beispielwerte zeigen das Format — ersetze sie mit echten Daten):

{
  "findings": [
    {
      "id": "F1",
      "title": "Median WR-Lebensdauer nach Genre",
      "text": "Der KM-Median beträgt für Platformer 17 Tage und für RPG 52 Tage."
    },
    {
      "id": "F2",
      "title": "Überlebenswahrscheinlichkeit nach einem Jahr",
      "text": "Nach 365 Tagen überlebt ein RPG-Weltrekord mit 15.3% Wahrscheinlichkeit."
    },
    {
      "id": "F3",
      "title": "Signifikante Genre-Unterschiede",
      "text": "Der Kruskal-Wallis-Test zeigt p=0.0, d.h. signifikante Unterschiede zwischen Genres."
    },
    {
      "id": "F4",
      "title": "Jahrzehntvergleich",
      "text": "WRs aus den 2010ern hielten im Schnitt X Tage, in den 2020ern Y Tage."
    }
  ],
  "genre_survival": [
    {
      "genre": "Action-Adventure",
      "km_median_days": 14.0,
      "survival_at_365": 0.0643,
      "interpretation": "Weltrekorde brechen sehr schnell. Nur 6.4% überleben ein Jahr."
    },
    {
      "genre": "Arcade",
      "km_median_days": 7.0,
      "survival_at_365": 0.1875,
      "interpretation": "Überraschend hohe Überlebensrate trotz kurzem Median."
    }
  ],
  "summary": "Gesamtzusammenfassung in 3-4 Sätzen."
}

Regeln:
- Antworte auf Deutsch.
- findings: mindestens 4 Einträge, jeder mit id, title und text (nur Strings).
- genre_survival: ein Eintrag pro Genre aus den Daten (7 Genres), km_median_days und survival_at_365 als Zahlen.
- Erkläre in einem Finding, warum KM dem einfachen Median überlegen ist.
- Für den Jahrzehntvergleich: nutze decade_stats aus q3_stats.json — der Schlüssel heißt "decade_stats", nicht "decade_comparison".\
"""

USER_PROMPT_TEMPLATE = """\
{context}

---

Analysiere die drei Informationsschichten oben und erstelle das JSON-Objekt.
Beantworte dabei:
1. Wie lange halten WRs im KM-Median je Genre? Welches Genre hält am längsten?
2. Welches Genre hat die höchste Überlebenswahrscheinlichkeit nach 365 Tagen?
3. Sind die Genre-Unterschiede statistisch signifikant (Kruskal-Wallis p-Wert)?
4. Jahrzehntvergleich: nutze nur Daten aus q3_stats.json — erfinde keine Werte.

Gib NUR das JSON-Objekt aus. Kein erklärender Text, keine Kommentare.\
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


def run_q3(data_dir: Path, output_dir: Path, analysis_dir: Path, dataset_md: Path,
           model: str, ollama_url: str, keep_alive: int, num_ctx: int) -> None:
    context, tok_estimate = build_q3_context(data_dir, analysis_dir, dataset_md)

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
        "question":       "q3",
        "title":          "WR-Lebensdauer — Kaplan-Meier Überlebensanalyse",
        "model":          model,
        "generated_at":   datetime.now().isoformat(timespec="seconds"),
        "token_estimate": tok_estimate,
        **result,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "q3_analysis.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Gespeichert → {out_path}")
