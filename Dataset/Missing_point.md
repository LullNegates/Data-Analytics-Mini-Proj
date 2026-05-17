# Missing Points & Inconsistencies — Paper vs. Implementation

Comparing the updated PDF (`Speedrunning_Weltrekord_Analyse.pdf`, revised 2026-05-17) against session logs and the actual code.

---

## Still Open

- **η² formula — wrong citation (CRITICAL)**
  - §2.2 F3c still cites `[Lak13]` for `η² = (H − k + 1) / (N − k)`
  - Lakens [2013] is explicitly about t-tests and ANOVAs — it does not cover Kruskal-Wallis effect sizes
  - The numerical result (0.044) is correct; only the citation is wrong
  - Replace `[Lak13]` with: **Tomczak & Tomczak (2014)** — "The need to report effect size estimates revisited. An overview of some recommended measures of effect size." *Trends in Sport Sciences*, 1(21), 19–25
  - This means adding a new `[TT14]` entry to the Literaturverzeichnis and updating the in-text reference in §2.2

- **F3a velocity formula — d_pre not explicitly defined**
  - The formula `v_pre = Σ∆t_pre / d_pre` is shown but `d_pre` is never defined in words
  - The new prerequisite sentence ("Segmentlänge von mehr als 0 Tagen") implies d is a date span, which is correct, but d_pre could still be read as total calendar time since the game's first WR rather than the span within the segment
  - What the code actually computes: `d_pre = (date_of_last_pre_wr − date_of_first_pre_wr).days` — the date span between the first and last WR inside the pre-breakthrough segment only
  - Fix: add one sentence after the formulas, e.g. *"d_pre und d_post bezeichnen jeweils die Zeitspanne in Tagen zwischen dem ersten und letzten Weltrekord des jeweiligen Segments."*

---

## Fixed in This Version (no longer issues)

- ~~Model wins text said Gompertz 5/17~~ → corrected to 4/17 in §3.2 prose ✓
- ~~LOWESS missing from Table 3.2~~ → added with 0 wins and "—" for R² ✓
- ~~power_law omitted from §3.2 prose~~ → now listed as Potenzgesetz (1/17) ✓
- ~~F3a segment-size threshold unstated~~ → now explicitly stated in §2.2 ✓
- ~~Decade comparison used raw means but implied KM~~ → §3.3 now says "arithmetisch mittlere beobachtete Lebensdauer" and "Rohmittelwerte" ✓
- ~~KW underpowered not acknowledged~~ → now in §4.2 as "Teststärke" limitation ✓
- ~~Spearman p-value cutoffs missing from methods~~ → table footnote (∗ p<0,05; ∗∗∗ p<0,001) covers this ✓
