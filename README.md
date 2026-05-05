# Data Analytics Mini-Project

**Kurs**: Data Analytics Q2-2026 | Prof. Dr. Jil Klünder | FHDW Hannover  
**Abgabe**: 17.05.2026 23:59 (Folien + 10-seitige Ausarbeitung via MS Teams "Abgaben")  
**Präsentationen**: 18.05. / 19.05. / 26.05.2026 (20 Min.)

---

## Thema: Speedrunning Weltrekord-Analyse

**Datensatz**: Weltrekord-Verlauf von 17 Spielen aus 7 Genres — abgerufen über die speedrun.com API v1  
**Quelle**: [speedrun.com API v1](https://github.com/speedruncomorg/api)

### Forschungsfragen

1. **Wie stark hat sich die Bestzeit prozentual je Spielkategorie reduziert?**  
   Ranking aller Kategorien nach prozentualer Zeitreduktion (Q1)

2. **Gibt es einen Sättigungspunkt bei den Verbesserungen?**  
   Logarithmische Regression: flacht die Verbesserungsrate über die Zeit ab? (Q2)

3. **Wie lange hält ein Weltrekord je nach Spielgenre?**  
   Mediane Lebensdauer eines Weltrekords nach Genre und Jahrzehnt (Q3)

---

## Projektstruktur

```
Data-Analytics-Mini-Proj/
├── README.md
├── requirements.txt           <- Alle Python-Abhaengigkeiten (requests, plotext, numpy)
├── setup.ps1                  <- Einmaliges Setup: venv + Ollama + phi4-mini
│
├── Dataset/                   <- Datenbeschaffung, Bereinigung & Statistik
│   ├── Dataset.md             <- Vollstaendige Dokumentation (Spalten, Modelle, API)
│   ├── main.py                <- fetch + clean (+ optional --stats)
│   ├── config.py              <- Spieleliste (17 Spiele, 7 Genres)
│   ├── fetch.py               <- speedrun.com API -> data/raw/ (10k-Limit-Handling)
│   ├── clean.py               <- Rohdaten -> 5 bereinigte CSVs (erweiterte Felder)
│   ├── analysis/              <- Statistische Analyse-Module
│   │   ├── models.py          <- Kurvenanpassung: log, power law, exp decay, poly2, LOWESS
│   │   ├── q1_analysis.py     <- Q1: Power Law auf WR-Verbesserungen, Kruskal-Wallis
│   │   ├── q2_analysis.py     <- Q2: Multi-Modell-Vergleich (AIC), Saettigungspunkt
│   │   ├── q3_analysis.py     <- Q3: Gini, Mann-Whitney U, Jahrzehnt-Vergleich
│   │   └── run.py             <- Alle drei Analysen ausfuehren
│   └── data/
│       ├── raw/               <- API-Rohdaten JSON (nicht im Git)
│       ├── clean/             <- Bereinigte Datensaetze (im Git)
│       │   ├── all_runs.csv
│       │   ├── wr_progression.csv
│       │   ├── q1_reduction.csv
│       │   ├── q2_saturation.csv
│       │   └── q3_lifetimes.csv
│       └── analysis/          <- JSON-Ergebnisse der stat. Analyse
│           ├── q1_stats.json
│           ├── q2_stats.json
│           └── q3_stats.json
│
├── visualise/                 <- Terminal-Visualisierung (plotext, kein GUI)
│   ├── main.py
│   └── charts/
│       ├── registry.py        <- Hier neue Charts registrieren
│       ├── helpers.py
│       ├── all_runs.py
│       ├── wr_progression.py
│       ├── q1_reduction.py
│       ├── q2_saturation.py
│       ├── q3_lifetimes.py
│       └── generic.py
│
├── Model/                     <- Lokale LLM-Inferenz (phi4-mini via Ollama)
│   ├── main.py
│   ├── config.py              <- Modell, Ollama-URL, Datenpfade, KEEP_ALIVE
│   ├── output/                <- Generierte JSON-Analysen
│   └── questions/
│       ├── registry.py        <- Hier Q2/Q3 registrieren
│       └── q1.py
│
├── notebooks/                 <- Jupyter Notebooks
└── docs/                      <- Planung & Abgabe
    ├── KAOS_Baum_Speedrunning.pdf
    ├── Gantt_Speedrunning_Weltrekorde.xlsx
    ├── ideas.md
    └── project-plan.md
```

---

## Setup (einmalig)

**Voraussetzungen**: Python 3.11+, winget (Windows 11 eingebaut; Win 10: "App Installer" im Store)

```powershell
# 1. PowerShell oeffnen, ins Projektverzeichnis wechseln
# 2. Skript-Ausfuehrung fuer diese Sitzung erlauben:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# 3. Setup ausfuehren (venv + Ollama + phi4-mini, ~5-10 Min.):
.\setup.ps1

# 4. Umgebung aktivieren (einmal pro Terminal):
.venv\Scripts\Activate.ps1
```

`setup.ps1` erledigt: venv erstellen, alle Abhaengigkeiten installieren, Ollama via winget installieren, `phi4-mini` pullen (~2.3 GB).

---

## Datenbeschaffung

Vollstaendige Dokumentation: [Dataset/Dataset.md](Dataset/Dataset.md)

```powershell
cd Dataset
python main.py          # fetch + clean
python main.py --stats  # fetch + clean + statistische Analyse
python analysis/run.py  # nur Analyse (wenn clean-Daten bereits vorhanden)
```

Oder einzeln:

```powershell
python fetch.py    # speedrun.com API abrufen (~15-25 Min., resumierbar)
python clean.py    # 5 bereinigte CSVs generieren
```

Rohdaten (`data/raw/`) sind nicht im Git. Bereinigte CSVs (`data/clean/`) sind committed.

Die API-Paginierung behandelt Spiele mit >10.000 Runs (z.B. Minecraft) automatisch
durch einen zweiten Durchlauf in umgekehrter Reihenfolge.

---

## Visualisierung

```powershell
cd visualise
python main.py
```

```
CSV files (comma-separated) or 'all' for a folder:
> q1_reduction.csv, q3_lifetimes.csv
> all
```

Neue Diagramme: Modul in `charts/` anlegen + eine Zeile in `charts/registry.py`.

---

## Modell-Inferenz (phi4-mini via Ollama)

```powershell
# Ollama starten (separates Terminal):
ollama serve

# Frage ausfuehren:
cd Model
python main.py
```

```
Verfuegbare Fragen:
  [q1]  Q1 -- Prozentuale Zeitreduktion je Spielkategorie  (Input: q1_reduction.csv)

Frage auswaehlen [q1]:
> q1
```

Output wird als strukturiertes JSON nach `Model/output/` gespeichert. Neue Fragen: Modul in `questions/` anlegen + eine Zeile in `questions/registry.py`.

`KEEP_ALIVE` in `Model/config.py` steuert, wie lange das Modell nach der letzten Anfrage im VRAM bleibt (Standard: 300 Sekunden).

---

## Datenpipeline

```
speedrun.com API
      |
      v
Dataset/fetch.py  ->  data/raw/*.json
      |
      v
Dataset/clean.py  ->  data/clean/*.csv
      |
      +-->  visualise/main.py   ->  Terminal-Diagramme
      |
      +-->  Model/main.py       ->  output/q*_analysis.json
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

## Status

- [x] Thema gewaehlt und von Prof. Kluender genehmigt
- [x] Dataset-Pipeline aufgebaut und ausgefuehrt
- [x] Visualisierungs-Tool aufgebaut
- [x] Modell-Projekt aufgebaut -- Q1 implementiert
- [x] Setup-Skript (Ollama + phi4-mini)
- [x] Statistische Analyse-Module (analysis/) mit 4 Modellen + Kruskal-Wallis + Gini
- [x] API-Pagination fuer >10.000 Runs
- [ ] `python main.py --stats` ausfuehren -> statistische Analyse
- [ ] Q1-Analyse ausfuehren (`python main.py` in `Model/`)
- [ ] Q2 und Q3 in `Model/questions/` implementieren
- [ ] Explorative Analyse in `notebooks/`
- [ ] Ausarbeitung + Praesentation in `docs/`
