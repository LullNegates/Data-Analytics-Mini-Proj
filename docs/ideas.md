# Datensatz-Ideen — Mini-Projekt

Alle 15 Ideen folgen dem KAOS-Fragestellungsbaum aus der Vorlesung:  
**Grobe Frage → Sub-Fragen → Konkrete, messbare Hypothesen**

Quellen: Kaggle, NASA Open Data, NYC Open Data, speedrun.com, BoardGameGeek

---

## 🍜 Idee 1 — Ramen Ratings (The Ramen Rater)

**Datensatz**: ~3.500 Instant-Nudel-Bewertungen (Brand, Variety, Style, Country, Stars 0–5)  
**Quelle**: kaggle.com/datasets/residentmario/ramen-ratings

```
Grobe Frage: Was macht ein Instant-Nudelprodukt besonders gut bewertet?
|
├── Beeinflusst das Herkunftsland die Qualität?
|       └── Konkret: Unterscheiden sich die Durchschnittsbewertungen zwischen
|                    asiatischen und westlichen Ländern signifikant (Mann-Whitney)?
|
├── Spielt die Verpackungsform eine Rolle?
|       └── Konkret: Erhalten Bowl-Ramen höhere Bewertungen als Pack-Ramen?
|
└── Gibt es konsistent führende Marken?
        └── Konkret: Welche Marken haben den höchsten Median-Score über alle Produkte?
```

**Warum interessant**: Instant-Nudeln sind ein globaler $50Mrd-Markt. Die Frage, ob Japan wirklich besser ist als Deutschland, lässt sich sauber testen.

---

## 🎤 Idee 2 — Eurovision Song Contest (1975–2024)

**Datensatz**: Abstimmungspunkte aller Jahre, Land-zu-Land-Vergabe, Platzierungen  
**Quelle**: kaggle.com/datasets/datagraver/eurovision-song-contest-scores-19752019

```
Grobe Frage: Wird Eurovision durch Musikqualität oder geopolitische Nähe entschieden?
|
├── Bevorzugen Länder ihre Nachbarn beim Voting?
|       └── Konkret: Korreliert die geografische Distanz zwischen zwei Ländern
|                    mit den abgegebenen Punkten (Pearsons r)?
|
├── Beeinflusst die Liedsprache die Platzierung?
|       └── Konkret: Schneiden englischsprachige Songs besser ab als muttersprachliche?
|
└── Gibt es stabile Abstimmungsblöcke?
        └── Konkret: Sind Punkte zwischen nordischen oder balkanischen Ländern
                     überdurchschnittlich häufig hoch (χ²-Test)?
```

**Warum interessant**: Deutschland verliert jedes Jahr — ist das statistisch erklärbar?

---

## 🐿️ Idee 3 — NYC Squirrel Census 2018

**Datensatz**: ~3.000 Eichhörnchen-Beobachtungen in Central Park (Fellfarbe, Verhalten, Standort, ob sie sich Menschen nähern)  
**Quelle**: data.cityofnewyork.us (NYC Open Data)

```
Grobe Frage: Was beeinflusst das Verhalten von Eichhörnchen gegenüber Menschen?
|
├── Hängt die Annäherungsbereitschaft vom Standort ab?
|       └── Konkret: Nähern sich Eichhörnchen in stark frequentierten Parkzonen
|                    Menschen häufiger als in ruhigen Bereichen?
|
├── Spielt die Fellfarbe eine Rolle?
|       └── Konkret: Unterscheidet sich die Annäherungsrate zwischen grauen,
|                    schwarzen und zimtfarbenen Eichhörnchen (χ²-Test)?
|
└── Beeinflusst die Tageszeit das Verhalten?
        └── Konkret: Ist die Annäherungsrate morgens signifikant anders als
                     nachmittags (Mann-Whitney)?
```

**Warum interessant**: 323 Freiwillige haben 2018 zwei Wochen lang jeden Eichhörnchen in Central Park gezählt und kategorisiert. Das Dataset existiert wirklich.

---

## 🧱 Idee 4 — LEGO Sets (1980–2024)

**Datensatz**: ~18.000 LEGO-Sets mit Teilezahl, Preis, Thema, Erscheinungsjahr  
**Quelle**: rebrickable.com / kaggle.com (mehrere verfügbare Datasets)

```
Grobe Frage: Hat sich der LEGO-Preis im Verhältnis zur Qualität verändert?
|
├── Ist der Preis pro Stein gestiegen?
|       └── Konkret: Wie hat sich der durchschnittliche Preis/Teil zwischen
|                    1990 und 2024 entwickelt (Zeitreihenanalyse)?
|
├── Kosten lizenzierte Themen mehr?
|       └── Konkret: Ist der Preis/Teil bei Star Wars- und Marvel-Sets signifikant
|                    höher als bei LEGO-eigenen Themen (t-Test)?
|
└── Sagt die Teilezahl den Preis zuverlässig vorher?
        └── Konkret: Wie stark korrelieren Teilezahl und Verkaufspreis (Pearsons r)?
```

---

## 🎲 Idee 5 — Board Game Geek Ratings

**Datensatz**: ~20.000 Brettspiele mit BGG-Score, Komplexität, Spielzeit, Spieleranzahl, Mechaniken  
**Quelle**: kaggle.com/datasets/andrewmvd/board-games

```
Grobe Frage: Was macht ein Brettspiel erfolgreich?
|
├── Beeinflusst die Komplexität die Bewertung?
|       └── Konkret: Korreliert das "Weight"-Rating (Komplexität 1–5)
|                    mit dem BGG-Score (Pearsons r)?
|
├── Gibt es eine optimale Spieleranzahl?
|       └── Konkret: Werden 2-Spieler-Spiele signifikant anders bewertet
|                    als Partyspiele für 6+ Personen?
|
└── Haben bestimmte Mechaniken Vorteile?
        └── Konkret: Erhalten Spiele mit "Worker Placement" im Schnitt höhere
                     Scores als Spiele mit "Roll and Move"?
```

---

## 🦶 Idee 6 — Bigfoot Sightings (BFRO Database)

**Datensatz**: ~5.000 georeferenzierte Sichtungsberichte in den USA (Klasse A/B/C, Jahr, Bundesstaat, Beschreibung)  
**Quelle**: kaggle.com/datasets/josephvm/bigfoot-sightings-data

```
Grobe Frage: Gibt es Muster in Bigfoot-Sichtungen, die auf konkrete Ursachen hinweisen?
|
├── Hängen Sichtungen mit Bevölkerungsdichte zusammen?
|       └── Konkret: Korreliert die Anzahl der Sichtungen pro Bundesstaat
|                    mit der Einwohnerdichte (Spearmans ρ)?
|
├── Gibt es saisonale Muster?
|       └── Konkret: In welchen Monaten treten Sichtungen am häufigsten auf
|                    und weicht das von einer Gleichverteilung ab (χ²-Test)?
|
└── Unterscheiden sich Klasse-A- und Klasse-B-Sichtungen geografisch?
        └── Konkret: Treten direkte Sichtungen (Klasse A) näher an
                     Waldflächen auf als indirekte (Klasse B)?
```

**Warum interessant**: Bigfoot als seriöses Analysethema zu präsentieren ist der Peak akademischer Energie.

---

## 👻 Idee 7 — Haunted Places in the USA

**Datensatz**: ~10.000 gemeldete Spukorte in den USA (Ortstyp, Beschreibung, Stadt, Bundesstaat)  
**Quelle**: kaggle.com/datasets/sujaykapadnis/haunted-places

```
Grobe Frage: Welche Orte gelten in den USA am häufigsten als "heimgesucht"?
|
├── Gibt es Ortstypen mit besonders vielen Berichten?
|       └── Konkret: Werden Hotels, Krankenhäuser oder Schulen am häufigsten
|                    als heimgesucht klassifiziert?
|
├── Gibt es geografische Cluster?
|       └── Konkret: Welche Bundesstaaten haben die höchste Spukort-Dichte
|                    pro 100.000 Einwohner?
|
└── Hängt die Art der gemeldeten Phänomene vom Ortstyp ab?
        └── Konkret: Werden in historischen Gebäuden andere Phänomene
                     beschrieben als in modernen Gebäuden (Textanalyse + χ²)?
```

---

## ☄️ Idee 8 — Meteorite Landings (NASA)

**Datensatz**: ~45.000 Meteoriteneinschläge und -funde weltweit (Masse, Jahr, Koordinaten, Typ, beobachtet vs. gefunden)  
**Quelle**: data.nasa.gov / kaggle.com/datasets/nasa/meteorite-landings

```
Grobe Frage: Gibt es Muster darin, wo und wann Meteoriten auf der Erde gefunden werden?
|
├── Werden Meteoriten gleichmäßig über die Erde verteilt gefunden?
|       └── Konkret: Weicht die geografische Verteilung der Funde von einer
|                    Gleichverteilung ab (χ²-Test nach Region)?
|
├── Hat sich die Dokumentationsrate über die Zeit verändert?
|       └── Konkret: Wie hat sich die Anzahl der registrierten Funde pro
|                    Jahrzehnt seit 1900 entwickelt?
|
└── Unterscheiden sich beobachtete Einschläge von zufälligen Funden in der Masse?
        └── Konkret: Ist der Median der Masse bei beobachteten Einschlägen
                     signifikant höher als bei Zufallsfunden (Mann-Whitney)?
```

---

## 🎢 Idee 9 — Roller Coaster Database (RCDB)

**Datensatz**: ~3.000 Achterbahnen weltweit (Höhe, Geschwindigkeit, Inversionen, Hersteller, Baujahr, Bewertung)  
**Quelle**: kaggle.com/datasets/robikscube/rollercoaster-database

```
Grobe Frage: Was bestimmt, ob eine Achterbahn besonders hoch bewertet wird?
|
├── Beeinflussen physikalische Merkmale die Bewertung?
|       └── Konkret: Korreliert die Anzahl der Inversionen mit dem Nutzer-Rating
|                    (Pearsons r)?
|
├── Produzieren bestimmte Hersteller bessere Bahnen?
|       └── Konkret: Unterscheiden sich die Durchschnittsbewertungen von
|                    Intamin, B&M und RMC signifikant (Kruskal-Wallis)?
|
└── Verlieren ältere Bahnen an Beliebtheit?
        └── Konkret: Korreliert das Baujahr negativ mit dem
                     aktuellen Bewertungsdurchschnitt (Spearmans ρ)?
```

---

## 🍺 Idee 10 — Craft Beer Database

**Datensatz**: ~2.400 US-amerikanische Craft Biere (Alkoholgehalt ABV, Bitterkeit IBU, Stil, Brauerei, Bundesstaat)  
**Quelle**: kaggle.com/datasets/nickhould/craft-cans

```
Grobe Frage: Was beeinflusst den Bitterkeitsgrad von Craft Beer?
|
├── Hängt IBU vom Alkoholgehalt (ABV) ab?
|       └── Konkret: Wie stark korrelieren ABV und IBU über alle Bierstile
|                    (Pearsons r)?
|
├── Unterscheiden sich Bierstile systematisch in IBU und ABV?
|       └── Konkret: Haben IPAs signifikant höhere IBU-Werte als Stouts
|                    (Mann-Whitney-U-Test)?
|
└── Gibt es regionale Unterschiede im US-Markt?
        └── Konkret: Produzieren Brauereien an der Westküste bitterere Biere
                     als an der Ostküste?
```

---

## 🐉 Idee 11 — D&D 5e Monster Stats

**Datensatz**: ~700 Monster aus dem Dungeons & Dragons Monster Manual (STR, DEX, CON, INT, WIS, CHA, HP, AC, Challenge Rating)  
**Quelle**: kaggle.com/datasets/mrpantherson/dnd-5e-monsters

```
Grobe Frage: Kann man die Gefährlichkeit eines D&D-Monsters aus seinen
             Statistiken vorhersagen?
|
├── Welche Attribute bestimmen den Challenge Rating am stärksten?
|       └── Konkret: Welche Statistiken (HP, AC, STR, INT …) korrelieren am
|                    stärksten mit dem CR (Korrelationsmatrix)?
|
├── Lässt sich CR durch ein Modell klassifizieren?
|       └── Konkret: Wie genau klassifiziert ein Entscheidungsbaum die
|                    CR-Kategorie (leicht/mittel/schwer/tödlich)?
|
└── Gibt es charakteristische Unterschiede zwischen Monstertypen?
        └── Konkret: Unterscheiden sich Drachen, Untote und Humanoide
                     signifikant in HP und AC (Kruskal-Wallis)?
```

---

## ☕ Idee 12 — Coffee Quality Institute (CQI)

**Datensatz**: ~1.000 Spezialitätenkaffee-Proben (Herkunftsland, Altitude, Verarbeitungsmethode, Sorte, Cupper-Score 0–100)  
**Quelle**: kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi

```
Grobe Frage: Was beeinflusst die Qualität von Spezialitätenkaffee?
|
├── Spielt die Anbaualtitude eine Rolle?
|       └── Konkret: Korreliert die Anbaualtitude (Meter ü. NN) mit dem
|                    Gesamtpunktestand (Pearsons r)?
|
├── Beeinflusst die Aufbereitungsmethode die Bewertung?
|       └── Konkret: Erhalten "Washed"-Kaffees höhere Scores als
|                    "Natural"-Kaffees (Mann-Whitney)?
|
└── Gibt es Länder, die konsistent besseren Kaffee produzieren?
        └── Konkret: Unterscheiden sich die mittleren Scores zwischen
                     äthiopischen und brasilianischen Kaffees signifikant?
```

---

## 🦈 Idee 13 — Global Shark Attack File (GSAF)

**Datensatz**: ~6.000 Hai-Angriffe seit 1845 (Land, Jahr, Aktivität des Opfers, Haiart, Ausgang)  
**Quelle**: kaggle.com/datasets/teajay/global-shark-attacks

```
Grobe Frage: Welche Faktoren erhöhen das Risiko eines Hainangriffs?
|
├── Hängt das Angriffsrisiko von der menschlichen Aktivität ab?
|       └── Konkret: Bei welchen Aktivitäten (Surfen, Schwimmen, Tauchen)
|                    treten die meisten Angriffe auf (Häufigkeitsanalyse)?
|
├── Gibt es geografische Hotspots?
|       └── Konkret: Welche Länder weisen die höchste absolute Anzahl
|                    an dokumentierten Angriffen auf?
|
└── Haben sich Angriffe über die Jahrzehnte verändert?
        └── Konkret: Hat die Anzahl der jährlich dokumentierten Angriffe
                     seit 1950 signifikant zugenommen (Trendanalyse)?
```

---

## 🎮 Idee 14 — Speedrunning World Records (speedrun.com)

**Datensatz**: Weltrekorde nach Spiel, Kategorie, Läufer und Datum  
**Quelle**: speedrun.com API / kaggle.com

```
Grobe Frage: Wie entwickeln sich Speedrunning-Weltrekorde über die Zeit?
|
├── Verbessern sich Rekorde in bestimmten Spielen schneller?
|       └── Konkret: In welchen Spielkategorien hat sich die Bestzeit
|                    prozentual am stärksten reduziert?
|
├── Gibt es einen Sättigungspunkt bei Verbesserungen?
|       └── Konkret: Flacht die Verbesserungsrate über die Zeit ab
|                    (logarithmische Regression)?
|
└── Wie lange hält ein Weltrekord durchschnittlich?
        └── Konkret: Was ist die mediane Lebensdauer eines Weltrekords
                     nach Spielgenre (Action/Plattformer/RPG)?
```

---

## 🏆 Idee 15 — Ig Nobel Prize Winners (1991–2024)

**Datensatz**: Alle Preisträger seit 1991 (Forschungsthema, Kategorie, Land, Institution)  
**Quelle**: Wikipedia / improbable.com (scraping oder manuelle Zusammenstellung, ~350 Einträge)

```
Grobe Frage: Was kennzeichnet Forschung, die mit dem Ig-Nobelpreis ausgezeichnet wird?
|
├── Welche Länder dominieren bei Ig-Nobel-Preisen?
|       └── Konkret: Welche Länder stellen die meisten Preisträger und wie
|                    verhält sich das im Vergleich zu echten Nobelpreisen?
|
├── Gibt es thematische Cluster in der ausgezeichneten Forschung?
|       └── Konkret: Welche Forschungskategorien (Medizin, Physik, Biologie,
|                    Frieden …) treten am häufigsten auf?
|
└── Hat sich die Art der Forschung über Jahrzehnte verändert?
        └── Konkret: Gibt es Zeiträume mit besonders vielen biologischen
                     oder medizinischen Preisen (Trendanalyse)?
```

**Warum interessant**: Die Ig-Nobelpreise belohnen Forschung, die "zunächst zum Lachen bringt, dann aber zum Nachdenken." Echte Studie-Beispiele: "Warum Katzen sowohl fest als auch flüssig sein können" — Physikpreis 2017.

---

## Übersichtstabelle

| # | Thema | Datengröße | Schwierigkeit | Lustigkeitsfaktor |
|---|-------|-----------|--------------|------------------|
| 1 | Ramen Ratings | 3.500 | ⭐⭐ | 🔥🔥🔥🔥 |
| 2 | Eurovision | variabel | ⭐⭐⭐ | 🔥🔥🔥 |
| 3 | NYC Squirrel Census | 3.000 | ⭐⭐ | 🔥🔥🔥🔥🔥 |
| 4 | LEGO Sets | 18.000 | ⭐⭐ | 🔥🔥🔥 |
| 5 | Board Game Geek | 20.000 | ⭐⭐⭐ | 🔥🔥 |
| 6 | Bigfoot Sightings | 5.000 | ⭐⭐ | 🔥🔥🔥🔥🔥 |
| 7 | Haunted Places | 10.000 | ⭐⭐ | 🔥🔥🔥🔥 |
| 8 | Meteorite Landings | 45.000 | ⭐⭐⭐ | 🔥🔥🔥 |
| 9 | Roller Coasters | 3.000 | ⭐⭐ | 🔥🔥🔥🔥 |
| 10 | Craft Beer | 2.400 | ⭐⭐ | 🔥🔥🔥 |
| 11 | D&D Monsters | 700 | ⭐⭐⭐ | 🔥🔥🔥🔥🔥 |
| 12 | Coffee Quality | 1.000 | ⭐⭐ | 🔥🔥🔥 |
| 13 | Shark Attacks | 6.000 | ⭐⭐ | 🔥🔥🔥🔥 |
| 14 | Speedrunning WRs | variabel | ⭐⭐⭐ | 🔥🔥🔥🔥 |
| 15 | Ig Nobel Prizes | ~350 | ⭐⭐⭐⭐ | 🔥🔥🔥🔥🔥 |
