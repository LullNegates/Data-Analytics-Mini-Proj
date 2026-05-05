# Projektplan — Data Analytics Mini-Projekt

**Datensatz**: → wird aus `ideas.md` gewählt (Team-Abstimmung steht aus)  
**Abgabe**: 17.05.2026 23:59 | **Präsentation**: 18./19./26.05.2026

---

## Pflichtaufgaben (vor Analysestart)

- [ ] Datensatz aus `ideas.md` auswählen
- [ ] Gantt-Chart erstellen und an Prof. Klünder schicken
- [ ] **Pflichttermin** mit Prof. Klünder vereinbaren (terminlich verpflichtend!)
- [ ] Selbständigkeitserklärung in Ausarbeitung einplanen

---

## Grober Zeitplan

| Zeitraum | Phase | Aufgaben |
|---------|-------|---------|
| 01.05 – 04.05 | Phase 1–2 | Fragestellung finalisieren, Gantt erstellen, Termin vereinbaren |
| 05.05 – 09.05 | Phase 3 | Daten herunterladen, Qualität prüfen, Bereinigung |
| 10.05 – 13.05 | Phase 4–5 | Deskriptive Statistik, Hypothesentests, Visualisierungen |
| 14.05 – 17.05 | Phase 6 | 10-seitige Ausarbeitung + Präsentation fertigstellen |
| 18./19./26.05 | Präsentation | 20-minütiger Vortrag |

---

## Dokumentationsstruktur (max. 10 Seiten)

### 1. Einleitung (Phase 1 — Fragestellung)
- Breite Fragestellung einführen und in einen größeren Kontext setzen
- Motivation: Warum ist die Antwort für andere interessant?
- Verfeinerung der Fragestellung mit KAOS-Baum (grafisch darstellen)

### 2. Methodik
- **2a. Datenbasis**: Herkunft, Umfang, Struktur des Datensatzes beschreiben
- **2b. Datenbereinigung**: Was wurde entfernt/bereinigt/harmonisiert? (und warum)
- **2c. Analyse**: Welche statistischen Tests wurden gewählt und warum?  
  → Voraussetzungen immer prüfen und dokumentieren (z.B. Normalverteilungstest)

### 3. Ergebnisse
- Alle relevanten Werte angeben (nicht nur p < 0.05 / p > 0.05)
- Effektgröße angeben (Cohens d, r oder r²)
- Findings explizit formulieren: *„Finding 1: …"*
- Visualisierungen mit Beschriftung

### 4. Diskussion + Handlungsempfehlungen
- Was bedeuten die Zahlen in der Praxis?
- Was kann **nicht** geschlossen werden? (Korrelation ≠ Kausalität explizit nennen)
- Praktische Empfehlungen ableiten

### 5. Fazit

### 6. Selbständigkeitserklärung *(Pflicht)*

---

## Präsentation (20 Min.)

Erzählt eine Geschichte:
1. Wie seid ihr auf die Fragestellung gekommen?
2. Wie habt ihr die Daten erhoben und analysiert?
3. Was sind die Ergebnisse?
4. Was lest ihr daraus?
5. Was habt ihr gelernt?

---

## Kritische Hinweise aus der Vorlesung

> "Mit komplexer Statistik beeindruckt ihr niemanden — vielmehr besteht das Risiko, dass ihr am Ende eure eigene Arbeit nicht mehr versteht."

- Immer Voraussetzungen vor jedem Test prüfen (Normalverteilung, Skalenniveau)
- Deskriptive Statistik zuerst — dann erst inferenzielle
- Alle relevanten Kennzahlen berichten, nicht nur Signifikanz
- Korrelation ≠ Kausalität — explizit ansprechen
- Detailgrad: genug um Korrektheit zu beurteilen, nicht so viel, dass es verwirrt

---

## Ordnerstruktur

```
data/        → rohe CSV/JSON-Dateien (nicht ins Git bei sensiblen Daten)
notebooks/   → Jupyter Notebooks pro Analyseschritt
docs/        → Entwürfe Ausarbeitung (.docx / .tex) und Präsentation (.pptx)
```
