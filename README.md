# Data Analytics Mini-Project

**Kurs**: Data Analytics Q2-2026 | Prof. Dr. Jil Klünder | FHDW Hannover  
**Team**: 4–5 Personen  
**Abgabe**: 17.05.2026 23:59 (Folien + 10-seitige Ausarbeitung via MS Teams "Abgaben")  
**Präsentationen**: 18.05. / 19.05. / 26.05.2026 (20 Min.)

---

## Gewähltes Thema: Speedrunning Weltrekord-Analyse

**Datensatz**: Weltrekord-Verlauf von 17 Spielen aus 7 Genres — abgerufen über die speedrun.com API v1  
**Quelle**: [speedrun.com API v1](https://github.com/speedruncomorg/api)  
**KAOS-Baum**: `KAOS_Baum_Speedrunning.pdf`

### Forschungsfragen

1. **Wie stark hat sich die Bestzeit prozentual je Spielkategorie reduziert?**  
   → Ranking aller Kategorien nach prozentualer Zeitreduktion (Q1)

2. **Gibt es einen Sättigungspunkt bei den Verbesserungen?**  
   → Logarithmische Regression: flacht die Verbesserungsrate über die Zeit ab? (Q2)

3. **Wie lange hält ein Weltrekord je nach Spielgenre?**  
   → Mediane Lebensdauer eines Weltrekords nach Genre und Jahrzehnt (Q3)

---

## Projektstruktur

```
Data-Analytics-Mini-Proj/
├── README.md                  ← Projektübersicht (diese Datei)
├── KAOS_Baum_Speedrunning.pdf ← Fragestellungsbaum (Phase 1)
├── ideas.md                   ← 15 Datensatz-Ideen (Auswahlphase)
├── project-plan.md            ← Projektplan, Gantt, Dokumentationsstruktur
│
├── Dataset/                   ← Datenbeschaffung & Bereinigung
│   ├── config.py              ← Spieleliste (17 Spiele, 7 Genres)
│   ├── fetch.py               ← speedrun.com API → data/raw/
│   ├── clean.py               ← Rohdaten → 5 bereinigte CSVs
│   ├── requirements.txt
│   └── data/
│       ├── raw/               ← API-Rohdaten JSON (nicht im Git)
│       └── clean/             ← Bereinigte Datensätze (im Git)
│           ├── all_runs.csv          ← Alle Runs mit is_wr-Flag (Master)
│           ├── wr_progression.csv    ← Nur WR-setzende Runs (Master)
│           ├── q1_reduction.csv      ← % Zeitreduktion je Kategorie
│           ├── q2_saturation.csv     ← Zeitreihen für Sättigungsanalyse
│           └── q3_lifetimes.csv      ← WR-Lebensdauer je Genre/Jahrzehnt
│
├── visualise/                 ← Terminal-Visualisierung (plotext, kein GUI)
│   ├── main.py                ← Einstiegspunkt — interaktive Dateiauswahl
│   ├── requirements.txt
│   └── charts/                ← Ein Modul pro Diagrammtyp
│       ├── registry.py        ← Hier neue Charts registrieren
│       ├── helpers.py         ← Gemeinsame Hilfsfunktionen
│       ├── all_runs.py
│       ├── wr_progression.py
│       ├── q1_reduction.py
│       ├── q2_saturation.py
│       ├── q3_lifetimes.py
│       └── generic.py         ← Fallback für unbekannte CSVs
│
├── Model/                     ← Lokale LLM-Inferenz (phi4-mini via Ollama)
│   ├── main.py                ← Einstiegspunkt — Frage auswählen & ausführen
│   ├── config.py              ← Modell, Ollama-URL, Datenpfade
│   ├── requirements.txt
│   ├── output/                ← Generierte JSON-Analysen (im Git)
│   │   └── q1_analysis.json  ← Findings + Genre-Muster + Summary
│   └── questions/             ← Ein Modul pro Forschungsfrage
│       ├── registry.py        ← Hier Q2/Q3 registrieren
│       └── q1.py              ← Q1: % Zeitreduktion → JSON-Output
│
├── notebooks/                 ← Jupyter Notebooks (Analyse, Visualisierung)
└── docs/                      ← Entwürfe Ausarbeitung + Präsentation
```

---

## Spieleliste (17 Spiele, 7 Genres)

| Genre | Spiele |
|-------|--------|
| Platformer | Super Mario Bros., Super Mario 64, Celeste |
| Action-Adventure | Super Metroid, Zelda: Ocarina of Time, Hollow Knight |
| RPG | Pokemon Red/Blue, Final Fantasy VII |
| FPS | Doom, Quake, Half-Life 2 |
| Puzzle | Portal, Portal 2, The Talos Principle |
| Sandbox | Minecraft: Java Edition |
| Arcade | Pac-Man, Donkey Kong |

---

## Datenbeschaffung

```bash
cd Dataset/
pip install -r requirements.txt
python fetch.py    # Daten von speedrun.com laden (~15–25 Min., resumierbar)
python clean.py    # 5 bereinigte CSVs generieren
```

`fetch.py` ist resumierbar — bereits abgerufene Spiele werden übersprungen.  
Die Rohdaten (`data/raw/`) sind nicht im Git; die bereinigten CSVs (`data/clean/`) sind committed.

---

## Visualisierung

```bash
cd visualise/
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Interaktive Terminal-Eingabe — kein GUI-Fenster:

```
CSV files (comma-separated) or 'all' for a folder:
> q1_reduction.csv, q3_lifetimes.csv     # einzelne Dateien
> all                                    # alle CSVs in einem Ordner
```

Dateinamen werden automatisch gegen `Dataset/data/clean/` aufgelöst.  
Neue Diagramme können in `visualise/charts/registry.py` registriert werden — `main.py` muss nicht geändert werden.

---

## Modell-Inferenz (phi4-mini via Ollama)

```powershell
# Ollama einmalig installieren: https://ollama.com
ollama pull phi4-mini

# Aus dem Model/-Verzeichnis:
cd Model\
pip install -r requirements.txt
python main.py
```

Das Modell liest die fertigen CSVs aus `Dataset/data/clean/`, interpretiert sie und gibt ein strukturiertes JSON aus — kein Rohdaten-Zugriff, keine Statistikberechnung (das erledigt `clean.py`).

Output wird nach `Model/output/` gespeichert und kann von `visualise/` weiterverarbeitet werden.  
Neue Fragen können in `Model/questions/registry.py` registriert werden — `main.py` muss nicht geändert werden.

---

## Gesamtarchitektur (Datenpipeline)

```
speedrun.com API
      │
      ▼
Dataset/fetch.py  →  data/raw/*.json
      │
      ▼
Dataset/clean.py  →  data/clean/*.csv
      │
      ├──▶  visualise/main.py   →  Terminal-Diagramme
      │
      └──▶  Model/main.py       →  output/q*_analysis.json
```

---

## Nächste Schritte

- [x] Thema gewählt: Speedrunning Weltrekord-Analyse
- [x] Dataset-Pipeline aufgebaut (`Dataset/`)
- [x] Visualisierungs-Tool aufgebaut (`visualise/`)
- [x] Modell-Projekt aufgebaut — Q1 implementiert (`Model/`)
- [ ] Gantt-Chart erstellen und an Prof. Klünder schicken
- [ ] Pflichttermin mit Prof. Klünder vereinbaren
- [ ] `python fetch.py` ausführen → Rohdaten abrufen
- [ ] `python clean.py` ausführen → CSVs generieren
- [ ] `python main.py` (Model) ausführen → Q1-Analyse generieren
- [ ] Q2 und Q3 in `Model/questions/` implementieren
- [ ] Explorative Analyse in `notebooks/`
- [ ] Ausarbeitung + Präsentation in `docs/`
